# Shopify Webhook Setup Guide

This guide will help you set up and test Shopify webhooks with your CheeseShirts API.

## What are Webhooks?

Webhooks allow Shopify to automatically notify your API when specific events occur (like new orders). Instead of constantly polling Shopify for updates, your API receives real-time notifications.

## Prerequisites

1. **Public URL**: Your API must be accessible from the internet. Shopify needs to be able to send HTTP requests to your server.
   - For local testing, use tools like:
     - [ngrok](https://ngrok.com/) (recommended)
     - [localtunnel](https://localtunnel.github.io/)
     - [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)

2. **Shopify Store**: Access to a Shopify store (can be a development/partner store)

3. **API Credentials**: Shopify access token with appropriate permissions

## Step 1: Setup Your Environment

1. Create a `.env` file from the example:
   ```bash
   cp env.example .env
   ```

2. Fill in your Shopify credentials in `.env`:
   ```env
   SHOPIFY_STORE_URL=your-store.myshopify.com
   SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
   SHOPIFY_WEBHOOK_SECRET=your-webhook-secret  # Optional but recommended
   ```

## Step 2: Start Your API Server

```bash
python run.py
```

Your API should now be running on `http://localhost:8000` (or the port specified in your `.env`).

## Step 3: Expose Your Local Server (for testing)

If you're testing locally, you need to expose your server to the internet. Here's how to do it with ngrok:

### Using ngrok:

1. Install ngrok:
   ```bash
   # Windows (using Chocolatey)
   choco install ngrok

   # Or download from https://ngrok.com/download
   ```

2. Start ngrok:
   ```bash
   ngrok http 8000
   ```

3. You'll get a public URL like: `https://abc123.ngrok-free.app`

4. Your webhook URL will be: `https://abc123.ngrok-free.app/webhooks/orders/create`

## Step 4: Test Basic Connectivity

Before registering webhooks, verify your API is accessible:

```bash
# Test health endpoint
curl https://your-public-url.ngrok-free.app/health

# Should return: {"status":"healthy","timestamp":"..."}
```

## Step 5: Register Webhooks with Shopify

You have two options:

### Option A: Using the API (Recommended)

Use the built-in webhook registration endpoint:

```bash
curl -X POST "http://localhost:8000/webhooks/register?topic=orders/create&callback_url=https://your-public-url.ngrok-free.app/webhooks/orders/create"
```

Or use the interactive API docs:
1. Visit `http://localhost:8000/docs`
2. Find the `/webhooks/register` endpoint
3. Click "Try it out"
4. Enter:
   - `topic`: `orders/create`
   - `callback_url`: `https://your-public-url.ngrok-free.app/webhooks/orders/create`
5. Click "Execute"

### Option B: Using Shopify Admin

1. Go to your Shopify admin: `https://your-store.myshopify.com/admin`
2. Navigate to: **Settings** → **Notifications** → **Webhooks**
3. Click **Create webhook**
4. Select:
   - **Event**: Order creation
   - **Format**: JSON
   - **URL**: `https://your-public-url.ngrok-free.app/webhooks/orders/create`
5. Click **Save**

## Step 6: Verify Webhook Registration

Check that your webhooks are registered:

```bash
# Using your API
curl http://localhost:8000/webhooks

# Or visit in browser
http://localhost:8000/docs
```

You should see your registered webhook(s) listed.

## Step 7: Test the Webhook

Now test that Shopify can send webhooks to your API:

### Method 1: Create a Test Order in Shopify

1. Go to your Shopify admin
2. Navigate to **Orders** → **Create order**
3. Fill in some test data
4. Click **Create order**

### Method 2: Use Shopify's Webhook Testing (if available)

Some Shopify apps/admin interfaces allow you to send test webhooks.

### Method 3: Manual Testing with cURL

You can simulate a Shopify webhook:

```bash
curl -X POST http://localhost:8000/webhooks/orders/create \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Topic: orders/create" \
  -H "X-Shopify-Shop-Domain: your-store.myshopify.com" \
  -d '{
    "id": 12345678,
    "name": "#1001",
    "email": "customer@example.com",
    "total_price": "99.99"
  }'
```

## Step 8: Monitor Webhook Activity

Watch your API logs to see incoming webhooks:

```bash
# Your API will log webhook receipts like:
# Received webhook: orders/create from your-store.myshopify.com
# Order ID: 12345678, Order Name: #1001
```

You can also check in Shopify admin:
- **Settings** → **Notifications** → **Webhooks**
- Click on your webhook to see delivery history

## Available Webhook Endpoints

Your API has the following webhook endpoints:

- `POST /webhooks/orders/create` - Triggered when a new order is created
- `POST /webhooks/orders/updated` - Triggered when an order is updated

## Webhook Security (HMAC Verification)

For production, you should verify that webhooks are actually from Shopify:

1. Set `SHOPIFY_WEBHOOK_SECRET` in your `.env` file
2. Get this secret from Shopify when creating the webhook
3. The API will automatically verify the HMAC signature

## Troubleshooting

### Webhook not receiving data

1. **Check ngrok is running**: Make sure your tunnel is active
2. **Check URL**: Ensure the webhook URL in Shopify matches your ngrok URL
3. **Check firewall**: Ensure port 8000 is accessible
4. **Check logs**: Look at your API console output for errors

### "Invalid webhook signature" error

1. Make sure `SHOPIFY_WEBHOOK_SECRET` matches the secret in Shopify
2. Or remove/comment out the secret to disable verification (for testing only)

### Shopify shows webhook as "Failed"

1. Your API must return a 200 status code quickly (within 5 seconds)
2. Check your API logs for errors
3. Verify the endpoint URL is correct and accessible

### ngrok session expired

Free ngrok URLs expire after a few hours. Restart ngrok to get a new URL, then:
1. Update the webhook URL in Shopify, or
2. Re-register the webhook with the new URL

## Additional Webhook Topics

You can register webhooks for many other events:

- `orders/cancelled`
- `orders/fulfilled`
- `orders/paid`
- `products/create`
- `products/update`
- `customers/create`

See [Shopify's webhook documentation](https://shopify.dev/docs/api/admin-rest/2024-01/resources/webhook) for a full list.

## Production Considerations

When deploying to production:

1. **Use HTTPS**: Shopify requires HTTPS for webhook URLs
2. **Set webhook secret**: Always verify HMAC signatures in production
3. **Handle retries**: Shopify will retry failed webhooks
4. **Process async**: Use background tasks for time-consuming operations
5. **Monitor**: Set up logging and monitoring for webhook failures
6. **Rate limits**: Be aware of Shopify's rate limits

## Next Steps

Once webhooks are working:

1. Implement automatic order processing when orders are created
2. Send notifications to your printer automatically
3. Update order status back in Shopify
4. Add error handling and retry logic

## Useful Commands

```bash
# List all registered webhooks
curl http://localhost:8000/webhooks

# Register a webhook
curl -X POST "http://localhost:8000/webhooks/register?topic=orders/create&callback_url=YOUR_URL"

# Delete a webhook
curl -X DELETE "http://localhost:8000/webhooks/{webhook_id}"

# Check health
curl http://localhost:8000/health

# View API documentation
# Visit: http://localhost:8000/docs
```

## Resources

- [Shopify Webhooks Documentation](https://shopify.dev/docs/api/admin-rest/2024-01/resources/webhook)
- [ngrok Documentation](https://ngrok.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

