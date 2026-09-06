"""Cart business logic"""
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

import database.database_models as database_models


def find_cart(db: Session, user: database_models.User) -> database_models.Cart | None:
    """Return the user's cart, or None if they've never added anything to it."""
    return (
        db.query(database_models.Cart)
        .filter(database_models.Cart.user_id == user.id)
        .first()
    )


def get_or_create_cart(db: Session, user: database_models.User) -> database_models.Cart:
    """Return the user's cart, creating an empty one on first use."""
    cart = find_cart(db, user)
    if cart is None:
        cart = database_models.Cart(user_id=user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def serialize_cart(db: Session, cart: database_models.Cart | None, user_id) -> dict:
    """Build the /cart response shape: totals plus line items with product details."""
    if cart is None:
        return {"user": user_id, "cart": None, "total_amt": 0, "cart_items": []}

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
        "user": user_id,
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


def add_item(db: Session, cart: database_models.Cart, product_id: int, quantity: int):
    """Add `quantity` of `product_id` to `cart`, merging into an existing line item.

    Raises HTTPException(404) if the product doesn't exist, or 400 if the
    combined quantity would exceed current stock.
    """
    product = db.query(database_models.Product).filter(database_models.Product.pid == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    existing_item = (
        db.query(database_models.CartItem)
        .filter(
            database_models.CartItem.cart_id == cart.id,
            database_models.CartItem.product_id == product_id,
        )
        .first()
    )
    current_qty_in_cart = existing_item.quantity if existing_item else 0
    total_requested = current_qty_in_cart + quantity

    if product.stock < total_requested:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    if existing_item:
        existing_item.quantity = total_requested
        db.commit()
        db.refresh(existing_item)
        return existing_item

    cart_item = database_models.CartItem(product_id=product_id, quantity=quantity, cart_id=cart.id)
    db.add(cart_item)
    db.commit()
    db.refresh(cart_item)
    return cart_item


def remove_item(db: Session, cart: database_models.Cart, product_id: int, quantity: int) -> None:
    """Remove `quantity` of `product_id` from `cart`, deleting the line item if it hits zero.

    Raises HTTPException(404) if the product isn't in the cart, or 400 if
    trying to remove more than is currently there.
    """
    cart_item = (
        db.query(database_models.CartItem)
        .filter(
            database_models.CartItem.cart_id == cart.id,
            database_models.CartItem.product_id == product_id,
        )
        .first()
    )
    if cart_item is None or cart_item.quantity <= 0:
        raise HTTPException(status_code=404, detail="You cannot delete a product that is not in the cart.")

    if quantity > cart_item.quantity:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove more of a product than is present in the cart.",
        )

    if quantity == cart_item.quantity:
        db.delete(cart_item)
    else:
        cart_item.quantity -= quantity

    db.commit()