# CheeseShirts Shopify Orders Worker

A worker that periodically pulls new orders from Shopify and serializes the content for processing by other workers.

## Features

- **Shopify Integration**: Fetch orders using Shopify's GraphQL Admin API
- **Webhook Support**: Receive real-time notifications from Shopify when orders are created/updated
- **Order Processing**: Analyze orders and generate processing notes
- **Email Notifications**: Send order details with attachments to printers
- **REST API**: FastAPI-based endpoints for easy integration
- **Background Tasks**: Asynchronous email sending
- **AI Integration**: OpenAI for order analysis and summaries (optional)
- **SMS Notifications**: Twilio integration for SMS alerts (optional)
- **Order Archiving**: Stores full Shopify payloads under `Orders/<shopify_id>/order.json`

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the example environment file and configure your variables:

```bash
cp env.example .env
```

Then edit the `.env` file with your actual values:

```env
# Shopify Configuration
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=your-access-token-here
SHOPIFY_API_VERSION=2024-01

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
PRINTER_EMAIL=printer@example.com

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=1000
OPENAI_TEMPERATURE=0.7

# Other External APIs (optional)
STRIPE_API_KEY=your-stripe-secret-key
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=your-twilio-phone-number

# Application Configuration
DEBUG=True
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

### 3. Shopify App Setup

1. Create a Shopify app in your Partner Dashboard
2. Configure the following scopes:
   - `read_orders`
   - `write_orders` (for webhook management)
   - `read_products` (if needed)
3. Get your access token and store URL
4. (Optional) Set up webhooks for real-time order notifications - see **WEBHOOKS.md** for detailed instructions

### 4. External API Setup

#### OpenAI Setup
1. Get an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Add your API key to the `.env` file
3. Choose your preferred model (gpt-4, gpt-3.5-turbo, etc.)

#### Email Setup (Gmail)
1. Enable 2-factor authentication
2. Generate an App Password
3. Use the App Password in your `.env` file

#### Stripe Setup (Optional)
1. Get your secret key from [Stripe Dashboard](https://dashboard.stripe.com/apikeys)
2. Add to `.env` file for payment processing

#### Twilio Setup (Optional)
1. Get credentials from [Twilio Console](https://console.twilio.com/)
2. Add Account SID, Auth Token, and Phone Number to `.env` file

## Usage

### Start the Server

```bash
python run.py
# Or use the main file directly:
# python main.py
```

The API will be available at `http://localhost:8000`

### Quick Test

Run the setup test script to verify everything is configured correctly:

```bash
python test_setup.py
```

This will check your configuration, test API connectivity, and verify Shopify integration.

### API Endpoints

#### Get Orders
```bash
GET /orders?limit=10&status=any
```

#### Get Specific Order
```bash
GET /orders/{order_id}
```

#### Process Order
```bash
POST /orders/{order_id}/process?send_email=true
```

#### Get Processed Orders
```bash
GET /processed-orders
```

#### Test Email
```bash
POST /test-email?to_email=test@example.com
```

#### Send Custom Email
```bash
POST /send-email
Content-Type: application/json

{
  "to_email": "printer@example.com",
  "subject": "Custom Subject",
  "body": "Email body content",
  "attachment_path": "/path/to/file.json"
}
```

#### Analyze Order with OpenAI
```bash
POST /orders/{order_id}/analyze
```

#### Generate Order Summary with OpenAI
```bash
POST /orders/{order_id}/generate-summary
```

#### Send SMS
```bash
POST /send-sms?to_phone=+1234567890&message=Your message here
```

#### Check API Status
```bash
GET /api-status
```

#### Test All APIs
```bash
POST /test-apis
```

#### Validate Configuration
```bash
GET /validate-config
```

#### Webhook Management
```bash
# List registered webhooks
GET /webhooks

# Register a new webhook
POST /webhooks/register?topic=orders/create&callback_url=https://your-url.com/webhooks/orders/create

# Delete a webhook
DELETE /webhooks/{webhook_id}
```

See **WEBHOOKS.md** for detailed webhook setup instructions.

### API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```
worker-shopify-orders/
├── main.py                 # FastAPI application with webhook endpoints
├── config.py              # Configuration management
├── models.py              # Pydantic models
├── shopify_client.py      # Shopify GraphQL client with webhook support
├── order_processor.py     # Order processing logic
├── email_service.py       # Email functionality
├── external_apis.py       # External API integrations (OpenAI, Stripe, Twilio)
├── run.py                 # Simple server runner
├── test_setup.py          # Setup verification script
├── requirements.txt       # Python dependencies
├── env.example           # Environment variables template
├── README.md             # This file
├── WEBHOOKS.md           # Webhook setup guide
├── DOCKER.md             # Docker deployment guide
├── processed_orders/     # Generated order summaries
└── attachments/          # Email attachments
```

## How It Works

1. **Order Fetching**: Uses Shopify's GraphQL API to retrieve order details
2. **Webhooks**: Receives real-time notifications from Shopify (orders/create, orders/updated, etc.)
3. **Order Processing**: Analyzes orders and generates processing notes
4. **AI Analysis**: Uses OpenAI to analyze orders and generate professional summaries
5. **File Generation**: Creates JSON summaries and processing documents
6. **Email Sending**: Sends formatted emails with attachments to printers
7. **SMS Notifications**: Sends SMS updates via Twilio (optional)
8. **Payment Processing**: Handles payments via Stripe (optional)
9. **Background Tasks**: Handles email sending and other tasks asynchronously

## Example Workflow

### Manual Processing
1. **Setup**: Copy `env.example` to `.env` and configure your API keys
2. **Test Setup**: Run `python test_setup.py` to verify configuration
3. **Start Server**: Run `python run.py` to start the API
4. **Fetch Orders**: Get orders from Shopify with `GET /orders`
5. **Analyze Order**: Use AI analysis with `POST /orders/{order_id}/analyze`
6. **Process Order**: Process and send email with `POST /orders/{order_id}/process`
7. **Check Status**: View processed orders with `GET /processed-orders`

### Automated Processing (with Webhooks)
1. **Setup**: Follow steps 1-3 above
2. **Expose API**: Use ngrok or deploy to a public server
3. **Register Webhooks**: See **WEBHOOKS.md** for detailed instructions
4. **Receive Orders**: Orders are automatically sent to your webhook endpoint when created
5. **Auto-Process**: Implement background processing in webhook handlers (optional)
6. **Monitor**: Check logs for webhook activity and processing status

## Error Handling

The API includes comprehensive error handling:
- Shopify API errors are caught and returned as HTTP 500
- Email sending failures are logged but don't break the order processing
- Missing orders return HTTP 404
- Configuration errors are handled gracefully

## Security Notes

- Keep your Shopify access token secure
- Use environment variables for sensitive configuration
- Consider using a dedicated email account for the API
- Implement proper authentication for production use

## Development

To run in development mode with auto-reload:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Production Deployment

For production deployment:
1. Set `DEBUG=False` in your environment
2. Use a proper WSGI server like Gunicorn
3. Set up proper logging
4. Configure SSL/TLS
5. Implement authentication and rate limiting
