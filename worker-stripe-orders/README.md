# Cheeseshirt Stripe Orders Worker

A background worker that polls Stripe for successful payments and persists order data locally.

## What It Does

1. **Polls Stripe** every 5 minutes (configurable) for new successful payments
2. **Extracts order data** including:
   - Customer email
   - Shipping address (name, address, city, state, zip, country, phone)
   - Size (from metadata)
   - Phrase (from metadata) - the custom text for the shirt graphic
3. **Persists orders** to local filesystem under `orders/<payment_intent_id>/order.json`
4. **Tracks sync state** to avoid re-processing orders

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp env.example .env
# Edit .env with your Stripe secret key
```

### 3. Run

```bash
python main.py
```

The worker will start polling immediately and expose an API on port 8002.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/status` | GET | Worker status and sync state |
| `/sync` | POST | Manually trigger a sync |
| `/orders` | GET | List all locally stored orders |
| `/orders/{id}` | GET | Get a specific order |

## Docker

```bash
docker build -t cheeseshirt-worker-stripe .
docker run -e STRIPE_SECRET_KEY=sk_xxx -v ./data/orders:/app/data/orders cheeseshirt-worker-stripe
```

## Order Data Structure

Each order is stored as JSON:

```json
{
  "id": "pi_abc123",
  "amount": 3500,
  "currency": "usd",
  "status": "succeeded",
  "created_at": "2024-01-15T10:30:00",
  "email": "customer@example.com",
  "shipping": {
    "name": "John Doe",
    "phone": "+15551234567",
    "line1": "123 Main St",
    "line2": "Apt 4",
    "city": "Portland",
    "state": "OR",
    "postal_code": "97201",
    "country": "US"
  },
  "phrase": "the cheese stands alone",
  "size": "L",
  "session_id": "abc123-session-id"
}
```

## Integration with Other Workers

The order data persisted by this worker can be consumed by other workers for:

- **Graphic generation** - Using the `phrase` field
- **Email notifications** - Using the `email` field
- **Fulfillment** - Using shipping address and size
- **Analytics** - Order totals, popular sizes, etc.

