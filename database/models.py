'''
the main goal of pydantic models is data validation and parsing. 
they do not directly interact with the database

Pydantic models are user facing, whereas Database models deal with persistent storage.
'''
from typing import Optional

import pydantic
from pydantic import BaseModel, EmailStr

from database.database_models import OrderStatus


class User(BaseModel):
    """Public user profile data."""
    name: str
    age:int
    email:str
    contact:str
    city:str
class Product(BaseModel):
    """Public product catalog data."""
    pname:str
    pid:int
    price:float
    seller:str
    stock:int
    categories:list
    url:str

class ProductVariant(BaseModel):
    """A purchasable variant of a product."""
    id: int
    product_id:int
    stock:int
    name:str
    price:float

class OrderItemCreate(BaseModel):
    """Input data for adding an item to an order."""
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    """Input data for creating an order."""
    cart_item_ids: Optional[list[int]] = None  

class OrderItemOut(BaseModel):
    """Serialized order item returned by the API."""
    product_id: int
    quantity: int
    unit_price: float
    model_config = {"from_attributes": True}

class OrderOut(BaseModel):
    """Serialized order returned by the API."""
    id: int
    status: OrderStatus
    total_amount: float
    currency: str
    items: list[OrderItemOut]
    model_config = {"from_attributes": True}

class PaymentInitiate(BaseModel):
    """Payment initiation data supplied by a client."""
    vpa:str

class ChatInput(BaseModel):
    """Chat message submitted to the shopping agent."""
    messages:str

class RegisterRequest(BaseModel):
    """Credentials submitted during registration."""
    email: EmailStr | None = None
    username: EmailStr | None = None
    password: str

    @property
    def resolved_email(self) -> str:
        """Return the normalized email supplied by the caller."""
        return (self.email or self.username or "").strip().lower()
