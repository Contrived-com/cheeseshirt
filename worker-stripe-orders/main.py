"""
Stripe Orders Worker

Polls Stripe for successful payments and persists order data locally.
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from config import get_config, Config
from stripe_client import StripeClient
from models import Order, OrderSyncState


# Global state
config: Config = get_config()
stripe_client: StripeClient = StripeClient(config)
sync_state: OrderSyncState = OrderSyncState()
sync_task: Optional[asyncio.Task] = None


def get_state_file_path() -> Path:
    """Get path to the sync state file."""
    state_dir = Path(config.STATE_DIR)
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "sync_state.json"


def get_orders_dir() -> Path:
    """Get path to the orders directory."""
    orders_dir = Path(config.ORDERS_DIR)
    orders_dir.mkdir(parents=True, exist_ok=True)
    return orders_dir


def load_sync_state() -> OrderSyncState:
    """Load sync state from disk."""
    state_file = get_state_file_path()
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text())
            return OrderSyncState(**data)
        except Exception as e:
            print(f"Error loading sync state: {e}")
    return OrderSyncState()


def save_sync_state(state: OrderSyncState):
    """Save sync state to disk."""
    state_file = get_state_file_path()
    state_file.write_text(state.model_dump_json(indent=2))


def save_order(order: Order) -> Path:
    """
    Save an order to disk.
    
    Creates: Orders/<payment_intent_id>/order.json
    
    Returns the path to the saved file.
    """
    order_dir = get_orders_dir() / order.id
    order_dir.mkdir(parents=True, exist_ok=True)
    
    order_file = order_dir / "order.json"
    order_file.write_text(order.model_dump_json(indent=2, default=str))
    
    return order_file


def get_local_orders() -> List[str]:
    """Get list of order IDs we have locally."""
    orders_dir = get_orders_dir()
    if not orders_dir.exists():
        return []
    
    return [d.name for d in orders_dir.iterdir() if d.is_dir()]


async def sync_orders() -> dict:
    """
    Sync orders from Stripe.
    
    Returns sync result summary.
    """
    global sync_state
    
    # Get orders created after last sync (or last 24 hours if never synced)
    created_after = sync_state.last_sync_at
    if not created_after:
        created_after = datetime.now() - timedelta(days=7)  # Initial sync: last 7 days
    
    print(f"Syncing orders created after {created_after}")
    
    # Fetch from Stripe
    orders = stripe_client.get_succeeded_payments(created_after=created_after)
    
    # Get existing order IDs
    existing_ids = set(get_local_orders())
    
    # Save new orders
    new_orders = []
    for order in orders:
        if order.id not in existing_ids:
            save_order(order)
            new_orders.append(order.id)
            print(f"Saved new order: {order.id} - {order.size} - {order.phrase[:30]}...")
    
    # Update sync state
    sync_state.last_sync_at = datetime.now()
    if orders:
        sync_state.last_payment_intent_id = orders[0].id
    sync_state.total_orders_synced += len(new_orders)
    save_sync_state(sync_state)
    
    return {
        "synced_at": sync_state.last_sync_at.isoformat(),
        "orders_fetched": len(orders),
        "new_orders_saved": len(new_orders),
        "new_order_ids": new_orders,
        "total_orders_synced": sync_state.total_orders_synced,
    }


async def poll_loop():
    """Background task that polls Stripe periodically."""
    while True:
        try:
            result = await sync_orders()
            print(f"Sync complete: {result['new_orders_saved']} new orders")
        except Exception as e:
            print(f"Sync error: {e}")
        
        await asyncio.sleep(config.POLL_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global sync_state, sync_task
    
    # Load state on startup
    sync_state = load_sync_state()
    print(f"Loaded sync state: {sync_state.total_orders_synced} orders synced previously")
    
    # Start background polling
    sync_task = asyncio.create_task(poll_loop())
    print(f"Started polling every {config.POLL_INTERVAL_SECONDS} seconds")
    
    yield
    
    # Cleanup on shutdown
    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
    
    save_sync_state(sync_state)
    print("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Cheeseshirt Stripe Orders Worker",
    description="Polls Stripe for orders and persists them locally",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================
# API Endpoints
# ============================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/status")
async def status():
    """Get worker status and sync state."""
    stripe_ok = stripe_client.test_connection()
    local_orders = get_local_orders()
    
    return {
        "stripe_connected": stripe_ok,
        "poll_interval_seconds": config.POLL_INTERVAL_SECONDS,
        "last_sync_at": sync_state.last_sync_at.isoformat() if sync_state.last_sync_at else None,
        "total_orders_synced": sync_state.total_orders_synced,
        "local_orders_count": len(local_orders),
    }


@app.post("/sync")
async def trigger_sync():
    """Manually trigger a sync."""
    result = await sync_orders()
    return result


@app.get("/orders")
async def list_orders(limit: int = 50):
    """List locally stored orders."""
    orders_dir = get_orders_dir()
    
    orders = []
    for order_dir in sorted(orders_dir.iterdir(), reverse=True)[:limit]:
        if order_dir.is_dir():
            order_file = order_dir / "order.json"
            if order_file.exists():
                try:
                    order_data = json.loads(order_file.read_text())
                    orders.append(order_data)
                except Exception as e:
                    print(f"Error reading {order_file}: {e}")
    
    return {
        "count": len(orders),
        "orders": orders,
    }


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get a specific order by ID."""
    order_file = get_orders_dir() / order_id / "order.json"
    
    if not order_file.exists():
        raise HTTPException(status_code=404, detail="Order not found")
    
    try:
        return json.loads(order_file.read_text())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading order: {e}")


# ============================================
# Run Server
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower(),
    )

