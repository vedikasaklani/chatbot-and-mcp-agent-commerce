from fastapi import FastAPI, Depends, HTTPException
import database.database_models as database_models
from fastapi.middleware.cors import CORSMiddleware
import models
from sqlalchemy.orm import Session
from models import OrderCreate, OrderOut, ChatInput
from models import User
from models import Product
from typing import Optional
from agent.agent import run_agent
from database.database import session, get_db
from api.dependencies import oauth_scheme1
from api.razorpay_integration import agent_router, customer_router
from api.auth import router as auth_router
from security import get_current_user, oauth2_scheme
from sqlalchemy.sql.operators import ilike_op
from api.razorpay_payment_webhook import webhook_router
app=FastAPI()
app.include_router(customer_router)
app.include_router(agent_router)
app.include_router(webhook_router)
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
def chat(
    payload: ChatInput,
    auth_token: str = Depends(oauth2_scheme),
    user: database_models.User = Depends(get_current_user),
):
    return run_agent(payload.messages, token=auth_token)



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

from sqlalchemy.orm import joinedload



@app.get("/cart")
def get_cart(
    db: Session = Depends(get_db),
    user: database_models.User = Depends(get_current_user),
):
    cart = (
        db.query(database_models.Cart)
        .filter(database_models.Cart.user_id == user.id)
        .first()
    )

    if cart is None:
        return {"user": user.id, "cart": None, "total_amt": 0, "cart_items": []}

    cart_items = (
        db.query(database_models.CartItem)
        .options(joinedload(database_models.CartItem.product))
        .filter(database_models.CartItem.cart_id == cart.id)
        .all()
    )

    total_amt = sum(
        item.quantity * item.product.price
        for item in cart_items
        if item.product is not None
    )

    return {
        "user": user.id,
        "cart": cart.id,
        "total_amt": total_amt,
        "cart_items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "name": item.product.pname if item.product else None,
                "price": item.product.price if item.product else None,
                "quantity": item.quantity,
                "subtotal": item.quantity * item.product.price if item.product else 0,
            }
            for item in cart_items
        ],
    }


@app.post("/cart/{id}/{qty}")
def add_cart(
    id: int,
    qty: int,
    db: Session = Depends(get_db),
    user: database_models.User = Depends(get_current_user),
):
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive.")

    cart = (
        db.query(database_models.Cart)
        .filter(database_models.Cart.user_id == user.id)
        .first()
    )
    if cart is None:
        cart = database_models.Cart(user_id=user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)

    product = db.query(database_models.Product).filter(database_models.Product.pid == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    existing_item = (
        db.query(database_models.CartItem)
        .filter(
            database_models.CartItem.cart_id == cart.id,
            database_models.CartItem.product_id == id,
        )
        .first()
    )
    current_qty_in_cart = existing_item.quantity if existing_item else 0
    total_requested = current_qty_in_cart + qty

    if product.stock < total_requested:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    if existing_item:
        existing_item.quantity = total_requested
        db.commit()
        db.refresh(existing_item)
        return existing_item

    cart_item = database_models.CartItem(product_id=id, quantity=qty, cart_id=cart.id)
    db.add(cart_item)
    db.commit()
    db.refresh(cart_item)
    return cart_item


@app.post("/cart/{id}/{qty}/delete")
def delete_from_cart(
    id: int,
    qty: int,
    db: Session = Depends(get_db),
    user: database_models.User = Depends(get_current_user),
):
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity to remove must be positive.")

    cart = (
        db.query(database_models.Cart)
        .filter(database_models.Cart.user_id == user.id)
        .first()
    )
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found.")

    cart_item = (
        db.query(database_models.CartItem)
        .filter(
            database_models.CartItem.cart_id == cart.id,
            database_models.CartItem.product_id == id,
        )
        .first()
    )
    if cart_item is None or cart_item.quantity <= 0:
        raise HTTPException(status_code=404, detail="You cannot delete a product that is not in the cart.")

    if qty > cart_item.quantity:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove more of a product than is present in the cart.",
        )

    if qty == cart_item.quantity:
        db.delete(cart_item)
    else:
        cart_item.quantity -= qty

    db.commit()
    return {"detail": "Cart updated."} 
