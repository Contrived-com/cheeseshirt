import stripe
from typing import List, Optional
from datetime import datetime
from config import Config
from models import Order, ShippingAddress


class StripeClient:
    """Client for interacting with Stripe API."""
    
    def __init__(self, config: Config):
        self.config = config
        stripe.api_key = config.STRIPE_SECRET_KEY
    
    def get_succeeded_payments(
        self,
        created_after: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Order]:
        """
        Fetch succeeded payment intents from Stripe.
        
        Args:
            created_after: Only fetch payments created after this time
            limit: Maximum number of payments to fetch
            
        Returns:
            List of Order objects
        """
        params = {
            "limit": limit,
            "expand": ["data.latest_charge"],
        }
        
        if created_after:
            params["created"] = {"gte": int(created_after.timestamp())}
        
        orders = []
        
        # Use auto-pagination to get all results
        for payment_intent in stripe.PaymentIntent.list(**params).auto_paging_iter():
            # Only process succeeded payments with our metadata
            if payment_intent.status != "succeeded":
                continue
                
            metadata = payment_intent.metadata or {}
            
            # Skip if not from our terminal (no phrase/size)
            if "phrase" not in metadata or "size" not in metadata:
                continue
            
            # Parse shipping address
            shipping = None
            if payment_intent.shipping:
                addr = payment_intent.shipping.address or {}
                shipping = ShippingAddress(
                    name=payment_intent.shipping.name or "",
                    phone=payment_intent.shipping.phone,
                    line1=addr.get("line1", ""),
                    line2=addr.get("line2"),
                    city=addr.get("city", ""),
                    state=addr.get("state", ""),
                    postal_code=addr.get("postal_code", ""),
                    country=addr.get("country", "US"),
                )
            
            order = Order(
                id=payment_intent.id,
                amount=payment_intent.amount,
                currency=payment_intent.currency,
                status=payment_intent.status,
                created_at=datetime.fromtimestamp(payment_intent.created),
                email=payment_intent.receipt_email,
                shipping=shipping,
                phrase=metadata.get("phrase", ""),
                size=metadata.get("size", ""),
                session_id=metadata.get("session_id", ""),
                raw_metadata=dict(metadata),
            )
            
            orders.append(order)
        
        return orders
    
    def get_payment_intent(self, payment_intent_id: str) -> Optional[Order]:
        """
        Fetch a specific payment intent by ID.
        
        Args:
            payment_intent_id: The PaymentIntent ID
            
        Returns:
            Order object or None if not found
        """
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if payment_intent.status != "succeeded":
                return None
            
            metadata = payment_intent.metadata or {}
            
            # Parse shipping address
            shipping = None
            if payment_intent.shipping:
                addr = payment_intent.shipping.address or {}
                shipping = ShippingAddress(
                    name=payment_intent.shipping.name or "",
                    phone=payment_intent.shipping.phone,
                    line1=addr.get("line1", ""),
                    line2=addr.get("line2"),
                    city=addr.get("city", ""),
                    state=addr.get("state", ""),
                    postal_code=addr.get("postal_code", ""),
                    country=addr.get("country", "US"),
                )
            
            return Order(
                id=payment_intent.id,
                amount=payment_intent.amount,
                currency=payment_intent.currency,
                status=payment_intent.status,
                created_at=datetime.fromtimestamp(payment_intent.created),
                email=payment_intent.receipt_email,
                shipping=shipping,
                phrase=metadata.get("phrase", ""),
                size=metadata.get("size", ""),
                session_id=metadata.get("session_id", ""),
                raw_metadata=dict(metadata),
            )
            
        except stripe.error.StripeError as e:
            print(f"Error fetching payment intent {payment_intent_id}: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test the Stripe API connection."""
        try:
            stripe.Balance.retrieve()
            return True
        except stripe.error.StripeError:
            return False

