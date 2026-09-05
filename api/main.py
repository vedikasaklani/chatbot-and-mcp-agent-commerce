from fastapi import FastAPI, Depends, HTTPException, Header
import database.database_models as database_models
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database.models import OrderCreate, OrderOut, ChatInput, User, Product
from typing import Optional
from agent.agent import run_agent, build_decision_record, clear_conversation
from api import cart_service
from api.reviews import reviews_router
from database.database import session, get_db
from api.dependencies import oauth_scheme1
from api.razorpay_integration import agent_router, customer_router
from api.auth import router as auth_router
from security import get_current_user, oauth2_scheme
from sqlalchemy.sql.operators import ilike_op
from api.razorpay_payment_webhook import webhook_router
from pathlib import Path
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.include_router(reviews_router)
app.include_router(customer_router)
app.include_router(agent_router)
app.include_router(webhook_router)
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "https://agent-commerce-payout-automation.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
def chat(
    payload: ChatInput,
    x_chat_session_id: str = Header(..., min_length=1, max_length=128),
    auth_token: str = Depends(oauth2_scheme),
    user: database_models.User = Depends(get_current_user),
    db:Session=Depends(get_db)
):
    result=run_agent(payload.messages, token=auth_token, session_id=x_chat_session_id)
    order_id = next(
        (e["result"]["id"] for e in result["trace"]
         if e["tool"] == "create_order" and isinstance(e["result"], dict) and "id" in e["result"]),
        None,
    )

    if order_id:
        record = build_decision_record(result["trace"], payload.messages, result["final_response"], order_id)
        order = db.query(database_models.Order).filter(database_models.Order.id == order_id).first()
        if order:
            order.decision_record = record
            db.commit()

    return result


@app.delete("/chat/session", status_code=204)
def clear_chat_session(
    x_chat_session_id: str = Header(..., min_length=1, max_length=128),
    _: database_models.User = Depends(get_current_user),
):
    """Clear transient agent context when the browser session ends."""
    clear_conversation(x_chat_session_id)



@app.get("/products")
def get_products(
    q: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock: bool | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(database_models.Product)

    if q:
        query = query.filter(database_models.Product.pname.ilike(f"%{q}%"))
    if category:
        query = query.filter(database_models.Product.categories.contains([category]))
    if min_price is not None:
        query = query.filter(database_models.Product.price >= min_price)
    if max_price is not None:
        query = query.filter(database_models.Product.price <= max_price)
    if in_stock is True:
        query = query.filter(database_models.Product.stock > 0)

    return query.all()


@app.get("/products/{id}")
def get_product(
    id: int,
    db: Session=Depends(get_db)
):
    product=db.query(database_models.Product).filter(database_models.Product.pid==id).first()
    return product


@app.get("/cart")
def get_cart(
    db: Session = Depends(get_db),
    user: database_models.User = Depends(get_current_user),
):
    cart = cart_service.find_cart(db, user)
    return cart_service.serialize_cart(db, cart, user.id)


@app.post("/cart/{id}/{qty}")
def add_cart(
    id: int,
    qty: int,
    db: Session = Depends(get_db),
    user: database_models.User = Depends(get_current_user),
):
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive.")

    cart = cart_service.get_or_create_cart(db, user)
    return cart_service.add_item(db, cart, id, qty)


@app.post("/cart/{id}/{qty}/delete")
def delete_from_cart(
    id: int,
    qty: int,
    db: Session = Depends(get_db),
    user: database_models.User = Depends(get_current_user),
):
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity to remove must be positive.")

    cart = cart_service.find_cart(db, user)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found.")

    cart_service.remove_item(db, cart, id, qty)
    return {"detail": "Cart updated."}


# Serve the frontend through an HTTP route instead of exposing its Windows
# filesystem path to the browser.
frontend_directory = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=frontend_directory, html=True), name="frontend")