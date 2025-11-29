# cheeseshirt web
# Static files served by nginx

FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY index.html ./
COPY tsconfig.json ./
COPY vite.config.ts ./
COPY src ./src
COPY public ./public

# Build static files
RUN npm run build

# Production stage - nginx unprivileged
FROM nginxinc/nginx-unprivileged:alpine

# Copy built static files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Switch to root to set up user and permissions
USER root

# Create user with UID 1002 to match host cheeseshirt user
RUN deluser nginx && \
    addgroup -g 1002 cheeseshirt && \
    adduser -u 1002 -G cheeseshirt -s /bin/sh -D cheeseshirt && \
    mkdir -p /app/logs && \
    chown -R cheeseshirt:cheeseshirt /usr/share/nginx/html && \
    chown -R cheeseshirt:cheeseshirt /var/cache/nginx && \
    chown -R cheeseshirt:cheeseshirt /var/log/nginx && \
    chown -R cheeseshirt:cheeseshirt /app/logs && \
    chown -R cheeseshirt:cheeseshirt /etc/nginx && \
    touch /tmp/nginx.pid && \
    chown cheeseshirt:cheeseshirt /tmp/nginx.pid

USER cheeseshirt

# nginx-unprivileged uses port 8080 by default
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
