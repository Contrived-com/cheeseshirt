# CheeseShirts API

A simple Python backend that integrates with Shopify's GraphQL API to process orders and send them to t-shirt printers via email.

## Features

- **Shopify Integration**: Fetch orders using Shopify's GraphQL Admin API
- **Order Processing**: Analyze orders and generate processing notes
- **Email Notifications**: Send order details with attachments to printers
- **REST API**: FastAPI-based endpoints for easy integration
- **Background Tasks**: Asynchronous email sending

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
   - `read_products` (if needed)
3. Get your access token and store URL

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
python main.py
```

The API will be available at `http://localhost:8000`

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

### API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```
cheeseshirts_api/
├── main.py                 # FastAPI application
├── config.py              # Configuration management
├── models.py              # Pydantic models
├── shopify_client.py      # Shopify GraphQL client
├── order_processor.py     # Order processing logic
├── email_service.py       # Email functionality
├── external_apis.py       # External API integrations (OpenAI, Stripe, Twilio)
├── run.py                 # Simple server runner
├── requirements.txt       # Python dependencies
├── env.example           # Environment variables template
├── README.md             # This file
├── processed_orders/     # Generated order summaries
└── attachments/          # Email attachments
```

## How It Works

1. **Order Fetching**: Uses Shopify's GraphQL API to retrieve order details
2. **Order Processing**: Analyzes orders and generates processing notes
3. **AI Analysis**: Uses OpenAI to analyze orders and generate professional summaries
4. **File Generation**: Creates JSON summaries and processing documents
5. **Email Sending**: Sends formatted emails with attachments to printers
6. **SMS Notifications**: Sends SMS updates via Twilio (optional)
7. **Payment Processing**: Handles payments via Stripe (optional)
8. **Background Tasks**: Handles email sending and other tasks asynchronously

## Example Workflow

1. **Setup**: Copy `env.example` to `.env` and configure your API keys
2. **Validate**: Check configuration with `GET /validate-config`
3. **Test APIs**: Verify all external APIs with `POST /test-apis`
4. **Fetch Orders**: Get orders from Shopify with `GET /orders`
5. **Analyze Order**: Use AI analysis with `POST /orders/{order_id}/analyze`
6. **Process Order**: Process and send email with `POST /orders/{order_id}/process`
7. **Check Status**: View processed orders with `GET /processed-orders`
8. **Send SMS**: Notify customers with `POST /send-sms`

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
