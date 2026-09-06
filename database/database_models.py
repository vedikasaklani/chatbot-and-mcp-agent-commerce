"""Core database model for ecommerce store"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (JSON, UUID, Column, DateTime, Enum, Float, ForeignKey,
                        Integer, String)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base=declarative_base()

class User(Base):
    __tablename__="Users"
    id=Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password=Column(String)
    age=Column(Integer)
    city=Column(String)
    contact=Column(String)

    cart = relationship(
        "Cart",
        back_populates="user",
        uselist=False
    )
    orders = relationship("Order", back_populates="user")

class Product(Base):
    __tablename__="Products"
    pname=Column(String)
    pid=Column(Integer, primary_key=True, index=True)
    price=Column(Float)
    stock=Column(Integer)
    seller=Column(String)
    categories=Column(ARRAY(String))
    url=Column(String)

class Cart(Base):
    __tablename__ = "Carts"
    id = Column(Integer, primary_key=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("Users.id"),
        unique=True
    )
    user = relationship(
        "User",
        back_populates="cart"
    )
    items = relationship(
        "CartItem",
        back_populates="cart"
    )

class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    quantity = Column(Integer, nullable=False, default=1)

    cart_id = Column(
        Integer,
        ForeignKey("Carts.id")
    )

    product_id = Column(
        Integer,
        ForeignKey("Products.pid")
    )

    cart = relationship(
        "Cart",
        back_populates="items"
    )

    product = relationship(
        "Product"
    )


class OrderStatus(str, enum.Enum):
    CREATED = "created"       # order intent saved, not yet sent to Razorpay
    PENDING = "pending"       # Razorpay order created, awaiting payment
    PAID = "paid"             # payment verified
    FAILED = "failed"
    CANCELLED = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("Users.id"), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.CREATED)
    total_amount = Column(Float, nullable=False)          # in rupees
    currency = Column(String, default="INR")
    razorpay_order_id = Column(String, nullable=True)      # filled in step 2
    razorpay_payment_id = Column(String, nullable=True)    # filled after payment
    created_at = Column(DateTime, default=datetime.now)
    decision_record = Column(JSON, nullable=True)

    items = relationship("OrderItem", back_populates="order")
    user = relationship("User", back_populates="orders")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("Products.pid"))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)  # snapshot price at order time

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class ConversationSession(Base):
    """One row per user thar works as the agent's in-progress chat context.
    there is exactly one live conversation
    per logged-in user. `started_at` is reset whenever the
    conversation is considered stale. attempt to remove need of a background job.
    """
    __tablename__ = "conversation_sessions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("Users.id"), primary_key=True)
    messages = Column(JSON, nullable=False, default=list)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True)

    product_id = Column(
        Integer,
        ForeignKey("Products.pid")
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("Users.id")
    )
    rating = Column(Integer, nullable=False)

    text = Column(String, nullable=False)

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    product = relationship("Product")
    user = relationship("User")