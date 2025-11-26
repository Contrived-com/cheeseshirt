# Use Python 3.11 on Debian Bookworm (stable, suitable for AWS)
FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies
# - curl for health checks
# - ca-certificates for SSL/TLS
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/state/processed_orders /app/state/attachments && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port 80
EXPOSE 80

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=80
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]

