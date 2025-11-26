# Docker Deployment Guide

## Building the Container

Build the Docker image:

```bash
docker build -t worker-shopify-orders:latest .
```

## Running the Container

### Basic Run (with environment file)

```bash
docker run -d \
  --name worker-shopify-orders \
  -p 80:80 \
  --env-file .env \
  worker-shopify-orders:latest
```

### Run with Volume Mount (for persistent state)

```bash
docker run -d \
  --name worker-shopify-orders \
  -p 80:80 \
  --env-file .env \
  -v $(pwd)/state:/app/state \
  worker-shopify-orders:latest
```

### Run with Individual Environment Variables

```bash
docker run -d \
  --name worker-shopify-orders \
  -p 80:80 \
  -e SHOPIFY_STORE_URL=your-store.myshopify.com \
  -e SHOPIFY_ACCESS_TOKEN=your-token \
  -e EMAIL_USERNAME=your-email@gmail.com \
  -e EMAIL_PASSWORD=your-app-password \
  -e PRINTER_EMAIL=printer@example.com \
  worker-shopify-orders:latest
```

## AWS Deployment

### AWS ECS (Elastic Container Service)

1. **Build and tag for ECR:**
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
   docker build -t worker-shopify-orders .
   docker tag worker-shopify-orders:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/worker-shopify-orders:latest
   docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/worker-shopify-orders:latest
   ```

2. **Create ECS Task Definition** with:
   - Container port: 80
   - Environment variables from AWS Secrets Manager or Parameter Store
   - Optional: Mount EFS volume for persistent state

3. **Deploy to ECS** using Fargate or EC2 launch type

### AWS App Runner

1. Push image to ECR (see above)
2. Create App Runner service:
   - Source: Container registry (ECR)
   - Port: 80
   - Add environment variables in App Runner configuration
   - Configure auto-scaling based on requests

### AWS Lightsail Containers

1. Push to AWS Lightsail:
   ```bash
   aws lightsail push-container-image \
     --service-name worker-shopify-orders \
     --label worker-shopify-orders-latest \
     --image worker-shopify-orders:latest
   ```

2. Deploy with Lightsail container service

## Environment Variables

All environment variables from `.env` should be provided at runtime. Key variables:

- `SHOPIFY_STORE_URL` - Your Shopify store URL
- `SHOPIFY_ACCESS_TOKEN` - Shopify API access token
- `EMAIL_USERNAME` - SMTP username
- `EMAIL_PASSWORD` - SMTP password
- `PRINTER_EMAIL` - Printer email address
- `OPENAI_API_KEY` - OpenAI API key (optional)
- `PORT` - Port to run on (defaults to 80)
- `HOST` - Host to bind to (defaults to 0.0.0.0)
- `STATE_DIR` - Base directory for state (defaults to "state")

## Health Check

The container includes a health check on `/health`:

```bash
curl http://localhost/health
```

## Logs

View container logs:

```bash
docker logs worker-shopify-orders
docker logs -f worker-shopify-orders  # Follow logs
```

## Stopping and Removing

```bash
docker stop worker-shopify-orders
docker rm worker-shopify-orders
```

## Development with Docker

For local development with hot-reload:

```bash
docker run -d \
  --name worker-shopify-orders-dev \
  -p 8000:80 \
  --env-file .env \
  -e DEBUG=True \
  -v $(pwd):/app \
  -v $(pwd)/state:/app/state \
  worker-shopify-orders:latest
```

## Docker Compose (Optional)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "80:80"
    env_file:
      - .env
    volumes:
      - ./state:/app/state
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
```

Run with:

```bash
docker-compose up -d
```

## Persistent State

The container creates directories under `/app/state/`:
- `/app/state/processed_orders/` - Processed order records
- `/app/state/attachments/` - Order attachments

For production, consider:
1. **Volume Container**: Mount a Docker volume
2. **AWS EFS**: Use Elastic File System for shared storage
3. **AWS S3**: Modify application to use S3 for file storage (recommended for production)

## Security Best Practices

1. Never bake secrets into the image
2. Use AWS Secrets Manager or Parameter Store for sensitive data
3. Run container with read-only root filesystem where possible
4. Implement rate limiting and authentication at the load balancer level
5. Use AWS WAF for additional protection
6. Keep base image updated regularly

