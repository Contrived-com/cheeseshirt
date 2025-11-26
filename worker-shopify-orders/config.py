import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file
load_dotenv()

class Config:
    def __init__(self):
        # Load environment variables
        self._load_config()
    
    def _load_config(self):
        """Load all configuration from environment variables"""
        # Shopify Configuration
        self.SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL", "your-store.myshopify.com")
        self.SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
        self.SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2024-01")
        self.SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")
        
        # Email Configuration
        self.SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        self.EMAIL_USERNAME = os.getenv("EMAIL_USERNAME", "")
        self.EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
        self.PRINTER_EMAIL = os.getenv("PRINTER_EMAIL", "printer@example.com")
        
        # OpenAI Configuration
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
        self.OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "1000"))
        self.OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
        
        # Other External APIs
        self.STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
        self.TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
        
        # Application Configuration
        self.DEBUG = os.getenv("DEBUG", "True").lower() == "true"
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", "8000"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # Database Configuration
        self.DATABASE_URL = os.getenv("DATABASE_URL", "")
        
        # Security Configuration
        self.SECRET_KEY = os.getenv("SECRET_KEY", "")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
        
        # File Storage Configuration
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "")
        self.AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    
    @property
    def shopify_graphql_url(self) -> str:
        """Get Shopify GraphQL API URL"""
        return f"https://{self.SHOPIFY_STORE_URL}/admin/api/{self.SHOPIFY_API_VERSION}/graphql.json"
    
    @property
    def is_openai_configured(self) -> bool:
        """Check if OpenAI is properly configured"""
        return bool(self.OPENAI_API_KEY)
    
    @property
    def is_stripe_configured(self) -> bool:
        """Check if Stripe is properly configured"""
        return bool(self.STRIPE_API_KEY)
    
    @property
    def is_twilio_configured(self) -> bool:
        """Check if Twilio is properly configured"""
        return bool(self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN)
    
    @property
    def is_aws_configured(self) -> bool:
        """Check if AWS is properly configured"""
        return bool(self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY)
    
    def validate_required_config(self) -> list:
        """Validate that required configuration is present"""
        errors = []
        
        if not self.SHOPIFY_ACCESS_TOKEN:
            errors.append("SHOPIFY_ACCESS_TOKEN is required")
        
        if not self.EMAIL_USERNAME:
            errors.append("EMAIL_USERNAME is required")
        
        if not self.EMAIL_PASSWORD:
            errors.append("EMAIL_PASSWORD is required")
        
        return errors
    
    def get_config_summary(self) -> dict:
        """Get a summary of configuration (without sensitive data)"""
        return {
            "shopify_store_url": self.SHOPIFY_STORE_URL,
            "shopify_api_version": self.SHOPIFY_API_VERSION,
            "smtp_server": self.SMTP_SERVER,
            "smtp_port": self.SMTP_PORT,
            "printer_email": self.PRINTER_EMAIL,
            "openai_model": self.OPENAI_MODEL,
            "openai_configured": self.is_openai_configured,
            "stripe_configured": self.is_stripe_configured,
            "twilio_configured": self.is_twilio_configured,
            "aws_configured": self.is_aws_configured,
            "debug": self.DEBUG,
            "host": self.HOST,
            "port": self.PORT,
            "log_level": self.LOG_LEVEL
        }
