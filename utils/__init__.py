"""Shared application utilities."""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from database.database import get_db
from database.database_models import Cart, User
from security import get_current_user


def get_cart(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Cart:
    """Return the authenticated user's cart or stop checkout if it is absent."""
    cart = db.query(Cart).filter(Cart.user_id == user.id).first()
    if cart is None:
        raise HTTPException(status_code=400, detail="Cart is empty")
    return cart
