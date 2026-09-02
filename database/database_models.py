from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey, Float, Enum, DateTime, UUID
from sqlalchemy.orm import relationship
import enum
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime
import uuid
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

class ProductVariant(Base):
    __tablename__="Product_Variants"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("Products.pid"))
    name = Column(String)
    stock=Column(Integer)
    price = Column(Float)

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
