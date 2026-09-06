"""Tool definitions and dispatch logic for the shopping agent."""

from commerce_client import commerce_client


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
                },
                "required": ["order_id"],
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


def execute_tool(name: str, auth_token: str, arguments: dict) -> dict:
    """Execute a tool call against the backend and return a JSON-able result."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    if name == "search_products":
        return commerce_client.search_products(
            headers,
            q=arguments.get("q"),
            category=arguments.get("category"),
            min_price=arguments.get("min_price"),
            max_price=arguments.get("max_price"),
            in_stock=arguments.get("in_stock"),
        )
    elif name == "get_product":
        return commerce_client.get_product(headers, arguments["product_id"])
    elif name == "add_to_cart":
        return commerce_client.add_to_cart(headers, arguments["product_id"], arguments["quantity"])
    elif name == "view_cart":
        return commerce_client.view_cart(headers)
    elif name == "create_order":
        return commerce_client.create_order(headers)
    elif name == "remove_from_cart":
        return commerce_client.remove_from_cart(headers, arguments["product_id"], arguments["quantity"])
    elif name == "initiate_payment":
        return commerce_client.initiate_payment(headers, arguments["order_id"])
    elif name == "get_ratings":
        return commerce_client.get_ratings(headers, arguments["product_id"])
    else:
        return {"error": f"Unknown tool: {name}"}