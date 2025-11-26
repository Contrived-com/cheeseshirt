# CheeseShirts API - Quick Reference

## Getting Started

1. **Setup Environment**
   ```bash
   cp env.example .env
   # Edit .env with your credentials
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Test Configuration**
   ```bash
   python test_setup.py
   ```

4. **Start Server**
   ```bash
   python run.py
   ```

5. **View Docs**
   - Open: http://localhost:8000/docs

## Essential Endpoints

### Health & Config
```bash
GET  /health              # Check if API is running
GET  /validate-config     # Validate configuration
GET  /config              # View current config (safe)
```

### Orders
```bash
GET  /orders              # List orders
GET  /orders/{id}         # Get specific order
POST /orders/{id}/process # Process order + send email
GET  /processed-orders    # List processed orders
```

### Webhooks (Shopify Integration)
```bash
GET    /webhooks                    # List registered webhooks
POST   /webhooks/register           # Register new webhook
DELETE /webhooks/{id}               # Delete webhook
POST   /webhooks/orders/create      # Webhook endpoint (Shopify calls this)
POST   /webhooks/orders/updated     # Webhook endpoint (Shopify calls this)
```

### Email
```bash
POST /test-email?to_email=test@example.com  # Send test email
POST /send-email                             # Send custom email
```

### AI Features (OpenAI)
```bash
POST /orders/{id}/analyze          # AI order analysis
POST /orders/{id}/generate-summary # AI summary generation
```

### External APIs
```bash
GET  /api-status          # Check API statuses
POST /test-apis           # Test all APIs
POST /send-sms            # Send SMS via Twilio
```

## Webhook Setup (Quick)

### 1. Use ngrok for local testing
```bash
ngrok http 8000
# Get URL like: https://abc123.ngrok-free.app
```

### 2. Register webhook
```bash
curl -X POST "http://localhost:8000/webhooks/register?\
topic=orders/create&\
callback_url=https://abc123.ngrok-free.app/webhooks/orders/create"
```

### 3. Test
- Create an order in Shopify
- Watch your API logs for webhook receipt

## Environment Variables (Required)

```env
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxx
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
```

## Environment Variables (Optional)

```env
SHOPIFY_WEBHOOK_SECRET=your-webhook-secret
OPENAI_API_KEY=sk-xxxxx
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
```

## Common Issues

### Can't fetch orders
- Check `SHOPIFY_ACCESS_TOKEN` in `.env`
- Verify store URL format: `your-store.myshopify.com`
- Check API permissions include `read_orders`

### Webhooks not working
- Ensure API is publicly accessible (use ngrok for testing)
- Check webhook URL in Shopify matches your public URL
- Look for HMAC verification errors (set webhook secret)
- Verify webhook is registered: `GET /webhooks`

### Email not sending
- Use Gmail App Password, not your regular password
- Enable 2FA on Gmail first
- Check SMTP settings: `smtp.gmail.com:587`

## File Locations

```
processed_orders/   # Generated order summaries (JSON)
attachments/        # Email attachments
.env                # Your configuration (create from env.example)
```

## Shopify API Scopes Needed

- `read_orders` (required)
- `write_orders` (for webhook management)
- `read_products` (optional)

## Testing Checklist

- [ ] Created `.env` file with credentials
- [ ] Ran `python test_setup.py` successfully
- [ ] Started server: `python run.py`
- [ ] Accessed API docs: http://localhost:8000/docs
- [ ] Fetched orders: `GET /orders`
- [ ] (Optional) Set up ngrok for webhooks
- [ ] (Optional) Registered webhook with Shopify
- [ ] (Optional) Tested webhook by creating order

## Documentation Files

- `README.md` - Full documentation
- `WEBHOOKS.md` - Webhook setup guide
- `DOCKER.md` - Docker deployment
- `WARP.md` - Deployment guides
- `env.example` - Configuration template

## Support

For detailed information on any feature:
1. Check the relevant .md file
2. Visit http://localhost:8000/docs
3. Review the code comments

## Quick Tips

- All order IDs can be provided with or without the `gid://shopify/Order/` prefix
- Webhook endpoints return 200 OK even on errors (to prevent Shopify retries)
- Email sending happens in the background and won't block order processing
- Use `send_email=false` when processing orders to skip email step
- OpenAI and Twilio features are optional - API works without them

