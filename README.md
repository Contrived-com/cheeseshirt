# cheeseshirt

the monger's underground operation.

## structure

```
cheeseshirt/
├── api/                     # backend - node.js api server
├── web/                     # frontend - terminal interface
├── worker-stripe-orders/    # background worker - stripe order sync
├── monger/                  # monger character config
├── docker-compose.yml       # container orchestration
└── .gitignore
```

## quick start (docker)

1. set environment variables:
```bash
export OPENAI_API_KEY=your-openai-key
export STRIPE_SECRET_KEY=sk_live_xxx
export STRIPE_PUBLISHABLE_KEY=pk_live_xxx
export STRIPE_WEBHOOK_SECRET=whsec_xxx
```

2. run:
```bash
docker compose up -d --build
```

3. visit http://localhost:8080

## quick start (development)

```bash
# terminal 1 - api
cd api
npm install
cp env.example .env  # edit with your secrets
npm run dev

# terminal 2 - web
cd web
npm install
npm run dev
```

visit http://localhost:3000

## ci/cd

images are automatically built and pushed to GHCR on push to main:

- `ghcr.io/contrived-com/cheeseshirt-api:latest`
- `ghcr.io/contrived-com/cheeseshirt-web:latest`

tags created:
- `latest` - current main branch
- `main` - branch name
- `abc1234` - commit SHA

## deployment

### option 1: build locally

```bash
docker compose up -d --build
```

### build images manually

```bash
# api
docker build -t cheeseshirt-api ./api

# web
docker build -t cheeseshirt-web ./web

# worker
docker build -t cheeseshirt-worker-stripe ./worker-stripe-orders
```

### environment variables

| variable | required | description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | yes | openai api key for monger responses |
| `OPENAI_MODEL` | no | model to use (default: gpt-4o) |
| `STRIPE_SECRET_KEY` | yes | stripe secret key (sk_live_xxx or sk_test_xxx) |
| `STRIPE_PUBLISHABLE_KEY` | yes | stripe publishable key (pk_live_xxx or pk_test_xxx) |
| `STRIPE_WEBHOOK_SECRET` | no | stripe webhook signing secret (whsec_xxx) |
| `SHIRT_PRICE_CENTS` | no | price in cents (default: 3500 = $35.00) |
| `COOKIE_SECURE` | no | set true for https (default: false) |
| `TIME_WASTER_THRESHOLD_HOURS` | no | hours before time-waster flag clears (default: 24) |
| `POLL_INTERVAL_SECONDS` | no | how often worker syncs orders (default: 300) |

### production with nginx (non-docker)

if running directly on a server:

1. build web: `cd web && npm run build`
2. serve `web/dist/` with nginx
3. proxy `/api` to the api server on port 3001
4. run api: `cd api && npm run build && npm start`

see `web/README.md` for nginx config example.

## architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              CHEESESHIRT                                    │
│                                                                             │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐       │
│  │     WEB      │         │     API      │         │    STRIPE    │       │
│  │   Terminal   │◀───────▶│   Server     │◀───────▶│              │       │
│  │              │         │              │         │  Holds:      │       │
│  │ - Chat UI    │         │ - Chat/Monger│         │  - Payment   │       │
│  │ - Stripe     │         │ - Payment    │         │  - Shipping  │       │
│  │   Elements   │         │   Intent     │         │  - Metadata  │       │
│  │ - Address    │         │ - Webhook    │         │    (phrase,  │       │
│  │   Form       │         │              │         │     size)    │       │
│  └──────────────┘         └──────────────┘         └──────────────┘       │
│                                                            │               │
│                                                            │               │
│                           ┌──────────────┐                 │               │
│                           │   WORKER     │◀────────────────┘               │
│                           │              │    polls every 5 min            │
│                           │ - Sync       │                                 │
│                           │   orders     │                                 │
│                           │ - Persist    │                                 │
│                           │   locally    │                                 │
│                           └──────────────┘                                 │
└────────────────────────────────────────────────────────────────────────────┘
```

- **stateless web** - stripe holds order data, worker syncs it
- **embedded checkout** - payment happens in the terminal, no redirect
- **stripe as database** - orders, addresses, metadata all stored in stripe
- **worker syncs orders** - polls stripe, persists to local filesystem

## the monger

he sells shirts.  one style.  white on green.  your phrase becomes the graphic.  you don't see it until it arrives.  that's the deal.

keep your voice low.  the signal jumps here.

