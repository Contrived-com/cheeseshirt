from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class ShippingAddress(BaseModel):
    """Shipping address from Stripe."""
    name: str
    phone: Optional[str] = None
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str


class OrderMetadata(BaseModel):
    """Custom metadata we store on PaymentIntent."""
    session_id: str
    phrase: str
    size: str
    source: str = "monger-terminal"


class Order(BaseModel):
    """Processed order from Stripe."""
    id: str  # PaymentIntent ID
    amount: int  # in cents
    currency: str
    status: str
    created_at: datetime
    
    # Customer info
    email: Optional[str] = None
    shipping: Optional[ShippingAddress] = None
    
    # Our custom data
    phrase: str
    size: str
    session_id: str
    
    # Raw data for reference
    raw_metadata: Dict[str, Any] = {}


class OrderSyncState(BaseModel):
    """State for tracking what we've synced."""
    last_sync_at: Optional[datetime] = None
    last_payment_intent_id: Optional[str] = None
    total_orders_synced: int = 0

