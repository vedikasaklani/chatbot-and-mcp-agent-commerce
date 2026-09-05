"""
Shared HTTP client for the FastAPI commerce backend.

Both the in-process agent (agent/agent_tools.py) and the external MCP
server (external/mcp_server.py) expose the same set of commerce actions
to two different callers (OpenAI-style tool calls vs. MCP tool calls).
"""
import os

import requests

BASE_URL = os.environ.get("BASE_URL", "https://backend-fastapi-bktw.onrender.com")
CONNECT_TIMEOUT_SECONDS = 3.05
READ_TIMEOUT_SECONDS = 15
DEFAULT_TIMEOUT = (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)


class CommerceClient:
    """Thin typed wrapper around the FastAPI commerce backend's HTTP API."""

    def __init__(self, base_url: str = BASE_URL, timeout: tuple = DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    def _get(self, path: str, headers: dict, params: dict | None = None):
        try:
            r = requests.get(f"{self.base_url}{path}", params=params, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            return {"error": True, "detail": f"Backend unreachable: {e}"}
        return self._unwrap(r)

    def _post(self, path: str, headers: dict):
        try:
            r = requests.post(f"{self.base_url}{path}", headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            return {"error": True, "detail": f"Backend unreachable: {e}"}
        return self._unwrap(r)

    @staticmethod
    def _unwrap(r: requests.Response):
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail")
            except ValueError:
                detail = r.text or "Backend returned an empty response"
            return {"error": True, "status_code": r.status_code, "detail": detail}
        return r.json()

    def search_products(self, headers: dict, q=None, category=None,
                         min_price=None, max_price=None, in_stock=None):
        params = {}
        if q is not None:
            params["q"] = q
        if category is not None:
            params["category"] = category
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if in_stock is not None:
            if isinstance(in_stock, str):
                params["in_stock"] = "true" if in_stock.strip().lower() in {"1", "true", "yes", "y"} else "false"
            else:
                params["in_stock"] = "true" if in_stock else "false"
        return self._get("/products", headers, params=params)

    def get_product(self, headers: dict, product_id: int):
        return self._get(f"/products/{product_id}", headers)

    def get_ratings(self, headers: dict, product_id: int):
        return self._get(f"/reviews/products/{product_id}", headers)


    def view_cart(self, headers: dict):
        return self._get("/cart", headers)

    def add_to_cart(self, headers: dict, product_id: int, quantity: int):
        return self._post(f"/cart/{product_id}/{quantity}", headers)

    def remove_from_cart(self, headers: dict, product_id: int, quantity: int):
        return self._post(f"/cart/{product_id}/{quantity}/delete", headers)


    def create_order(self, headers: dict):
        return self._post("/razorpay/agent/orders", headers)

    def initiate_payment(self, headers: dict, order_id: int):
        """Used by the in-process agent: triggers sending the payment link to the user."""
        return self._post(f"/razorpay/agent/orders/{order_id}/pay", headers)

    def get_payment_link(self, headers: dict, order_id: int):
        """Used by the MCP server: returns the hosted payment-page link directly."""
        return self._post(f"/razorpay/agent/orders/{order_id}/payment-link", headers)

    def check_order_status(self, headers: dict, order_id: int):
        return self._get(f"/razorpay/agent/orders/{order_id}", headers)


commerce_client = CommerceClient()