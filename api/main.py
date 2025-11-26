from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header
from fastapi.responses import JSONResponse
from typing import List, Optional
import uvicorn
from datetime import datetime
import hmac
import hashlib
import base64

from config import Config
from models import Order, ProcessedOrder, EmailRequest
from shopify_client import ShopifyClient
from order_processor import OrderProcessor
from email_service import EmailService
from external_apis import ExternalAPIService

# Initialize configuration and services
config = Config()
shopify_client = ShopifyClient(config)
order_processor = OrderProcessor(config)
email_service = EmailService(config)
external_apis = ExternalAPIService(config)

# Create FastAPI app
app = FastAPI(
    title="CheeseShirts API",
    description="A simple backend for processing Shopify orders and sending them to t-shirt printers",
    version="1.0.0"
)

# Webhook verification helper
def verify_shopify_webhook(data: bytes, hmac_header: str, secret: str) -> bool:
    """Verify that the webhook request is from Shopify"""
    if not hmac_header or not secret:
        return False
    
    computed_hmac = base64.b64encode(
        hmac.new(
            secret.encode('utf-8'),
            data,
            hashlib.sha256
        ).digest()
    ).decode('utf-8')
    
    return hmac.compare_digest(computed_hmac, hmac_header)

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "CheeseShirts API",
        "version": "1.0.0",
        "description": "Backend for processing Shopify orders and sending to t-shirt printers",
        "endpoints": {
            "orders": "/orders",
            "process_order": "/orders/{order_id}/process",
            "processed_orders": "/processed-orders",
            "test_email": "/test-email",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/webhooks/orders/create")
async def webhook_order_created(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    x_shopify_topic: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None)
):
    """
    Webhook endpoint for Shopify order creation events
    """
    try:
        # Get raw body for HMAC verification
        body = await request.body()
        
        # Verify webhook signature if secret is configured
        if config.SHOPIFY_WEBHOOK_SECRET:
            if not verify_shopify_webhook(body, x_shopify_hmac_sha256 or "", config.SHOPIFY_WEBHOOK_SECRET):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        # Parse the webhook payload
        import json
        payload = json.loads(body.decode('utf-8'))
        
        # Log webhook receipt
        print(f"Received webhook: {x_shopify_topic} from {x_shopify_shop_domain}")
        print(f"Order ID: {payload.get('id')}, Order Name: {payload.get('name')}")
        
        # TODO: Process the order in the background if desired
        # background_tasks.add_task(process_webhook_order, payload)
        
        # Return success response (Shopify expects 200 OK)
        return {"status": "received", "order_id": payload.get("id"), "order_name": payload.get("name")}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        print(f"Webhook processing error: {str(e)}")
        # Return 200 anyway to prevent Shopify from retrying
        return {"status": "error", "message": str(e)}

@app.post("/webhooks/orders/updated")
async def webhook_order_updated(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    x_shopify_topic: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None)
):
    """
    Webhook endpoint for Shopify order update events
    """
    try:
        body = await request.body()
        
        if config.SHOPIFY_WEBHOOK_SECRET:
            if not verify_shopify_webhook(body, x_shopify_hmac_sha256 or "", config.SHOPIFY_WEBHOOK_SECRET):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        import json
        payload = json.loads(body.decode('utf-8'))
        
        print(f"Received webhook: {x_shopify_topic} from {x_shopify_shop_domain}")
        print(f"Order ID: {payload.get('id')}, Order Name: {payload.get('name')}")
        
        return {"status": "received", "order_id": payload.get("id")}
        
    except Exception as e:
        print(f"Webhook processing error: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.post("/webhooks/orders/payment")
async def webhook_order_payment(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    x_shopify_topic: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None)
):
    """
    Webhook endpoint for Shopify order payment events
    Echoes out the entire payload received from Shopify
    """
    try:
        body = await request.body()
        
        if config.SHOPIFY_WEBHOOK_SECRET:
            if not verify_shopify_webhook(body, x_shopify_hmac_sha256 or "", config.SHOPIFY_WEBHOOK_SECRET):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        import json
        payload = json.loads(body.decode('utf-8'))
        
        # Echo out all the details
        print("\n" + "="*80)
        print("RECEIVED PAYMENT WEBHOOK FROM SHOPIFY")
        print("="*80)
        print(f"Topic: {x_shopify_topic}")
        print(f"Shop Domain: {x_shopify_shop_domain}")
        print(f"Order ID: {payload.get('id')}")
        print(f"Order Name: {payload.get('name')}")
        print(f"Order Number: {payload.get('order_number')}")
        print(f"\nFull Payload:")
        print(json.dumps(payload, indent=2))
        print("="*80 + "\n")
        
        return {
            "status": "received",
            "message": "Payment webhook received and logged",
            "order_id": payload.get("id"),
            "order_name": payload.get("name"),
            "payload_keys": list(payload.keys())
        }
        
    except json.JSONDecodeError:
        print("Error: Invalid JSON payload received")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        print(f"Webhook processing error: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/orders", response_model=List[Order])
async def get_orders(limit: int = 10, status: str = "any"):
    """
    Fetch orders from Shopify
    """
    try:
        orders = shopify_client.get_orders(limit=limit, status=status)
        return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch orders: {str(e)}")

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    """
    Fetch a specific order by ID
    """
    try:
        # Add 'gid://shopify/Order/' prefix if not present
        if not order_id.startswith('gid://shopify/Order/'):
            order_id = f"gid://shopify/Order/{order_id}"
        
        order = shopify_client.get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch order: {str(e)}")

@app.post("/orders/{order_id}/process", response_model=ProcessedOrder)
async def process_order(order_id: str, background_tasks: BackgroundTasks, send_email: bool = True):
    """
    Process an order and optionally send email to printer
    """
    try:
        # Add 'gid://shopify/Order/' prefix if not present
        if not order_id.startswith('gid://shopify/Order/'):
            order_id = f"gid://shopify/Order/{order_id}"
        
        # Fetch order
        order = shopify_client.get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Process order
        processed_order = order_processor.process_order(order)
        
        # Send email in background if requested
        if send_email:
            background_tasks.add_task(
                send_order_email_task,
                processed_order
            )
        
        return processed_order
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process order: {str(e)}")

async def send_order_email_task(processed_order: ProcessedOrder):
    """
    Background task to send order email
    """
    try:
        success = email_service.send_order_email(
            processed_order.order,
            processed_order.processing_notes,
            processed_order.attachment_path
        )
        
        if success:
            processed_order.email_sent = True
            processed_order.email_sent_at = datetime.now()
            # Update the processed order file
            order_processor._save_processed_order(processed_order)
        
    except Exception as e:
        print(f"Failed to send email for order {processed_order.order.name}: {e}")

@app.get("/processed-orders", response_model=List[ProcessedOrder])
async def get_processed_orders():
    """
    Get all processed orders
    """
    try:
        processed_orders = order_processor.get_processed_orders()
        return processed_orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch processed orders: {str(e)}")

@app.post("/test-email")
async def test_email(to_email: str):
    """
    Send a test email to verify email configuration
    """
    try:
        success = email_service.send_test_email(to_email)
        if success:
            return {"message": "Test email sent successfully", "to": to_email}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test email")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send test email: {str(e)}")

@app.post("/send-email")
async def send_custom_email(email_request: EmailRequest):
    """
    Send a custom email with optional attachment
    """
    try:
        success = email_service.send_email(email_request)
        if success:
            return {"message": "Email sent successfully", "to": email_request.to_email}
        else:
            raise HTTPException(status_code=500, detail="Failed to send email")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

@app.get("/config")
async def get_config():
    """
    Get current configuration (without sensitive data)
    """
    return config.get_config_summary()

@app.get("/api-status")
async def get_api_status():
    """
    Get status of all external APIs
    """
    return external_apis.get_api_status()

@app.post("/test-apis")
async def test_apis():
    """
    Test all configured external APIs
    """
    try:
        results = await external_apis.test_all_apis()
        return {"message": "API tests completed", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test APIs: {str(e)}")

@app.post("/orders/{order_id}/analyze")
async def analyze_order(order_id: str):
    """
    Analyze an order using OpenAI
    """
    try:
        # Add 'gid://shopify/Order/' prefix if not present
        if not order_id.startswith('gid://shopify/Order/'):
            order_id = f"gid://shopify/Order/{order_id}"
        
        # Fetch order
        order = shopify_client.get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Analyze with OpenAI
        analysis = await external_apis.analyze_order(order.dict())
        if not analysis:
            raise HTTPException(status_code=500, detail="Failed to analyze order - OpenAI may not be configured")
        
        return {
            "order_id": order.id,
            "order_name": order.name,
            "analysis": analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze order: {str(e)}")

@app.post("/orders/{order_id}/generate-summary")
async def generate_order_summary(order_id: str):
    """
    Generate a professional order summary using OpenAI
    """
    try:
        # Add 'gid://shopify/Order/' prefix if not present
        if not order_id.startswith('gid://shopify/Order/'):
            order_id = f"gid://shopify/Order/{order_id}"
        
        # Fetch order
        order = shopify_client.get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Generate summary with OpenAI
        summary = await external_apis.generate_order_summary(order.dict())
        if not summary:
            raise HTTPException(status_code=500, detail="Failed to generate summary - OpenAI may not be configured")
        
        return {
            "order_id": order.id,
            "order_name": order.name,
            "summary": summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

@app.post("/send-sms")
async def send_sms(to_phone: str, message: str):
    """
    Send SMS using Twilio
    """
    try:
        success = await external_apis.send_sms(to_phone, message)
        if success:
            return {"message": "SMS sent successfully", "to": to_phone}
        else:
            raise HTTPException(status_code=500, detail="Failed to send SMS")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")

@app.get("/validate-config")
async def validate_config():
    """
    Validate that all required configuration is present
    """
    errors = config.validate_required_config()
    if errors:
        return {"valid": False, "errors": errors}
    else:
        return {"valid": True, "message": "All required configuration is present"}

@app.get("/webhooks")
async def list_webhooks():
    """
    List all registered Shopify webhooks
    """
    try:
        webhooks = shopify_client.list_webhooks()
        return {"webhooks": webhooks, "count": len(webhooks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list webhooks: {str(e)}")

@app.post("/webhooks/register")
async def register_webhook(topic: str, callback_url: str):
    """
    Register a new webhook with Shopify
    
    Example topics: "orders/create", "orders/updated", "orders/cancelled"
    """
    try:
        webhook = shopify_client.register_webhook(topic, callback_url)
        return {"message": "Webhook registered successfully", "webhook": webhook}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register webhook: {str(e)}")

@app.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """
    Delete a webhook subscription
    """
    try:
        success = shopify_client.delete_webhook(webhook_id)
        if success:
            return {"message": "Webhook deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete webhook")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete webhook: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )
