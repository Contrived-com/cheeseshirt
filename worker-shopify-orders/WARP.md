# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Commands

- Install dependencies:
  - pip install -r requirements.txt
- Configure environment:
  - cp env.example .env
- Run the API server:
  - python main.py
  - or: python run.py
- Run in dev (auto-reload, uses HOST/PORT from environment):
  - uvicorn main:app --reload --host $env:HOST --port $env:PORT
- API docs once running:
  - http://localhost:8000/docs
- Lint: not configured
- Tests: not configured

## Architecture overview

- Application entrypoint: main.py defines a FastAPI app and wires together services. Endpoints cover: orders retrieval, single-order fetch, order processing (with optional background email), processed-orders listing, email utilities, OpenAI-assisted analysis/summary, SMS sending, config/status and health.
- Configuration: config.py loads settings via python-dotenv into a Config object (Shopify, SMTP, OpenAI, Stripe, Twilio, app host/port, etc.) and exposes convenience flags (is_openai_configured, is_stripe_configured, is_twilio_configured, is_aws_configured) plus a validation helper for required fields.
- Data models: models.py contains Pydantic models for Order, LineItem, ProcessedOrder, and EmailRequest used across the app and for response models.
- Shopify integration: shopify_client.py calls the Shopify GraphQL Admin API (requests), translates responses into Order/LineItem models, and normalizes IDs. Order IDs missing the gid://shopify/Order/ prefix are fixed at the API layer.
- Order processing and persistence: order_processor.py generates human-readable processing notes and a JSON order summary; it persists outputs under attachments/ and processed_orders/ (created on demand). Processed orders can be re-hydrated from JSON for the /processed-orders endpoint.
- Email delivery: email_service.py composes plaintext MIME emails, attaches the generated JSON summary when present, and sends via SMTP using credentials from Config. BackgroundTasks in main.py update persisted state after successful sends.
- External APIs: external_apis.py optionally initializes clients based on configuration and provides helpers to:
  - OpenAI: chat completions for analysis and professional summaries
  - Stripe: basic payment intent operations
  - Twilio: SMS sending and simple notifications
  It also exposes /api-status and a consolidated /test-apis check.

## Operational notes

- Background work: Email sending is dispatched via FastAPI BackgroundTasks to avoid blocking request handling; successful sends update the saved processed order record.
- Filesystem expectations: attachments/ and processed_orders/ are relative to the repo root and are created at runtime; ensure the process has write access.
- API documentation: Interactive docs are provided by FastAPI at /docs and /redoc when the server is running.
