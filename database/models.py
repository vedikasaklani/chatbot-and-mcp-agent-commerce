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
    name: str
    age:int
    email:str
    contact:str
    city:str
class Product(BaseModel):
    pname:str
    pid:int
    price:float
    seller:str
    stock:int
    categories:list
    url:str

class ProductVariant(BaseModel):
    id: int
    product_id:int
    stock:int
    name:str
    price:float

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    cart_item_ids: Optional[list[int]] = None  

class OrderItemOut(BaseModel):
    product_id: int
    quantity: int
    unit_price: float
    model_config = {"from_attributes": True}

class OrderOut(BaseModel):
    id: int
    status: OrderStatus
    total_amount: float
    currency: str
    items: list[OrderItemOut]
    model_config = {"from_attributes": True}

class PaymentInitiate(BaseModel):
    vpa:str

class ChatInput(BaseModel):
    messages:str

class RegisterRequest(BaseModel):
    email: EmailStr | None = None
    username: EmailStr | None = None
    password: str

    @property
    def resolved_email(self) -> str:
        """Return the normalized email supplied by the caller."""
        return (self.email or self.username or "").strip().lower()
