"""
OpenAI-spec tool definitions for the commerce agent.

Design notes:
- Every tool description is written for the MODEL to read, not a human.
  Have to be explicit about units, ID types, and side effects.
- Destructive/money-moving tools (add_to_cart, create_order) have tight
  parameter constraints (minimum, type) so the model can't pass garbage
  -- catching it at the schema level gives cleaner agent behavior and fewer wasted round trips.
- `create_order` has NO way to pass arbitrary product/qty
  pairs -- it only accepts cart_item_ids: backend rule that all order items must come from the existing cart.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search and filter the product catalog by name, category, price range, or stock status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {
                        "type": "string",
                        "description": "Search by product name (partial match)",
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category",
                    },
                    "min_price": {
                        "type": "number",
                        "description": "Minimum price in rupees",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum price in rupees",
                    },
                    "in_stock": {
                        "anyOf": [
                            {"type": "boolean"},
                            {"type": "string", "enum": ["true", "false", "yes", "no", "1", "0"]},
                        ],
                        "description": "Show only items in stock. Accepts true/false or yes/no values.",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": (
                "Get full details for a single product by its id (pid). "
                "Use this to confirm price/stock for a specific product before "
                "adding it to the cart, especially if the data from list_products "
                "might be stale."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "The product's pid, e.g. 4",
                    }
                },
                "required": ["product_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": (
                "Add a quantity of one product to the shared cart. Fails with "
                "404 if the product id doesn't exist, or 400 if requested "
                "quantity exceeds current stock. Stock is NOT decremented by "
                "this call -- it only happens at order creation. Calling this "
                "multiple times for the same product creates multiple cart line "
                "items, it does not merge quantities."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "The product's pid to add to the cart",
                    },
                    "quantity": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "How many units to add. Must be a positive integer.",
                    },
                },
                "required": ["product_id", "quantity"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_cart",
            "description": (
                "Get all current cart items and the current total cost. Each item has an id (the cart "
                "item's own id, plus a product_id and quantity. "
                "a product_id, and a quantity. Always call this before "
                "create_order if you don't already know the current cart "
                "item ids -- they are NOT the same as product ids."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": (
                "Place an order using items already in the cart. This is a "
                "money-moving action -- only call it after you have confirmed "
                "the intended products, quantities, and total cost with the "
                "user (or against their stated budget). "
                "It always orders ALL current cart items. Items must already "
                "exist in the cart via add_to_cart first. "
                "The backend enforces a hard cap of ₹10000 per order and will "
                "reject anything above that with a 400 error -- treat that as "
                "a real constraint, not a suggestion, and tell the user if "
                "their request would exceed it."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_from_cart",
            "description": (
                "Remove a quantity of a product from the cart, by product id "
                "(not cart item id). If quantity removed equals or exceeds "
                "what's in the cart, the entire line item is removed. Fails "
                "with 404 if the product isn't in the cart, or if you try to "
                "remove more than is currently there -- check view_cart first "
                "if you're unsure of current quantity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "The product's pid to remove from the cart",
                    },
                    "quantity": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "How many units to remove",
                    },
                },
                "required": ["product_id", "quantity"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_payment",
            "description": (
                "Send a payment link to the user for the existing order made by them"
                "The amount is determined by the order itself and "
                "cannot be specified here."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "vpa": {
                        "type": "string",
                        "description": "The buyer's UPI ID, e.g. name@bank",
                    },
                },
                "required": ["order_id", "vpa"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ratings",
            "description": "Get avg. rating by product ID to opt better products",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "Product ID",
                    },
                },
                "required": ["product_id"],
                "additionalProperties": False,
            },
        },
    }

]


# Dispatcher to map a tool call to an actual HTTP request against the running FastAPI backend
import requests

BASE_URL = "http://127.0.0.1:8000"
CONNECT_TIMEOUT_SECONDS = 3.05
READ_TIMEOUT_SECONDS = 15


def execute_tool(name: str, auth_token:str, arguments: dict) -> dict:
    """Execute a tool call against the backend and return a JSON-able result."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    try:
        if name == "search_products":
            params = {}
            if "q" in arguments:
                params["q"] = arguments["q"]
            if "category" in arguments:
                params["category"] = arguments["category"]
            if "min_price" in arguments:
                params["min_price"] = arguments["min_price"]
            if "max_price" in arguments:
                params["max_price"] = arguments["max_price"]
            if "in_stock" in arguments:
                value = arguments["in_stock"]
                if isinstance(value, str):
                    params["in_stock"] = "true" if value.strip().lower() in {"1", "true", "yes", "y"} else "false"
                else:
                    params["in_stock"] = "true" if value else "false"

            r = requests.get(
                f"{BASE_URL}/products",
                params=params,
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
                headers=headers
                )
            print(f"DEBUG: params={params}")
            print(f"DEBUG: final URL={r.request.url}")
            
            if r.status_code == 422:
                print(f"DEBUG: 422 error detail={r.json()}")
            
            return r.json()

        elif name == "get_product":
            r = requests.get(f"{BASE_URL}/products/{arguments['product_id']}", timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS), headers=headers)

        elif name == "add_to_cart":
            r = requests.post(
                f"{BASE_URL}/cart/{arguments['product_id']}/{arguments['quantity']}",
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS), headers=headers
            )

        elif name == "view_cart":
            r = requests.get(f"{BASE_URL}/cart", timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS), headers=headers)

        elif name == "create_order":
            r = requests.post(f"{BASE_URL}/razorpay/agent/orders", timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS), headers=headers)
        elif name == "remove_from_cart":
            r = requests.post(
                f"{BASE_URL}/cart/{arguments['product_id']}/{arguments['quantity']}/delete",
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS), headers=headers
            )
        elif name == "initiate_payment":
            r = requests.post(
                f"{BASE_URL}/razorpay/agent/orders/{arguments['order_id']}/pay",
                json={"vpa": arguments["vpa"]},
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
                headers=headers,
            )
        elif name == "get_ratings":
            product_id = arguments["product_id"]
            r = requests.get(
                f"{BASE_URL}/reviews/products/{product_id}",
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
                headers=headers
            )
            return r.json()
        else:
            return {"error": f"Unknown tool: {name}"}

        if r.status_code >= 400:
            return {"error": True, "status_code": r.status_code, "detail": r.json().get("detail")}

        return r.json()

    except requests.RequestException as e:
        return {"error": True, "detail": f"Backend unreachable: {str(e)}"}
