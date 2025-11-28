#!/usr/bin/env python3
"""
Quick Stripe connection test.
Run: python test-stripe.py
"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Check for required keys
secret_key = os.getenv("STRIPE_SECRET_KEY")
publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY")

print("=" * 50)
print("STRIPE CONNECTION TEST")
print("=" * 50)

if not secret_key:
    print("❌ STRIPE_SECRET_KEY not found in environment")
    exit(1)

if not publishable_key:
    print("❌ STRIPE_PUBLISHABLE_KEY not found in environment")
    exit(1)

print(f"✓ Secret key found: {secret_key[:12]}...{secret_key[-4:]}")
print(f"✓ Publishable key found: {publishable_key[:12]}...{publishable_key[-4:]}")

# Check key types (test vs live)
is_test = "test" in secret_key.lower()
print(f"✓ Mode: {'TEST (sandbox)' if is_test else 'LIVE (real money!)'}")

print()
print("Connecting to Stripe API...")
print()

try:
    import stripe
except ImportError:
    print("❌ stripe package not installed. Run: pip install stripe")
    exit(1)

stripe.api_key = secret_key

# Test 1: Retrieve account balance (verifies API key works)
print("Test 1: Checking API access...")
try:
    balance = stripe.Balance.retrieve()
    print(f"  ✓ Connected! Available balance: {len(balance.available)} currency(ies)")
    for b in balance.available:
        print(f"    - {b.currency.upper()}: {b.amount / 100:.2f}")
except stripe.error.AuthenticationError:
    print("  ❌ Authentication failed - check your STRIPE_SECRET_KEY")
    exit(1)
except stripe.error.StripeError as e:
    print(f"  ❌ Stripe error: {e}")
    exit(1)

# Test 2: List recent payment intents
print()
print("Test 2: Checking PaymentIntent access...")
try:
    payments = stripe.PaymentIntent.list(limit=3)
    print(f"  ✓ Can read PaymentIntents ({len(payments.data)} recent)")
    for pi in payments.data:
        print(f"    - {pi.id}: {pi.status} - ${pi.amount/100:.2f} {pi.currency.upper()}")
except stripe.error.StripeError as e:
    print(f"  ❌ Error: {e}")

# Test 3: Try creating a test PaymentIntent (then cancel it)
print()
print("Test 3: Creating test PaymentIntent...")
try:
    test_pi = stripe.PaymentIntent.create(
        amount=100,  # $1.00
        currency="usd",
        metadata={
            "test": "true",
            "source": "cheeseshirt-connection-test"
        },
        automatic_payment_methods={"enabled": True},
    )
    print(f"  ✓ Created: {test_pi.id}")
    print(f"    Status: {test_pi.status}")
    print(f"    Client secret: {test_pi.client_secret[:20]}...")
    
    # Cancel it since this is just a test
    cancelled = stripe.PaymentIntent.cancel(test_pi.id)
    print(f"  ✓ Cancelled test PaymentIntent")
except stripe.error.StripeError as e:
    print(f"  ❌ Error: {e}")

print()
print("=" * 50)
print("✅ ALL TESTS PASSED - Stripe is ready to rock!")
print("=" * 50)

