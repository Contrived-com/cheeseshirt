# cheeseshirt

the monger's underground operation.

## structure

```
cheeseshirt/
├── api/                    # backend - node.js api server
├── web/                    # frontend - terminal interface
├── worker-shopify-orders/  # background worker - order processing
├── docker-compose.yml      # container orchestration
└── .gitignore
```

## quick start (docker)

1. set environment variables:
```bash
export OPENAI_API_KEY=your-openai-key
export SHOPIFY_STORE_URL=your-store.myshopify.com
export SHOPIFY_ACCESS_TOKEN=your-shopify-token
```

2. run:
```bash
docker compose up -d
```

3. visit http://localhost

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

## deployment

### build images

```bash
# api
docker build -t cheeseshirt-api ./api

# web
docker build -t cheeseshirt-web ./web
```

### environment variables

| variable | required | description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | yes | openai api key for monger responses |
| `OPENAI_MODEL` | no | model to use (default: gpt-4o) |
| `SHOPIFY_STORE_URL` | yes | your-store.myshopify.com |
| `SHOPIFY_ACCESS_TOKEN` | yes | shopify admin api token |
| `SHOPIFY_API_VERSION` | no | api version (default: 2024-01) |
| `COOKIE_SECURE` | no | set true for https (default: false) |
| `TIME_WASTER_THRESHOLD_HOURS` | no | hours before time-waster flag clears (default: 24) |

### production with nginx (non-docker)

if running directly on a server:

1. build web: `cd web && npm run build`
2. serve `web/dist/` with nginx
3. proxy `/api` to the api server on port 3001
4. run api: `cd api && npm run build && npm start`

see `web/README.md` for nginx config example.

## architecture

- **stateless containers** - no persistent storage in containers
- **ephemeral sessions** - stored in sqlite (in-container, lost on restart)
- **state of truth** - shopify + worker-shopify-orders handles order state
- **api** talks to openai for monger responses, shopify for checkout
- **web** serves static files, proxies api calls

## the monger

he sells shirts.  one style.  white on green.  your phrase becomes the graphic.  you don't see it until it arrives.  that's the deal.

keep your voice low.  the signal jumps here.

