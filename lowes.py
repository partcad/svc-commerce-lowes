from datetime import datetime, timedelta, timezone
import random

from curl_cffi import requests

NOW = datetime.now(timezone.utc)


# Choose a random Chrome version to mimic for impersonation
chrome_versions = ["chrome", "chrome110"]
random_version = random.choice(chrome_versions)

# Create a session with a impersonation
session = requests.Session(impersonate="chrome110")

if not "request" in globals():
    request = {
        "api": "caps"
    }

home_page_headers = {
    "referer": "https://www.google.com/",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

product_url_search_headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en;q=0.9",
    "priority": "u=0, i",
    "referer": "https://www.lowes.com/",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
}

store_id_headers = {
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en;q=0.9",
    "priority": "u=0, i",
    "referer": "https://www.lowes.com/pd/Hillman-1-2-in-x-13-Galvanized-Steel-Hex-Nut/3037536",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

add_cart_headers_post = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en;q=0.9",
    "content-length": "8631",
    "content-type": "application/json; charset=utf-8",
    "priority": "u=0, i",
    "referer": "https://www.lowes.com/pd/Hillman-1-2-in-x-13-Galvanized-Steel-Hex-Nut/3037536",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

view_cart_headers = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en;q=0.9",
    "content-length": "8631",
    "content-type": "text/plain;charset=UTF-8",
    "priority": "u=0, i",
    "referer": "https://www.lowes.com/pd/Hillman-1-2-in-x-13-Galvanized-Steel-Hex-Nut/3037536",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

cookies_dict = {}
cookies_string = ""


def get_cookies(cookie_jar):
    """
    Refresh cookies from a response cookie jar and return as a dictionary.
    """
    return {cookie: cookie_jar[cookie] for cookie in cookie_jar}

def update_cookies_string():
    """
    Update the global cookies_string from cookies_dict.
    """
    global cookies_dict
    global cookies_string
    cookies_string = "; ".join([f"{name}={value}" for name, value in cookies_dict.items()])

def fetch_url(url, headers, method="GET", data=None, json=None):
    """
    Fetch a URL using the specified method (GET or POST), updating cookies.
    Raises an exception for 4xx or 5xx responses.
    """
    global cookies_dict
    global cookies_string
    global session

    # Choose the HTTP method
    if method.upper() == "GET":
        response = session.get(url) #, headers = {**headers, "Cookie": cookies_string}, cookies=cookies_dict)
    elif method.upper() == "POST":
        response = session.post(url, json=json) # headers={**headers, "Cookie": cookies_string}, cookies=cookies_dict, json=json)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")

    # Check for HTTP error status codes and raise exceptions
    if 400 <= response.status_code < 600:
        raise Exception(
            f"HTTP {response.status_code} Error: {response.reason}\n"
            f"URL: {url}\n"
            f"Method: {method}\n"
            f"Response Text: {response.text}"
        )

    # Update cookies if the response is successful
    cookies_dict.update(get_cookies(response.cookies))
    update_cookies_string()

    return response

    
def get_home_page():
    global home_page_headers
    url = "https://www.lowes.com/"
    fetch_url(url, home_page_headers)


def get_product_page(product_url):
    global product_url_search_headers
    fetch_url(product_url, product_url_search_headers)


def get_product_url(product_id):
    global product_url_search_headers

    url = f"https://www.lowes.com/search?searchTerm={product_id}"

    response = fetch_url(url, product_url_search_headers)
    return response.url


def get_store_id(product_id):
    global store_id_headers

    url = f"https://www.lowes.com/wpd/{product_id}/productdetail/undefined/Guest?quantity=1"

    response = fetch_url(url, store_id_headers)
    details = response.json()

    return details["productDetails"][product_id]["product"]["nearbyStore"]

def add_to_cart(product_id, quantity):
    global add_cart_headers_post

    store_id = get_store_id(product_id)

    cart_item_payload = {
        "items": [
            {
                "imageUrl": "",
                "quantity": quantity,
                "productInfo": {
                    "omniItemId": product_id
                },
                "subscriptionInfo": None,
                "fulfillmentStore": store_id,
                "isMultiPuis": True,
                "fulfillments": [
                    {
                        "fulfillmentType": "PICKUP",
                        "selected": True
                    }
                ]
            }
        ],
        "source": "PD",
        "flyout": True,
        "cartItems": [
            {
                "imageUrl": "",
                "quantity": quantity,
                "productInfo": {
                    "omniItemId": product_id
                },
                "subscriptionInfo": None,
                "fulfillmentStore": store_id,
                "isMultiPuis": True,
                "fulfillments": [
                    {
                        "fulfillmentType": "PICKUP",
                        "selected": True
                    }
                ]
            }
        ]
    }

    url = "https://www.lowes.com/purchase/api/cart/cartitems"

    fetch_url(url, add_cart_headers_post, method="POST", json=cart_item_payload)


def view_cart():
    global view_cart_headers

    url = "https://www.lowes.com/purchase/api/cart/view"
    response = fetch_url(url, view_cart_headers)
    
    return response.json()


if __name__ == "caps":
    raise Exception("Not suported by stores")

elif __name__ == "avail":
    vendor = request.get("vendor", None)
    sku = request.get("sku", None)

    if vendor == "lowes":
        output = {
            "available": True,
        }
    else:
        output = {
            "available": False,
        }

elif __name__ == "quote":
    parts = request["cart"]["parts"]
    get_home_page()
    
    for part_spec in parts.values():
        sku = part_spec.get("sku", "").replace("-", "")
        count_per_sku = part_spec["count_per_sku"]
        count = part_spec["count"]
        item_count = (count + count_per_sku - 1) // count_per_sku
        product_url = get_product_url(sku)
        get_product_page(product_url)
        add_to_cart(sku, item_count)

    cart = view_cart()
    
    output = {
        "qos": request["cart"]["qos"],
        "price": float(cart["cart"]["cartSummary"]["subTotal"]),
        "expire": (NOW + timedelta(hours=1)).timestamp(),
        "cartId": cart["cart"]["cartId"],
        "etaMin": (NOW + timedelta(hours=1)).timestamp(),
        "etaMax": (NOW + timedelta(hours=2)).timestamp(),
    }

elif __name__ == "order":
    raise Exception("Not implemented")

else:
    raise Exception("Unknown API: {}".format(__name__))
