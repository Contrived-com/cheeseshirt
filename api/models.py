from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

class CustomAttribute(BaseModel):
    key: str
    value: str

class LineItem(BaseModel):
    title: str
    quantity: int
    variant_id: str
    price: str
    size: Optional[str] = None
    custom_attributes: List[CustomAttribute] = Field(default_factory=list)

class Order(BaseModel):
    id: str
    name: str
    email: EmailStr
    created_at: datetime
    total_price: str
    currency_code: str
    line_items: List[LineItem]
    shipping_address: Optional[dict] = None
    billing_address: Optional[dict] = None

class ProcessedOrder(BaseModel):
    order: Order
    processing_notes: str
    attachment_path: Optional[str] = None
    email_sent: bool = False
    email_sent_at: Optional[datetime] = None

class EmailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body: str
    attachment_path: Optional[str] = None
