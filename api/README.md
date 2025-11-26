# cheeseshirt api

the monger's backend.  handles sessions, conversations, and checkout creation.

## setup

```bash
cd api
npm install
cp env.example .env  # then edit with your secrets
```

## docker

build:
```bash
docker build -t cheeseshirt-api .
```

run:
```bash
docker run -d \
  -p 3001:3001 \
  -e OPENAI_API_KEY=your-key \
  -e SHOPIFY_STORE_URL=your-store.myshopify.com \
  -e SHOPIFY_ACCESS_TOKEN=your-token \
  cheeseshirt-api
```

### required environment variables

- `OPENAI_API_KEY` - for the monger's voice
- `SHOPIFY_STORE_URL` - your shopify store
- `SHOPIFY_ACCESS_TOKEN` - shopify admin api token

### optional shopify variant ids

set these to map sizes to your product variants:

```
SHOPIFY_VARIANT_S=your-small-variant-id
SHOPIFY_VARIANT_M=your-medium-variant-id
SHOPIFY_VARIANT_L=your-large-variant-id
SHOPIFY_VARIANT_XL=your-xl-variant-id
SHOPIFY_VARIANT_XXL=your-xxl-variant-id
```

## run

development:
```bash
npm run dev
```

production:
```bash
npm run build
npm start
```

## endpoints

| method | path | description |
|--------|------|-------------|
| POST | /api/session/init | initialize a session |
| POST | /api/chat | send a message to the monger |
| POST | /api/referral-lookup | look up a referrer |
| POST | /api/create-checkout | create shopify checkout |
| GET | /api/profile | get customer profile |
| GET | /api/session/:id | get session info |
| GET | /api/health | health check |

## data

sqlite database stored at `./data/cheeseshirt.db` by default.

tables:
- `customers` - tracks buyers, purchase counts, time-waster flags
- `sessions` - conversation sessions with collected data
- `messages` - chat history
- `referrals` - referrer lookup for discounts

