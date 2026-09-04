import asyncio
import hashlib
import hmac
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api import razorpay_integration as payments
from api import razorpay_payment_webhook as webhooks
from database import database_models as models


class Query:
    def __init__(self, result=None, results=None):
        self.result = result
        self.results = results if results is not None else []

    def join(self, *args, **kwargs): return self
    def options(self, *args, **kwargs): return self
    def filter(self, *args, **kwargs): return self
    def with_for_update(self, *args, **kwargs): return self
    def first(self): return self.result
    def all(self): return self.results
    def __getitem__(self, index): return self.results[index]


class Db:
    def __init__(self, query_result=None, query_results=None):
        self.query_result, self.query_results = query_result, query_results
        self.added, self.deleted = [], []
        self.commits = self.rollbacks = self.flushes = 0

    def query(self, *args): return Query(self.query_result, self.query_results)
    def add(self, value): self.added.append(value)
    def delete(self, value): self.deleted.append(value)
    def flush(self):
        self.flushes += 1
        self.added[-1].id = 42
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def refresh(self, value): pass


class BodyRequest:
    def __init__(self, payload, signature="valid"):
        self._body = json.dumps(payload).encode()
        if signature == "valid":
            signature = hmac.new(
                webhooks.WEBHOOK_SECRET.encode(), self._body, hashlib.sha256
            ).hexdigest()
        self.headers = {} if signature is None else {"X-Razorpay-Signature": signature}

    async def body(self): return self._body


def make_user():
    return SimpleNamespace(id=uuid4(), email="buyer@example.com", contact="9999999999")


def make_order(status=models.OrderStatus.PENDING, total=19.99):
    return SimpleNamespace(
        id=12,
        user_id=uuid4(),
        status=status,
        total_amount=total,
        currency="INR",
        razorpay_order_id="order_test_123",
        razorpay_payment_id=None,
        items=[],
    )


def test_amount_is_converted_to_paise_without_float_truncation():
    assert payments.amount_to_paise(19.99) == 1999
    assert payments.amount_to_paise(1.005) == 101


def test_create_order_calls_razorpay_and_updates_inventory(monkeypatch):
    user = make_user()
    product = SimpleNamespace(pid=1, pname="Notebook", stock=3, price=19.99)
    cart_item = SimpleNamespace(product=product, quantity=2)
    cart = SimpleNamespace(id=7)
    db = Db(query_results=[cart_item])
    created = {}

    def create(payload):
        created.update(payload)
        return {"id": "order_test_123", "status": "created"}

    monkeypatch.setattr(payments.client.order, "create", create)
    order = payments.create_order(db, user, cart, initiated_by="agent")

    assert created["amount"] == 3998
    assert order.status == models.OrderStatus.PENDING
    assert order.razorpay_order_id == "order_test_123"
    assert product.stock == 1
    assert db.deleted == [cart_item]


def test_agent_order_cap_and_provider_failure_do_not_commit(monkeypatch):
    user, cart = make_user(), SimpleNamespace(id=7)
    expensive = SimpleNamespace(product=SimpleNamespace(pid=1, pname="TV", stock=1, price=10001), quantity=1)
    with pytest.raises(HTTPException, match="exceeds max allowed"):
        payments.create_order(Db(query_results=[expensive]), user, cart, initiated_by="agent")

    db = Db(query_results=[SimpleNamespace(product=SimpleNamespace(pid=1, pname="Pen", stock=1, price=10), quantity=1)])
    monkeypatch.setattr(payments.client.order, "create", lambda payload: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(HTTPException, match="payment provider"):
        payments.create_order(db, user, cart, initiated_by="user")
    assert db.rollbacks == 1


def test_checkout_and_payment_verification_paths(monkeypatch):
    user, order = make_user(), make_order()
    db = Db(query_result=order)
    checkout = payments.order_payment(order.id, db, user)
    assert checkout["amount"] == 1999
    assert checkout["order_id"] == "order_test_123"

    with pytest.raises(HTTPException, match="incomplete"):
        payments.verify_order_payment(order.id, {}, db, user)

    verified = {}
    monkeypatch.setattr(payments.client.utility, "verify_payment_signature", lambda payload: verified.update(payload))
    result = payments.verify_order_payment(order.id, {
        "razorpay_order_id": order.razorpay_order_id,
        "razorpay_payment_id": "pay_test_123",
        "razorpay_signature": "valid-signature",
    }, db, user)
    assert result["status"] == "paid"
    assert verified["razorpay_payment_id"] == "pay_test_123"
    assert order.status == models.OrderStatus.PAID


def test_payment_link_uses_mocked_razorpay_client(monkeypatch):
    user, order = make_user(), make_order()
    captured = {}
    monkeypatch.setattr(payments.client.payment_link, "create", lambda payload: captured.update(payload) or {"short_url": "https://rzp.io/i/test"})
    assert payments.get_payment_link(order.id, Db(query_result=order), user) == {"payment_link": "https://rzp.io/i/test"}
    assert captured["amount"] == 1999
    assert captured["reference_id"] == str(order.id)


def test_order_read_and_customer_checkout_endpoints():
    user = make_user()
    orders = [make_order(), make_order(status=models.OrderStatus.PAID)]
    assert payments.get_all_order(Db(query_results=orders), user) == orders
    assert payments.order_confirmed(Db(query_results=[orders[1]]), user) == [orders[1]]
    assert payments.get_order(orders[0].id, Db(query_results=[orders[0]]), user) == orders[0]
    assert payments.initiate_payment(orders[0].id, user, Db(query_result=orders[0]))["order_id"] == "order_test_123"


def webhook_payload(event="payment.captured", amount=1999, status="captured"):
    return {
        "event": event,
        "payload": {"payment": {"entity": {
            "order_id": "order_test_123", "id": "pay_test_123", "amount": amount,
            "currency": "INR", "status": status,
        }}},
    }


def test_webhook_marks_captured_payment_paid_and_failed_payment_restores_stock():
    paid = make_order()
    assert asyncio.run(webhooks.razorpay_webhook(BodyRequest(webhook_payload()), Db(query_result=paid))) == {"status": "ok"}
    assert paid.status == models.OrderStatus.PAID

    product = SimpleNamespace(stock=1)
    failed = make_order()
    failed.items = [SimpleNamespace(product=product, quantity=2)]
    result = asyncio.run(webhooks.razorpay_webhook(BodyRequest(webhook_payload("payment.failed", status="failed")), Db(query_result=failed)))
    assert result == {"status": "ok"}
    assert failed.status == models.OrderStatus.FAILED
    assert product.stock == 3


@pytest.mark.parametrize("event", ["payment.captured", "payment.received", "order.paid"])
def test_all_success_webhook_event_types_mark_order_paid(event):
    order = make_order()
    result = asyncio.run(webhooks.razorpay_webhook(BodyRequest(webhook_payload(event)), Db(query_result=order)))
    assert result == {"status": "ok"}
    assert order.status == models.OrderStatus.PAID


def test_webhook_ignores_malformed_unknown_and_unknown_order_payloads():
    assert asyncio.run(webhooks.razorpay_webhook(BodyRequest({}), Db())) == {"status": "ignored"}
    assert asyncio.run(webhooks.razorpay_webhook(BodyRequest(webhook_payload("refund.created")), Db(query_result=make_order()))) == {"status": "ignored"}
    assert asyncio.run(webhooks.razorpay_webhook(BodyRequest(webhook_payload()), Db(query_result=None))) == {"status": "order_not_found"}


def test_webhook_rejects_unsigned_payloads():
    # Security invariant: Razorpay must sign every webhook request.
    with pytest.raises(HTTPException, match="Missing signature"):
        asyncio.run(webhooks.razorpay_webhook(BodyRequest(webhook_payload(), signature=None), Db(query_result=make_order())))


def test_webhook_rejects_an_invalid_signature():
    with pytest.raises(HTTPException, match="Invalid webhook signature"):
        asyncio.run(webhooks.razorpay_webhook(BodyRequest(webhook_payload(), signature="not-valid"), Db(query_result=make_order())))
