import json
import os

import razorpay
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from api.razorpay_integration import amount_to_paise, client
from database import database_models
from database.database import get_db


webhook_router = APIRouter(tags=["webhook"])
WEBHOOK_SECRET = os.environ["razorpay_webhook_secret"]


@webhook_router.post("/webhook/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    print("WEBHOOK HIT")
    body = await request.body()
    '''
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature header")

    try:
        client.utility.verify_webhook_signature(body.decode("utf-8"), signature, WEBHOOK_SECRET)
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
'''
    try:
        payload = json.loads(body)
        payment_entity = payload["payload"]["payment"]["entity"]
        event = payload["event"]
        rp_order_id = payment_entity["order_id"]
        rp_payment_id = payment_entity["id"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return {"status": "ignored"}

    order = (
        db.query(database_models.Order)
        .options(joinedload(database_models.Order.items).joinedload(database_models.OrderItem.product))
        .filter(database_models.Order.razorpay_order_id == rp_order_id)
        .first()
    )
    if order is None:
        return {"status": "order_not_found"}

    if order.status in (
        database_models.OrderStatus.PAID,
        database_models.OrderStatus.CANCELLED,
        database_models.OrderStatus.FAILED,
    ):
        return {"status": "already_processed"}

    if event in ("payment.captured", "payment.received", "order.paid"):
        if payment_entity.get("amount") != amount_to_paise(order.total_amount) or payment_entity.get("currency") != order.currency or payment_entity.get("status") != "captured" or (order.razorpay_payment_id and order.razorpay_payment_id != rp_payment_id):
            return {"status": "payment_mismatch"}

        order.razorpay_payment_id = rp_payment_id
        order.status = database_models.OrderStatus.PAID

    elif event == "payment.failed":
        if order.razorpay_payment_id and order.razorpay_payment_id != rp_payment_id:
            return {"status": "payment_mismatch"}

        order.razorpay_payment_id = rp_payment_id
        order.status = database_models.OrderStatus.FAILED
        for item in order.items:
            if item.product is not None:
                item.product.stock += item.quantity

    else:
        return {"status": "ignored"}

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not persist webhook result")
    return {"status": "ok"}
