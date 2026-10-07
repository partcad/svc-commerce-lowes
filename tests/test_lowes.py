"""
Tests of 'lowes.py', run the way PartCAD runs it: with 'runpy', the API call
as '__name__' and the call's input in the global 'request'.

lowes.com is not asked for anything. A fake session answers instead, with
pages made up for the purpose: they carry product data in the shapes Lowe's
pages have been seen to use (JSON-LD, and the '__PRELOADED_STATE__' the page's
own scripts start from), which is all the script reads.

    python -m pytest tests
"""

import json
import runpy
from pathlib import Path
from urllib.parse import quote

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "lowes.py"
BASE = "https://www.lowes.com"


class FakeResponse:
    def __init__(self, url, status_code, text):
        self.url = url
        self.status_code = status_code
        self.text = text


class FakeSession:
    """Answers each URL with a page, following the redirect it is told of."""

    def __init__(self, pages):
        # requested URL -> (final URL, status, text)
        self.pages = pages
        self.requested = []

    def get(self, url, headers=None, timeout=None):
        self.requested.append(url)
        if url not in self.pages:
            return FakeResponse(url, 404, "<html>Not found</html>")
        final, status, text = self.pages[url]
        return FakeResponse(final, status, text)


def run(api, request, session):
    request = dict(request, api=api)
    request.setdefault("partcad_version", "0.0.0")
    request.setdefault("parameters", {"storeNumber": "0595", "zipCode": "28117", "currency": "USD"})
    return runpy.run_path(str(SCRIPT), init_globals={"request": request, "session": session}, run_name=api)


@pytest.fixture
def lowes():
    """The script's functions, without calling any API."""
    return run("__main__", {}, FakeSession({}))


def search(sku):
    return "%s/search?searchTerm=%s" % (BASE, quote(sku, safe=""))


def pdp_url(product_id, name="Some-Product"):
    return "%s/pd/%s/%s" % (BASE, name, product_id)


def json_ld(document):
    return '<script type="application/ld+json">%s</script>' % json.dumps(document)


def preloaded(state, spelling="window['__PRELOADED_STATE__'] = "):
    return "<script>%s%s;window.other = {};</script>" % (spelling, json.dumps(state))


def product_page(product_id, price=None, item_number=None, model=None, state_price=None, title="A product"):
    """A product page, with the JSON-LD and the state a Lowe's one carries."""
    html = "<html><head>"
    ld = {"@context": "https://schema.org", "@type": "Product", "name": title, "sku": product_id}
    if model:
        ld["mpn"] = model
    if price is not None:
        ld["offers"] = {"@type": "Offer", "price": price, "priceCurrency": "USD"}
    html += json_ld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": []})
    html += json_ld(ld)
    detail = {"product": {"omniItemId": product_id, "title": title}}
    if item_number:
        detail["product"]["itemNumber"] = item_number
    if model:
        detail["product"]["modelId"] = model
    if state_price is not None:
        detail["location"] = {"price": {"pricingDataList": [{"finalPrice": state_price, "retailPrice": 99.99}]}}
        # Prices of other things a product's record carries.
        detail["protectionPlans"] = [{"sellingPrice": 1.23}]
    html += preloaded({"productId": product_id, "productDetails": {product_id: detail}})
    return html + "</head><body></body></html>"


# Reading a product off a page.


def test_product_page_by_product_id(lowes):
    html = product_page("1001854134", price="5.98", title="2x4x8")
    product = lowes["product_on_page"](pdp_url("1001854134"), html, "1001854134")
    assert product is not None
    assert str(product.price) == "5.98"
    assert product.title == "2x4x8"
    assert product.url == pdp_url("1001854134")


def test_product_page_by_item_and_model_number(lowes):
    html = product_page("999995424", price=2.48, item_number="755544", model="127082")
    for sku in ("755544", "127082", "999995424"):
        assert lowes["product_on_page"](pdp_url("999995424"), html, sku) is not None


def test_product_page_of_another_product(lowes):
    html = product_page("1001854134", price="5.98", item_number="1234")
    assert lowes["product_on_page"](pdp_url("1001854134"), html, "4082904") is None


def test_page_without_product_data(lowes):
    html = "<html><body>Sorry, something went wrong.</body></html>"
    assert lowes["product_on_page"](pdp_url("4082904"), html, "4082904") is None


def test_price_from_state_when_json_ld_has_none(lowes):
    html = product_page("4082904", state_price=7.48)
    assert str(lowes["product_on_page"](pdp_url("4082904"), html, "4082904").price) == "7.48"


def test_json_ld_price_comes_first(lowes):
    html = product_page("4082904", price="7.28", state_price=7.48)
    assert str(lowes["product_on_page"](pdp_url("4082904"), html, "4082904").price) == "7.28"


def test_state_price_ignores_other_things(lowes):
    detail = {
        "protectionPlans": [{"finalPrice": 1.0, "sellingPrice": 1.0}],
        "location": {"price": {"pricingDataList": [{"sellingPrice": 9.0, "finalPrice": 8.5}]}},
    }
    assert str(lowes["_state_price"](detail)) == "8.5"
    assert str(lowes["_state_price"]({"mfePrice": {"price": {"sellingPrice": "$1,234.50"}}})) == "1234.50"
    assert lowes["_state_price"]({"protectionPlans": [{"sellingPrice": 1.0}]}) is None


def test_state_spellings(lowes):
    state = {"productDetails": {"4082904": {"product": {"title": "2x6x8"}, "mfePrice": {"finalPrice": 7.48}}}}
    for spelling in (
        "window['__PRELOADED_STATE__'] = ",
        'window["__PRELOADED_STATE__"]=',
        "window.__PRELOADED_STATE__ = ",
    ):
        html = preloaded(state, spelling)
        assert str(lowes["product_on_page"](pdp_url("4082904"), html, "4082904").price) == "7.48"
    next_data = '<script id="__NEXT_DATA__" type="application/json">%s</script>' % json.dumps({"props": state})
    assert str(lowes["product_on_page"](pdp_url("4082904"), next_data, "4082904").price) == "7.48"


def test_json_ld_offer_shapes(lowes):
    offer_price = lowes["_offer_price"]
    assert str(offer_price({"price": 3})) == "3"
    assert str(offer_price([{"price": None}, {"price": "4.50"}])) == "4.50"
    assert str(offer_price({"priceSpecification": [{"price": "6.25"}]})) == "6.25"
    # A range is not a price, and nor is nothing.
    assert offer_price({"@type": "AggregateOffer", "lowPrice": 1, "highPrice": 9, "price": 1}) is None
    assert offer_price({"price": "0.00"}) is None
    assert offer_price({"price": True}) is None


def test_json_ld_graph(lowes):
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebPage"},
            {"@type": ["Product"], "url": pdp_url("1000028905"), "offers": [{"@type": "Offer", "price": 15.48}]},
        ],
    }
    product = lowes["product_on_page"](pdp_url("1000028905"), json_ld(graph), "1000028905")
    assert str(product.price) == "15.48"


def test_a_list_of_products(lowes):
    # A search results page with prices on it: the product the SKU names.
    html = product_page("1", price=1) + product_page("4082904", price="7.48", item_number="12345")
    product = lowes["product_on_page"](search("12345"), html, "12345")
    assert str(product.price) == "7.48"


def test_product_links(lowes):
    html = (
        '<a href="/pd/Top-Choice-2-in-x-6-in-x-8-ft/4082904">a</a>'
        '<a href="https://www.lowes.com/pd/Plywood/1003140514?store=1">b</a>'
        '<a href="/pd/Top-Choice-2-in-x-6-in-x-8-ft/4082904#reviews">a again</a>'
        '<a href="/pl/lumber/4294934154">not a product</a>'
    )
    assert lowes["product_links"](html) == {
        "4082904": "/pd/Top-Choice-2-in-x-6-in-x-8-ft/4082904",
        "1003140514": "https://www.lowes.com/pd/Plywood/1003140514",
    }


def test_product_id_from_url(lowes):
    product_id = lowes["_product_id_from_url"]
    assert product_id(pdp_url("4082904") + "?cm_mmc=x#reviews") == "4082904"
    assert product_id(pdp_url("4082904") + "/") == "4082904"
    assert product_id(BASE + "/pl/lumber/4294934154") is None
    assert product_id(BASE + "/pd/name/408²904") is None
    assert product_id(None) is None


# Finding a product at lowes.com.


def test_search_leads_to_the_product(lowes):
    session = FakeSession({search("1001854134"): (pdp_url("1001854134"), 200, product_page("1001854134", "5.98"))})
    lowes = run("__main__", {}, session)
    assert str(lowes["find_product"]("1001854134").price) == "5.98"
    assert session.requested == [search("1001854134")]


def test_search_lists_products(lowes):
    link = "/pd/Top-Choice-2-in-x-6-in-x-8-ft/4082904"
    results = '<a href="/pd/Other/1">x</a><a href="%s">y</a>' % link
    session = FakeSession(
        {
            search("4082904"): (search("4082904"), 200, results),
            BASE + link: (pdp_url("4082904"), 200, product_page("4082904", "7.48")),
        }
    )
    lowes = run("__main__", {}, session)
    assert str(lowes["find_product"]("4082904").price) == "7.48"


def test_search_lands_on_another_product(lowes):
    # A search that leads somewhere else is not taken for the product.
    session = FakeSession({search("755544"): (pdp_url("1"), 200, product_page("1", "1.00", item_number="9"))})
    lowes = run("__main__", {}, session)
    with pytest.raises(Exception, match="No product at lowes.com goes by '755544'"):
        lowes["find_product"]("755544")
    assert session.requested == [search("755544"), BASE + "/pd/755544"]


def test_product_page_that_cannot_be_read(lowes):
    session = FakeSession({BASE + "/pd/4082904": (pdp_url("4082904"), 200, "<html>A page of a new shape</html>")})
    lowes = run("__main__", {}, session)
    with pytest.raises(Exception, match="is the product page of SKU '4082904', but no product could be read off it"):
        lowes["find_product"]("4082904")


def test_bot_protection(lowes):
    denied = "<HTML><HEAD><TITLE>Access Denied</TITLE></HEAD><BODY>errors.edgesuite.net</BODY></HTML>"
    session = FakeSession({search("4082904"): (search("4082904"), 403, denied)})
    lowes = run("__main__", {}, session)
    with pytest.raises(Exception, match="lowes.com refused .* bot protection"):
        lowes["find_product"]("4082904")
    # It is not asked again in the same breath.
    assert session.requested == [search("4082904")]


# The API calls.


def cart(parts, skus=None, qos=None):
    composed = {"parts": parts, "qos": qos}
    if skus is not None:
        composed["skus"] = skus
    return composed


def part(name, sku, count, count_per_sku=1, vendor="lowes"):
    return {"name": name, "count": count, "vendor": vendor, "sku": sku, "count_per_sku": count_per_sku}


def test_quote():
    session = FakeSession(
        {
            search("1001854134"): (pdp_url("1001854134"), 200, product_page("1001854134", "5.98", title="2x4x8")),
            search("999995424"): (pdp_url("999995424"), 200, product_page("999995424", "2.48", title="Nuts")),
        }
    )
    parts = {
        "//pub/svc/commerce/lowes:lumber/2x4x8": part("lumber/2x4x8", "1001854134", 6),
        "//pub/svc/commerce/lowes:nut": part("nut", "999995424", 20, 16),
    }
    skus = [
        {"vendor": "lowes", "sku": "1001854134", "count": 6, "parts": ["//pub/svc/commerce/lowes:lumber/2x4x8"]},
        {"vendor": "lowes", "sku": "999995424", "count": 2, "parts": ["//pub/svc/commerce/lowes:nut"]},
    ]
    output = run("quote", {"cart": cart(parts, skus, qos="fast")}, session)["output"]
    assert output["price"] == pytest.approx(6 * 5.98 + 2 * 2.48)
    assert output["qos"] == "fast"
    assert output["cartId"] is None
    assert output["store"] == "0595"
    assert output["expire"] > output["etaMin"] - 1
    assert output["etaMin"] < output["etaMax"]
    assert output["lines"] == [
        {
            "sku": "1001854134",
            "count": 6,
            "unitPrice": 5.98,
            "price": pytest.approx(35.88),
            "title": "2x4x8",
            "url": pdp_url("1001854134"),
        },
        {
            "sku": "999995424",
            "count": 2,
            "unitPrice": 2.48,
            "price": 4.96,
            "title": "Nuts",
            "url": pdp_url("999995424"),
        },
    ]


def test_quote_is_in_whole_cents():
    session = FakeSession({search("1"): (pdp_url("1"), 200, product_page("1", "0.10"))})
    output = run("quote", {"cart": cart({"p": part("p", "1", 3)})}, session)["output"]
    # 0.1 * 3 in floating point is 0.30000000000000004.
    assert output["price"] == 0.3


def test_quote_without_skus():
    # A PartCAD that predates 'skus' sends the parts alone: the parts naming
    # one SKU add up, and are ordered in whole packs.
    session = FakeSession({search("999995424"): (pdp_url("999995424"), 200, product_page("999995424", "2.48"))})
    parts = {"a": part("a", "999995424", 10, 16), "b": part("b", "999995424", 12, 16)}
    output = run("quote", {"cart": cart(parts)}, session)["output"]
    assert [(line["sku"], line["count"]) for line in output["lines"]] == [("999995424", 2)]
    assert output["price"] == pytest.approx(4.96)


def test_quote_of_something_not_for_sale():
    with pytest.raises(Exception, match="'template' is not something a store sells"):
        run("quote", {"cart": cart({"template": {"name": "template", "count": 1, "vendor": "lowes"}})}, FakeSession({}))


def test_quote_of_another_vendor():
    parts = {"p": part("p", "204275876", 1, vendor="homedepot")}
    with pytest.raises(Exception, match="sold by 'homedepot', not by Lowe's"):
        run("quote", {"cart": cart(parts)}, FakeSession({}))


def test_quote_without_a_price():
    session = FakeSession({search("1"): (pdp_url("1"), 200, product_page("1"))})
    with pytest.raises(Exception, match="lowes.com has no price for SKU '1'"):
        run("quote", {"cart": cart({"p": part("p", "1", 1)})}, session)


@pytest.mark.parametrize(
    "vendor, sku, available",
    [("lowes", "4082904", True), ("lowes", None, False), ("homedepot", "4082904", False), (None, None, False)],
)
def test_avail(vendor, sku, available):
    request = {"vendor": vendor, "sku": sku, "count": 1, "count_per_sku": 1}
    assert run("avail", request, FakeSession({}))["output"] == {"available": available}


@pytest.mark.parametrize("api, message", [("caps", "Not supported by stores"), ("order", "Not implemented")])
def test_unsupported(api, message):
    with pytest.raises(Exception, match=message):
        run(api, {}, FakeSession({}))


# The session itself.


def test_session(monkeypatch, tmp_path):
    pytest.importorskip("requests_cache")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    request = {"api": "__main__", "parameters": {"storeNumber": "Store #0595", "zipCode": "28117"}}
    lowes = runpy.run_path(str(SCRIPT), init_globals={"request": request}, run_name="__main__")
    session = lowes["session"]
    assert lowes["STORE"] == "0595"
    assert session.cookies.get("sn", domain=".lowes.com") == "0595"
    assert session.cookies.get("zipcode", domain=".lowes.com") == "28117"
    # One cache per store: a price is for the store it was read at.
    assert "partcad_lowes_0595" in str(session.cache.db_path)


def test_what_is_cached(lowes):
    keep = lowes["_is_product_data"]
    assert keep(FakeResponse(pdp_url("1"), 200, product_page("1", "1.00")))
    assert not keep(FakeResponse(pdp_url("1"), 200, "<html>Please verify you are a human</html>"))
    assert not keep(FakeResponse(pdp_url("1"), 404, product_page("1", "1.00")))
