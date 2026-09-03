import os
from fastmcp import FastMCP
from fastmcp.server.auth.providers.workos import AuthKitProvider
from fastmcp.server.dependencies import get_access_token
from fastapi import HTTPException
import requests

from security import create_access_token       
from database.database import get_db
from database.database_models import User

mcp = FastMCP(
    "ecommerce-agent",
    auth=AuthKitProvider(
        authkit_domain="https://polished-silence-88-staging.authkit.app",
        base_url="https://external-mcp-server.onrender.com",  # must match what WorkOS has configured
    ),
)

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")


def _headers() -> dict:
    """Map the WorkOS-verified caller to one of OUR users, then mint a
    normal backend JWT for calling our own FastAPI API."""
    token = get_access_token()               # verified by AuthKitProvider already
    email = token.claims.get("email")        # confirm exact claim name on first test

    db_gen = get_db()
    db = next(db_gen)
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise HTTPException(403, "No matching account for this email")
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}
    finally:
        next(db_gen, None)  # runs get_db's cleanup/close code after the yield


#im making the connection timeout so the agent doesnt stay stuck in loops.
CONNECT_TIMEOUT_SECONDS = 3.05
READ_TIMEOUT_SECONDS = 15

def _timeout():
    return (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)


@mcp.tool()
def search_products(q: str = None, category: str = None, min_price: float = None,
                     max_price: float = None, in_stock: bool = None) -> dict:
    """Search and filter the product catalog by name, category, price range, or stock status."""
    params = {}
    if q: params["q"] = q
    if category: params["category"] = category
    if min_price is not None: params["min_price"] = min_price
    if max_price is not None: params["max_price"] = max_price
    if in_stock is not None: params["in_stock"] = "true" if in_stock else "false"

    r = requests.get(f"{BASE_URL}/products", params=params, headers=_headers(), timeout=_timeout())
    if r.status_code >= 400:
        return {"error": True, "status_code": r.status_code, "detail": r.json().get("detail")}
    return r.json()


@mcp.tool()
def get_product(product_id: int) -> dict:
    """Get full details for a single product by its id (pid), including current price and stock."""
    r = requests.get(f"{BASE_URL}/products/{product_id}", headers=_headers(), timeout=_timeout())
    if r.status_code >= 400:
        return {"error": True, "status_code": r.status_code, "detail": r.json().get("detail")}
    return r.json()


@mcp.tool()
def add_to_cart(product_id: int, quantity: int) -> dict:
    """Add a quantity of one product to the cart. Fails if quantity exceeds current stock.
    Calling this multiple times for the same product creates separate cart line items."""
    r = requests.post(f"{BASE_URL}/cart/{product_id}/{quantity}", headers=_headers(), timeout=_timeout())
    if r.status_code >= 400:
        return {"error": True, "status_code": r.status_code, "detail": r.json().get("detail")}
    return r.json()


@mcp.tool()
def remove_from_cart(product_id: int, quantity: int) -> dict:
    """Remove a quantity of a product from the cart, by product id (not cart item id)."""
    r = requests.post(f"{BASE_URL}/cart/{product_id}/{quantity}/delete", headers=_headers(), timeout=_timeout())
    if r.status_code >= 400:
        return {"error": True, "status_code": r.status_code, "detail": r.json().get("detail")}
    return r.json()


@mcp.tool()
def view_cart() -> dict:
    """Get all current cart items and the current total cost."""
    r = requests.get(f"{BASE_URL}/cart", headers=_headers(), timeout=_timeout())
    if r.status_code >= 400:
        return {"error": True, "status_code": r.status_code, "detail": r.json().get("detail")}
    return r.json()


@mcp.tool()
def create_order() -> dict:
    """Place an order using all items currently in the cart. Backend enforces a ₹10,000 cap
    for agent-initiated orders -- if this returns a 400, tell the user their order exceeds it."""
    r = requests.post(f"{BASE_URL}/razorpay/agent/orders", headers=_headers(), timeout=_timeout())
    if r.status_code >= 400:
        return {"error": True, "status_code": r.status_code, "detail": r.json().get("detail")}
    return r.json()


@mcp.tool()
def get_payment_link(order_id: int) -> dict:
    """Get a hosted payment page link for an order awaiting payment.
    Send this URL to the user -- they complete payment there."""
    r = requests.post(f"{BASE_URL}/razorpay/agent/orders/{order_id}/payment-link",
                       headers=_headers(), timeout=_timeout())
    if r.status_code >= 400:
        return {"error": True, "status_code": r.status_code, "detail": r.json().get("detail")}
    return r.json()


@mcp.tool()
def check_order_status(order_id: int) -> dict:
    """Check whether an order has been paid yet."""
    r = requests.get(f"{BASE_URL}/razorpay/agent/orders/{order_id}", headers=_headers(), timeout=_timeout())
    if r.status_code >= 400:
        return {"error": True, "status_code": r.status_code, "detail": r.json().get("detail")}
    return r.json()


@mcp.tool()
def get_ratings(product_id: int) -> dict:
    """Get customer reviews and average rating for a product by ID."""
    r = requests.get(f"{BASE_URL}/reviews/products/{product_id}", headers=_headers(), timeout=_timeout())
    if r.status_code >= 400:
        return {"error": True, "status_code": r.status_code, "detail": r.json().get("detail")}
    return r.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http",
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 9000))
              )  # local Claude Desktop connector