import openai
import stripe
from twilio.rest import Client
from typing import Optional, Dict, Any
import logging
from config import Config

logger = logging.getLogger(__name__)

class ExternalAPIService:
    def __init__(self, config: Config):
        self.config = config
        self._setup_clients()
    
    def _setup_clients(self):
        """Initialize external API clients"""
        # OpenAI client
        if self.config.is_openai_configured:
            openai.api_key = self.config.OPENAI_API_KEY
            self.openai_client = openai.OpenAI(api_key=self.config.OPENAI_API_KEY)
        else:
            self.openai_client = None
            logger.warning("OpenAI not configured - API calls will be disabled")
        
        # Stripe client
        if self.config.is_stripe_configured:
            stripe.api_key = self.config.STRIPE_API_KEY
            self.stripe_client = stripe
        else:
            self.stripe_client = None
            logger.warning("Stripe not configured - API calls will be disabled")
        
        # Twilio client
        if self.config.is_twilio_configured:
            self.twilio_client = Client(
                self.config.TWILIO_ACCOUNT_SID,
                self.config.TWILIO_AUTH_TOKEN
            )
        else:
            self.twilio_client = None
            logger.warning("Twilio not configured - API calls will be disabled")
    
    # OpenAI Methods
    async def generate_text(self, prompt: str, max_tokens: Optional[int] = None) -> Optional[str]:
        """Generate text using OpenAI API"""
        if not self.openai_client:
            logger.error("OpenAI client not configured")
            return None
        
        try:
            max_tokens = max_tokens or self.config.OPENAI_MAX_TOKENS
            
            response = self.openai_client.chat.completions.create(
                model=self.config.OPENAI_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=self.config.OPENAI_TEMPERATURE
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return None
    
    async def analyze_order(self, order_data: Dict[str, Any]) -> Optional[str]:
        """Analyze order data using OpenAI"""
        prompt = f"""
        Analyze this t-shirt order data and provide insights:
        
        Order Details:
        - Order ID: {order_data.get('id', 'N/A')}
        - Customer Email: {order_data.get('email', 'N/A')}
        - Total: {order_data.get('total_price', 'N/A')}
        - Items: {[item.get('title', 'N/A') for item in order_data.get('line_items', [])]}
        
        Please provide:
        1. Order complexity assessment
        2. Potential issues or concerns
        3. Recommended processing steps
        4. Any special customer notes or requirements
        """
        
        return await self.generate_text(prompt)
    
    async def generate_order_summary(self, order_data: Dict[str, Any]) -> Optional[str]:
        """Generate a human-readable order summary"""
        prompt = f"""
        Create a professional order summary for a t-shirt printing business:
        
        Order: {order_data.get('name', 'N/A')}
        Customer: {order_data.get('email', 'N/A')}
        Items: {[f"{item.get('title', 'N/A')} (Qty: {item.get('quantity', 0)})" for item in order_data.get('line_items', [])]}
        Total: {order_data.get('total_price', 'N/A')}
        
        Format as a clear, professional summary suitable for a printer.
        """
        
        return await self.generate_text(prompt)
    
    # Stripe Methods
    async def create_payment_intent(self, amount: int, currency: str = "usd", metadata: Optional[Dict] = None) -> Optional[Dict]:
        """Create a Stripe payment intent"""
        if not self.stripe_client:
            logger.error("Stripe client not configured")
            return None
        
        try:
            intent = self.stripe_client.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata=metadata or {}
            )
            return intent
            
        except Exception as e:
            logger.error(f"Stripe API error: {str(e)}")
            return None
    
    async def retrieve_payment_intent(self, payment_intent_id: str) -> Optional[Dict]:
        """Retrieve a Stripe payment intent"""
        if not self.stripe_client:
            logger.error("Stripe client not configured")
            return None
        
        try:
            intent = self.stripe_client.PaymentIntent.retrieve(payment_intent_id)
            return intent
            
        except Exception as e:
            logger.error(f"Stripe API error: {str(e)}")
            return None
    
    # Twilio Methods
    async def send_sms(self, to_phone: str, message: str) -> bool:
        """Send SMS using Twilio"""
        if not self.twilio_client:
            logger.error("Twilio client not configured")
            return False
        
        try:
            message_obj = self.twilio_client.messages.create(
                body=message,
                from_=self.config.TWILIO_PHONE_NUMBER,
                to=to_phone
            )
            logger.info(f"SMS sent successfully: {message_obj.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Twilio API error: {str(e)}")
            return False
    
    async def send_order_notification_sms(self, phone_number: str, order_name: str) -> bool:
        """Send order notification SMS"""
        message = f"Your t-shirt order {order_name} has been received and is being processed. We'll send you updates via email."
        return await self.send_sms(phone_number, message)
    
    # Utility Methods
    def get_api_status(self) -> Dict[str, bool]:
        """Get status of all external APIs"""
        return {
            "openai": self.config.is_openai_configured,
            "stripe": self.config.is_stripe_configured,
            "twilio": self.config.is_twilio_configured,
            "aws": self.config.is_aws_configured
        }
    
    async def test_all_apis(self) -> Dict[str, Any]:
        """Test all configured APIs"""
        results = {}
        
        # Test OpenAI
        if self.config.is_openai_configured:
            try:
                test_response = await self.generate_text("Say 'OpenAI is working' if you can read this.")
                results["openai"] = {
                    "status": "success" if test_response else "failed",
                    "response": test_response
                }
            except Exception as e:
                results["openai"] = {"status": "error", "error": str(e)}
        else:
            results["openai"] = {"status": "not_configured"}
        
        # Test Stripe
        if self.config.is_stripe_configured:
            try:
                # Just test the API key by making a simple call
                self.stripe_client.Account.retrieve()
                results["stripe"] = {"status": "success"}
            except Exception as e:
                results["stripe"] = {"status": "error", "error": str(e)}
        else:
            results["stripe"] = {"status": "not_configured"}
        
        # Test Twilio
        if self.config.is_twilio_configured:
            try:
                # Test by retrieving account info
                account = self.twilio_client.api.accounts(self.config.TWILIO_ACCOUNT_SID).fetch()
                results["twilio"] = {"status": "success", "account": account.friendly_name}
            except Exception as e:
                results["twilio"] = {"status": "error", "error": str(e)}
        else:
            results["twilio"] = {"status": "not_configured"}
        
        return results
