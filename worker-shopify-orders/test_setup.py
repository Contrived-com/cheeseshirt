#!/usr/bin/env python3
"""
Quick setup test script for CheeseShirts API
Run this to verify your configuration and test basic functionality
"""

import sys
import requests
from config import Config

def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_success(text):
    """Print success message"""
    print(f"✓ {text}")

def print_error(text):
    """Print error message"""
    print(f"✗ {text}")

def print_info(text):
    """Print info message"""
    print(f"ℹ {text}")

def test_config():
    """Test configuration"""
    print_header("Configuration Check")
    
    try:
        config = Config()
        
        # Check Shopify config
        if config.SHOPIFY_ACCESS_TOKEN and config.SHOPIFY_ACCESS_TOKEN != "your-access-token-here":
            print_success(f"Shopify Store: {config.SHOPIFY_STORE_URL}")
            print_success("Shopify Access Token: Configured")
        else:
            print_error("Shopify Access Token: Not configured")
            print_info("Set SHOPIFY_ACCESS_TOKEN in .env file")
        
        # Check webhook secret
        if config.SHOPIFY_WEBHOOK_SECRET:
            print_success("Webhook Secret: Configured (recommended for production)")
        else:
            print_info("Webhook Secret: Not configured (webhooks will work but won't be verified)")
        
        # Check email config
        if config.EMAIL_USERNAME and config.EMAIL_PASSWORD:
            print_success(f"Email: {config.EMAIL_USERNAME}")
        else:
            print_error("Email: Not configured")
            print_info("Set EMAIL_USERNAME and EMAIL_PASSWORD in .env file")
        
        # Check optional services
        if config.is_openai_configured:
            print_success("OpenAI: Configured")
        else:
            print_info("OpenAI: Not configured (optional)")
        
        if config.is_twilio_configured:
            print_success("Twilio: Configured")
        else:
            print_info("Twilio: Not configured (optional)")
        
        return True
    except Exception as e:
        print_error(f"Configuration error: {str(e)}")
        return False

def test_api_connection(base_url="http://localhost:8000"):
    """Test API connection"""
    print_header("API Connection Test")
    
    try:
        # Test health endpoint
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print_success(f"API is running at {base_url}")
            data = response.json()
            print_info(f"Status: {data.get('status')}")
        else:
            print_error(f"API returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error(f"Could not connect to API at {base_url}")
        print_info("Make sure the API is running (python run.py)")
        return False
    except Exception as e:
        print_error(f"Connection error: {str(e)}")
        return False
    
    return True

def test_shopify_connection(base_url="http://localhost:8000"):
    """Test Shopify API connection"""
    print_header("Shopify Connection Test")
    
    try:
        response = requests.get(f"{base_url}/validate-config", timeout=10)
        data = response.json()
        
        if data.get("valid"):
            print_success("Shopify configuration is valid")
        else:
            print_error("Shopify configuration has errors:")
            for error in data.get("errors", []):
                print_info(f"  - {error}")
            return False
        
        # Try to fetch orders
        print_info("Attempting to fetch orders from Shopify...")
        response = requests.get(f"{base_url}/orders?limit=1", timeout=10)
        
        if response.status_code == 200:
            orders = response.json()
            print_success(f"Successfully connected to Shopify!")
            print_info(f"Found {len(orders)} order(s)")
        else:
            print_error(f"Failed to fetch orders: {response.status_code}")
            print_info(response.text)
            return False
            
    except Exception as e:
        print_error(f"Shopify connection error: {str(e)}")
        return False
    
    return True

def test_webhooks(base_url="http://localhost:8000"):
    """Test webhook endpoints"""
    print_header("Webhook Endpoints Test")
    
    try:
        # List existing webhooks
        response = requests.get(f"{base_url}/webhooks", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            webhook_count = data.get("count", 0)
            print_success(f"Webhook endpoint is accessible")
            print_info(f"Currently registered webhooks: {webhook_count}")
            
            if webhook_count > 0:
                print_info("Registered webhooks:")
                for webhook in data.get("webhooks", []):
                    print_info(f"  - {webhook.get('topic')}: {webhook.get('callback_url')}")
            else:
                print_info("No webhooks registered yet")
                print_info("Use /webhooks/register endpoint or see WEBHOOKS.md for setup instructions")
        else:
            print_error(f"Failed to list webhooks: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Webhook test error: {str(e)}")
        return False
    
    return True

def show_next_steps():
    """Show next steps"""
    print_header("Next Steps")
    
    print("\n1. Start the API server:")
    print("   python run.py")
    
    print("\n2. View API documentation:")
    print("   Visit: http://localhost:8000/docs")
    
    print("\n3. Test basic endpoints:")
    print("   curl http://localhost:8000/health")
    print("   curl http://localhost:8000/orders")
    
    print("\n4. Set up webhooks (for automatic order processing):")
    print("   - See WEBHOOKS.md for detailed instructions")
    print("   - For local testing, you'll need ngrok or similar")
    
    print("\n5. Test order processing:")
    print("   curl -X POST http://localhost:8000/orders/{order_id}/process")
    
    print("\n6. Monitor logs:")
    print("   Watch the console output for webhook events and errors")
    
    print("\nFor more information:")
    print("  - README.md - General overview")
    print("  - WEBHOOKS.md - Webhook setup guide")
    print("  - DOCKER.md - Docker deployment")
    print("  - http://localhost:8000/docs - Interactive API docs")
    print()

def main():
    """Main test function"""
    print("\n" + "="*60)
    print("  CheeseShirts API - Setup Test")
    print("="*60)
    
    # Test configuration
    config_ok = test_config()
    
    if not config_ok:
        print_header("Setup Incomplete")
        print_error("Configuration is incomplete. Please check the errors above.")
        print_info("1. Create .env file from env.example")
        print_info("2. Fill in required values (SHOPIFY_ACCESS_TOKEN, EMAIL_USERNAME, etc.)")
        print_info("3. Run this test again")
        return 1
    
    # Ask if API is running
    print_header("API Server Check")
    print_info("Is the API server running? (python run.py)")
    print_info("Testing connection...")
    
    # Test API connection
    api_ok = test_api_connection()
    
    if api_ok:
        # Test Shopify connection
        shopify_ok = test_shopify_connection()
        
        # Test webhooks
        webhooks_ok = test_webhooks()
        
        # Show results
        print_header("Test Results")
        print_success("Configuration: OK")
        print_success("API Server: OK")
        print_success("Shopify Connection: OK" if shopify_ok else "Shopify Connection: FAILED")
        print_success("Webhooks: OK" if webhooks_ok else "Webhooks: FAILED")
        
        if shopify_ok and webhooks_ok:
            print("\n" + "="*60)
            print("  ✓ All tests passed! Your API is ready to use.")
            print("="*60)
            show_next_steps()
            return 0
        else:
            print_error("\nSome tests failed. Please check the errors above.")
            return 1
    else:
        print_info("\nAPI server is not running. Start it with:")
        print_info("  python run.py")
        print_info("\nThen run this test again.")
        show_next_steps()
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)

