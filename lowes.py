"""
The Lowe's online store, as a PartCAD provider of the type 'store'.

PartCAD runs this file with 'runpy', once per call: the call is '__name__'
('avail', 'quote', ...), its input is the global 'request', and the answer is
whatever is left in the global 'output'. See "Providers" in PartCAD's
configuration documentation.

A quote is what the products cost at one Lowe's store, as their product pages
on lowes.com say. Each SKU in the cart is priced once and multiplied by the
number of it to order, and the quote is the sum. Nothing is put in a cart at
lowes.com, so a quote has no cart ID to order from later; ordering is not
implemented, the same as for '//pub/svc/commerce/homedepot'.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote as url_quote
from urllib.parse import urlsplit

NOW = datetime.now(timezone.utc)

BASE_URL = "https://www.lowes.com"
VENDOR = "lowes"

if "request" not in globals():
    request = {"api": "caps"}


# What lowes.com is asked for, and how.


def _parameter(name):
    """A provider parameter as a string, or None where it is not set."""
    value = (request.get("parameters") or {}).get(name)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _digits(value):
    """'value' as the ASCII digits it holds, or None.

    ASCII only: 'str.isdigit()' is true of superscripts and other scripts'
    digits too.
    """
    if value is None:
        return None
    digits = "".join(char for char in value if "0" <= char <= "9")
    return digits or None


STORE = _digits(_parameter("storeNumber"))
ZIP_CODE = _digits(_parameter("zipCode"))


def _is_product_data(response):
    """Whether a response is worth keeping: a page that describes products.

    Everything else is asked for again next time. Above all an answer from the
    bot protection in front of lowes.com, which can arrive as a '200' page of
    its own: kept, it would stand in for every product page for a day.
    """
    if response.status_code != 200:
        return False
    text = response.text
    return "application/ld+json" in text or "__PRELOADED_STATE__" in text or "__NEXT_DATA__" in text


def _session():
    import requests_cache

    # Prices differ from one store to the next, and a cached page says nothing
    # of which store it was priced for -- so each store has a cache of its own.
    name = "partcad_lowes" + ("_" + STORE if STORE else "")
    session = requests_cache.CachedSession(
        name,
        use_cache_dir=True,
        # A page is kept for a day, whatever caching headers came with it. A
        # quote is an estimate, and the more often lowes.com is asked, the
        # sooner its bot protection stops answering.
        cache_control=False,
        expire_after=timedelta(days=1),
        allowable_codes=[200],
        allowable_methods=["GET"],
        filter_fn=_is_product_data,
    )
    # Which store the pages are priced for. Without these, lowes.com picks one.
    if STORE:
        session.cookies.set("sn", STORE, domain=".lowes.com")
    if ZIP_CODE:
        session.cookies.set("zipcode", ZIP_CODE, domain=".lowes.com")
    return session


if "session" not in globals():
    session = _session()


def _get(url):
    """GET a page from lowes.com, or raise if lowes.com refuses to answer."""
    response = session.get(
        url,
        headers={
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "partcad/%s" % request.get("partcad_version", "unknown"),
        },
        # Well inside the 180 seconds PartCAD gives a whole quote by default,
        # which can take a few pages for each SKU in it.
        timeout=(10, 20),
    )
    text = response.text if response.status_code != 200 else ""
    if response.status_code in (403, 429) or "Access Denied" in text:
        raise Exception(
            "lowes.com refused %s (HTTP %d): its bot protection turned the request "
            "away. Prices that were fetched before are kept for a day; try again "
            "later." % (url, response.status_code)
        )
    return response


# Reading a product off a page.
#
# A page describes its products twice: as JSON-LD, the structured data a
# search engine reads, and as the state the page's own scripts start from
# ('__PRELOADED_STATE__', or '__NEXT_DATA__' where the page is built with
# Next.js). Lowe's changes the shape of both from time to time, so no single
# path into either is relied on.


class Product:
    """What one record on a page says about a product."""

    def __init__(self, ids, price=None, title=None, url=None):
        # Every number the product goes by: the product ID its URL ends with,
        # the item number, the model number, the barcode.
        self.ids = {str(value).strip() for value in ids if isinstance(value, (str, int)) and str(value).strip()}
        self.price = price
        self.title = title if isinstance(title, str) else None
        self.url = url if isinstance(url, str) else None
        if self.url and self.url.startswith("/"):
            self.url = BASE_URL + self.url

    def names(self, sku):
        return sku.casefold() in {value.casefold() for value in self.ids}


def _as_price(value):
    """A price as a Decimal, or None where 'value' is not one."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").strip()
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return price if price.is_finite() and price > 0 else None


def _product_id_from_url(url):
    """The product ID a product page's URL ends with ('/pd/<name>/<ID>'), or None."""
    if not isinstance(url, str):
        return None
    # The path alone: a query or a fragment is not part of the ID.
    path = urlsplit(url).path.rstrip("/")
    if "/pd/" not in path:
        return None
    last = path.split("/")[-1]
    return last if last and all("0" <= char <= "9" for char in last) else None


def _nodes(node):
    """Every object in a JSON document, the document itself included."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _nodes(value)
    elif isinstance(node, list):
        for value in node:
            yield from _nodes(value)


def _scripts(html, attribute):
    """The text of each '<script>' tag whose attributes match 'attribute'."""
    pattern = r"<script\b[^>]*" + attribute + r"[^>]*>(.*?)</script>"
    for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
        yield match.group(1)


def _json_ld(html):
    for text in _scripts(html, r"""type\s*=\s*["']?application/ld\+json"""):
        # Each block is its own document: a page usually has several, and
        # joining their text is not JSON.
        try:
            yield json.loads(text)
        except ValueError:
            continue


def _offer_price(offers):
    """The price an offer states, or None."""
    for offer in offers if isinstance(offers, list) else [offers]:
        if not isinstance(offer, dict):
            continue
        # A range of prices is not the price of the product.
        if offer.get("@type") == "AggregateOffer":
            continue
        price = _as_price(offer.get("price"))
        if price is not None:
            return price
        specs = offer.get("priceSpecification")
        for spec in specs if isinstance(specs, list) else [specs]:
            if isinstance(spec, dict):
                price = _as_price(spec.get("price"))
                if price is not None:
                    return price
    return None


# The numbers a product goes by, as JSON-LD names them.
JSON_LD_IDS = ("sku", "productID", "mpn", "model", "gtin", "gtin12", "gtin13", "gtin14")


def _products_in_json_ld(html):
    for document in _json_ld(html):
        for node in _nodes(document):
            kind = node.get("@type")
            if "Product" not in (kind if isinstance(kind, list) else [kind]):
                continue
            ids = [node.get(key) for key in JSON_LD_IDS]
            for key in ("url", "@id"):
                ids.append(_product_id_from_url(node.get(key)))
            yield Product(ids, _offer_price(node.get("offers")), node.get("name"), node.get("url"))


STATE = re.compile(r"""window(?:\.__PRELOADED_STATE__|\[\s*["']__PRELOADED_STATE__["']\s*\])\s*=\s*""")


def _states(html):
    decoder = json.JSONDecoder()
    for match in STATE.finditer(html):
        # The object alone, whatever follows it in the script.
        try:
            state, _ = decoder.raw_decode(html, match.end())
        except ValueError:
            continue
        yield state
    for text in _scripts(html, r"""id\s*=\s*["']?__NEXT_DATA__"""):
        try:
            yield json.loads(text)
        except ValueError:
            continue


def _first_price(node, key):
    """The first price under 'key' anywhere in 'node', or None."""
    for child in _nodes(node):
        price = _as_price(child.get(key))
        if price is not None:
            return price
    return None


def _state_price(detail):
    """The price of the product a state's record is for, or None.

    It is looked for only where a record keeps its own price, and not anywhere
    in it: a record can carry the prices of other things too (a protection
    plan, the products shown beside it). The final price comes before the
    selling price: it is what is paid, once a promotion is taken off.
    """
    location = detail.get("location") if isinstance(detail.get("location"), dict) else {}
    places = [location.get("price"), detail.get("mfePrice"), detail.get("price")]
    for key in ("finalPrice", "sellingPrice"):
        for place in places:
            if isinstance(place, (dict, list)):
                price = _first_price(place, key)
                if price is not None:
                    return price
    return None


# The numbers a product goes by, as a state's record of it names them.
STATE_IDS = ("productId", "omniItemId", "itemNumber", "modelId", "barcode")


def _products_in_state(state):
    for node in _nodes(state):
        details = node.get("productDetails")
        if not isinstance(details, dict):
            continue
        for key, detail in details.items():
            if not isinstance(detail, dict):
                continue
            product = detail.get("product") if isinstance(detail.get("product"), dict) else {}
            ids = [key] + [product.get(name) for name in STATE_IDS]
            yield Product(ids, _state_price(detail), product.get("title"), product.get("pdURL"))


def _products(html):
    """Every record of a product on a page, the JSON-LD ones first."""
    products = list(_products_in_json_ld(html))
    for state in _states(html):
        products.extend(_products_in_state(state))
    return products


def _merge(products, ids, url):
    """The records of one product, as one."""
    merged = Product(ids, url=url)
    for product in products:
        merged.ids |= product.ids
        merged.price = merged.price if merged.price is not None else product.price
        merged.title = merged.title or product.title
    return merged


def product_on_page(url, html, sku):
    """The product 'sku' names, as the page at 'url' describes it, or None.

    The SKU can be any number the product goes by: its product ID, its item
    number, its model number. It is checked against what the page says rather
    than trusted to the page being the right one -- a search can land anywhere.
    """
    products = _products(html)
    product_id = _product_id_from_url(url)
    if product_id is not None:
        # A product page: everything on it about the product it is for.
        own = [product for product in products if product_id in product.ids]
        merged = _merge(own, [product_id], url)
        if own and merged.names(sku):
            return merged
    # A page about other things that names this product among them -- in each
    # of the records about it, which need not all go by the same number.
    named = [product for product in products if product.names(sku)]
    if not named:
        return None
    ids = set().union(*(product.ids for product in named))
    same = [product for product in products if product.ids & ids]
    return _merge(same, [], next((product.url for product in same if product.url), None))


def product_links(html):
    """Every product page ('/pd/<name>/<ID>') a page links to, once each."""
    links = {}
    for match in re.finditer(r"""(?:https://www\.lowes\.com)?/pd/[^\s"'<>\\?#]+/(\d+)""", html):
        links.setdefault(match.group(1), match.group(0))
    return links


def find_product(sku):
    """
    The product 'sku' names at lowes.com, with its price at the store.

    The SKU a package states is the product ID, the number a product page's
    URL ends with -- it is what Lowe's own structured data calls the SKU. An
    item number ("Item #") or a model number works too, as long as a search for
    it at lowes.com leads to the one product.
    """
    tried = []
    unreadable = []

    def look(url):
        response = _get(url)
        tried.append("%s (HTTP %d)" % (url, response.status_code))
        if response.status_code != 200:
            return None, response
        product = product_on_page(response.url, response.text, sku)
        if product is None and _product_id_from_url(response.url) == sku:
            unreadable.append(response.url)
        return product, response

    for url in (
        "%s/search?searchTerm=%s" % (BASE_URL, url_quote(sku, safe="")),
        "%s/pd/%s" % (BASE_URL, url_quote(sku, safe="")),
    ):
        product, response = look(url)
        if product is not None:
            return product
        if response.status_code != 200:
            continue

        # A list of products: follow the one the SKU names, or the only one.
        links = product_links(response.text)
        if sku in links:
            follow = [links[sku]]
        elif len(links) == 1:
            follow = list(links.values())
        else:
            follow = []
        for link in follow:
            product, _ = look(link if link.startswith("http") else BASE_URL + link)
            if product is not None:
                return product

    if unreadable:
        # Found, and then not understood: that is lowes.com having changed the
        # shape of its pages, not the SKU being wrong.
        raise Exception(
            "%s is the product page of SKU '%s', but no product could be read off it" % (unreadable[0], sku)
        )
    raise Exception("No product at lowes.com goes by '%s'. Tried: %s" % (sku, "; ".join(tried)))


# The cart.


def order_lines(cart):
    """
    (vendor, SKU, how many of it to order), one per SKU.

    PartCAD works the number out itself and hands it over as 'skus', where one
    SKU can be a set of several parts. A PartCAD that predates that sends the
    parts alone, and the same is worked out here for a SKU of one kind of
    thing: the parts that name it add up, and are ordered in whole packs.
    """
    for name, part in (cart.get("parts") or {}).items():
        if not part.get("vendor") or not part.get("sku"):
            raise Exception("'%s' is not something a store sells: it has no vendor and SKU" % name)

    if "skus" in cart:
        return [(line["vendor"], str(line["sku"]), int(line["count"])) for line in cart["skus"]]

    needed = {}
    for part in (cart.get("parts") or {}).values():
        key = (part["vendor"], str(part["sku"]))
        per_sku = max(int(part.get("count_per_sku") or 1), 1)
        count, smallest = needed.get(key, (0, per_sku))
        # The same SKU named with two pack sizes is a mistake in the
        # declarations; the smaller pack is the one that cannot be short.
        needed[key] = (count + int(part["count"]), min(smallest, per_sku))
    return [(vendor, sku, -(-count // per_sku)) for (vendor, sku), (count, per_sku) in sorted(needed.items())]


def quote(cart):
    lines = []
    total = Decimal(0)
    for vendor, sku, count in order_lines(cart):
        if vendor != VENDOR:
            raise Exception("SKU '%s' is sold by '%s', not by Lowe's" % (sku, vendor))
        product = find_product(sku.strip())
        if product.price is None:
            raise Exception("lowes.com has no price for SKU '%s' (%s)" % (sku, product.url or "no product page"))
        total += product.price * count
        lines.append(
            {
                "sku": sku,
                "count": count,
                "unitPrice": float(product.price),
                "price": float(product.price * count),
                "title": product.title,
                "url": product.url,
            }
        )

    return {
        "qos": cart.get("qos"),
        "price": float(total),
        "expire": (NOW + timedelta(hours=1)).timestamp(),
        # Nothing was put in a cart at lowes.com.
        "cartId": None,
        # Picked up at the store.
        "etaMin": (NOW + timedelta(hours=1)).timestamp(),
        "etaMax": (NOW + timedelta(hours=2)).timestamp(),
        "store": STORE,
        "lines": lines,
    }


if __name__ == "caps":
    raise Exception("Not supported by stores")

elif __name__ == "avail":
    # Lowe's sells what is declared as Lowe's: there is no asking lowes.com
    # whether it stocks something without fetching the product's page, and that
    # is left to the quote. A declaration with no SKU is a product of no size
    # yet, which nobody can order.
    output = {
        "available": request.get("vendor") == VENDOR and bool(request.get("sku")),
    }

elif __name__ == "quote":
    output = quote(request["cart"])

elif __name__ == "order":
    raise Exception("Not implemented")

elif __name__ != "__main__":
    raise Exception("Unknown API: {}".format(__name__))
