from dotenv import load_dotenv
load_dotenv()
import os
import time
import razorpay
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
import database.database_models as db_mdl
import models
from fastapi import Depends, HTTPException, Request
from models import OrderOut, PaymentInitiate
from database.database_models import CartItem, Product, User
from sqlalchemy.orm import Session, joinedload
from database.database import get_db
from fastapi import APIRouter
from security import get_current_user
from utils import get_cart


customer_router = APIRouter(
    prefix="/razorpay",
    tags=["customer orders"],
)
agent_router = APIRouter(
    prefix="/razorpay/agent",
    tags=["agent orders"],
)



api_key=os.environ["razorpay_key"]
api_secret=os.environ["razorpay_secret"]
client = razorpay.Client(auth=(api_key, api_secret))
client.enable_retry(True)

MAX_AGENT_ORDER_AMOUNT = 10000


def amount_to_paise(amount: Decimal | float) -> int:
    """Convert an INR amount to paise without float truncation."""
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def create_order(db: Session, user: User, cart: db_mdl.Cart, initiated_by: Literal["user", "agent"]):
    query = (
        db.query(db_mdl.CartItem)
        .options(joinedload(db_mdl.CartItem.product))
        .join(db_mdl.CartItem.product)
        .filter(db_mdl.CartItem.cart_id == cart.id)
        .with_for_update(of=db_mdl.Product)
    )

    cart_items = query.all()

    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    order_items = []
    total = Decimal("0")

    for cart_item in cart_items:
        product = cart_item.product
        if not product:
            raise HTTPException(status_code=404, detail=f"Product for cart item {cart_item.id} not found")
        if product.stock < cart_item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.pname}")

        line_total = Decimal(str(product.price)) * cart_item.quantity
        total += line_total

        order_items.append(db_mdl.OrderItem(
            product_id=product.pid,
            quantity=cart_item.quantity,
            unit_price=product.price
        ))

    if initiated_by=="agent" and total > Decimal(str(MAX_AGENT_ORDER_AMOUNT)):
        raise HTTPException(status_code=400, detail=f"Order total ₹{total} exceeds max allowed ₹{MAX_AGENT_ORDER_AMOUNT}")
    elif total <= 0:
        raise HTTPException(status_code=400, detail="Total amount of order to be placed cannot be 0.")

    order = db_mdl.Order(
        user_id=user.id,
        total_amount=float(total),
        status=db_mdl.OrderStatus.CREATED,
        currency="INR",  # <-- ADD THIS LINE
    )
    order.items = order_items
    db.add(order)

    # Get an ID for Razorpay's receipt without committing stock/cart changes.
    db.flush()
    try:
        response = client.order.create({
            "amount": amount_to_paise(total),
            "currency": "INR",
            "receipt": f"order_{order.id}",
            "partial_payment": False,
        })
        if response.get("status") != "created":
            raise RuntimeError("Razorpay did not create the order")
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="Order could not be created with payment provider",
        ) from exc

    order.razorpay_order_id = response["id"]
    order.status = db_mdl.OrderStatus.PENDING
    try:
        for cart_item in cart_items:
            cart_item.product.stock -= cart_item.quantity
            db.delete(cart_item)

        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save the order")

    return order

@customer_router.post("/orders", response_model=OrderOut)
def create_order_human(
    cart: db_mdl.Cart = Depends(get_cart),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_order(db, current_user, cart, initiated_by="user")

@agent_router.post("/orders", response_model=OrderOut)
def create_order_agent(
    cart: db_mdl.Cart = Depends(get_cart),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_order(db, current_user, cart, initiated_by="agent")


@customer_router.get("/order")
def get_all_order(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    # Never expose the account-wide Razorpay order list to an end user.
    return db.query(db_mdl.Order).filter(db_mdl.Order.user_id == user.id).all()


@agent_router.post("/orders/confirmed")
def order_confirmed(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    # Razorpay's account-wide payment listing must remain an operator-only
    # reconciliation task, not an authenticated customer-facing endpoint.
    return (
        db.query(db_mdl.Order)
        .filter(
            db_mdl.Order.user_id == user.id,
            db_mdl.Order.status == db_mdl.OrderStatus.PAID,
        )
        .all()
    )

@agent_router.get("/orders/{id}")
def get_order(id:int, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    query=db.query(db_mdl.Order).filter(db_mdl.Order.user_id==user.id).filter(db_mdl.Order.id==id)
    return query[0]


def prepare_checkout_session(*, order: db_mdl.Order, user: User) -> dict:
    """Return everything the frontend needs to open Razorpay Checkout for this order.

    No payment is initiated here — Checkout.js does that client-side once the
    customer picks a method and confirms. This function only guards against
    re-using an order that's already paid/in-flight and hands back the
    order/key/amount Checkout requires to render.
    """
    if order.razorpay_payment_id:
        raise HTTPException(status_code=409, detail="A payment is already in progress for this order")
    if not order.razorpay_order_id:
        raise HTTPException(status_code=409, detail="Order has no Razorpay order id")

    return {
        "key": api_key,  # public key id — safe to expose to the frontend
        "amount": amount_to_paise(order.total_amount),
        "currency": order.currency,
        "order_id": order.razorpay_order_id,   # Razorpay's order id, required by Checkout
        "name": "Your Store Name",
        "description": f"Order #{order.id}",
        "prefill": {
            "email": user.email,
            "contact": user.contact,
        },
        "notes": {"internal_order_id": str(order.id)},
    }


@agent_router.post("/orders/{id}/pay")
def order_payment(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = (
        db.query(db_mdl.Order)
        .filter(db_mdl.Order.id == id, db_mdl.Order.user_id == user.id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != db_mdl.OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail="Order is not awaiting payment")
    return prepare_checkout_session(order=order, user=user)


@agent_router.post("/orders/{id}/verify")
def verify_order_payment(
    id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = (
        db.query(db_mdl.Order)
        .filter(db_mdl.Order.id == id, db_mdl.Order.user_id == user.id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == db_mdl.OrderStatus.PAID:
        return {"status": "paid", "order_id": order.id, "payment_id": order.razorpay_payment_id}

    razorpay_order_id = payload.get("razorpay_order_id")
    razorpay_payment_id = payload.get("razorpay_payment_id")
    razorpay_signature = payload.get("razorpay_signature")

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        raise HTTPException(status_code=400, detail="Payment verification payload is incomplete")

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Razorpay payment signature") from exc

    order.razorpay_payment_id = razorpay_payment_id
    order.status = db_mdl.OrderStatus.PAID
    db.commit()
    db.refresh(order)
    return {"status": "paid", "order_id": order.id, "payment_id": razorpay_payment_id}


@customer_router.post("/orders/{order_id}/pay")
def initiate_payment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(db_mdl.Order)
        .filter(db_mdl.Order.id == order_id, db_mdl.Order.user_id == current_user.id)
        .first()
    )
    if not order or order.status != db_mdl.OrderStatus.PENDING:
        raise HTTPException(400, "Order not payable")
    return prepare_checkout_session(order=order, user=current_user)