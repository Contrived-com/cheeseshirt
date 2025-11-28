import Stripe from 'stripe';
import { config } from './config.js';
import { logger } from './logger.js';

// Initialize Stripe client
const stripe = new Stripe(config.stripeSecretKey, {
  apiVersion: '2025-11-17.clover',
});

export interface CreatePaymentIntentInput {
  sessionId: string;
  size: string;
  phrase: string;
  email: string;
  customerName: string;
}

export interface PaymentIntentResponse {
  clientSecret: string;
  paymentIntentId: string;
  amount: number;
  currency: string;
}

/**
 * Create a PaymentIntent for a shirt purchase.
 * 
 * At this stage, we only have the size and phrase.
 * Shipping address and full customer details are collected
 * via Stripe Elements on the frontend.
 */
export async function createPaymentIntent(input: CreatePaymentIntentInput): Promise<PaymentIntentResponse> {
  const { sessionId, size, phrase, email, customerName } = input;
  
  logger.info('Creating PaymentIntent', {
    sessionId: sessionId.substring(0, 8) + '...',
    size,
    phraseLength: phrase.length,
  });
  
  try {
    // Create the PaymentIntent with automatic tax calculation
    const paymentIntent = await stripe.paymentIntents.create({
      amount: config.shirtPriceCents,
      currency: 'usd',
      
      // Metadata - this is what the worker will retrieve
      metadata: {
        session_id: sessionId,
        phrase: phrase,  // Up to 500 chars
        size: size,
        source: 'monger-terminal',
      },
      
      // Receipt email
      receipt_email: email,
      
      // Enable automatic payment methods (cards, Apple Pay, Google Pay, etc)
      automatic_payment_methods: {
        enabled: true,
      },
      
      // Description shown on bank statements
      statement_descriptor_suffix: 'CHEESESHIRT',
      
      // Description for Stripe dashboard
      description: `Cheeseshirt - Size ${size.toUpperCase()}`,
    });
    
    logger.info('PaymentIntent created', {
      paymentIntentId: paymentIntent.id,
      amount: paymentIntent.amount,
      status: paymentIntent.status,
    });
    
    return {
      clientSecret: paymentIntent.client_secret!,
      paymentIntentId: paymentIntent.id,
      amount: paymentIntent.amount,
      currency: paymentIntent.currency,
    };
    
  } catch (error) {
    logger.error('Failed to create PaymentIntent', {
      error: error instanceof Error ? error.message : String(error),
      sessionId: sessionId.substring(0, 8) + '...',
    });
    throw error;
  }
}

/**
 * Update a PaymentIntent with shipping address.
 * Called after the user fills in the Address Element.
 */
export async function updatePaymentIntentShipping(
  paymentIntentId: string,
  shipping: Stripe.PaymentIntentUpdateParams.Shipping
): Promise<void> {
  logger.info('Updating PaymentIntent with shipping', {
    paymentIntentId,
    shippingName: shipping.name,
  });
  
  try {
    await stripe.paymentIntents.update(paymentIntentId, {
      shipping,
    });
    
    logger.info('PaymentIntent shipping updated', { paymentIntentId });
    
  } catch (error) {
    logger.error('Failed to update PaymentIntent shipping', {
      error: error instanceof Error ? error.message : String(error),
      paymentIntentId,
    });
    throw error;
  }
}

/**
 * Verify a Stripe webhook signature.
 */
export function verifyWebhookSignature(
  payload: string | Buffer,
  signature: string
): Stripe.Event {
  return stripe.webhooks.constructEvent(
    payload,
    signature,
    config.stripeWebhookSecret
  );
}

/**
 * Retrieve a PaymentIntent by ID (for verification).
 */
export async function getPaymentIntent(paymentIntentId: string): Promise<Stripe.PaymentIntent> {
  return stripe.paymentIntents.retrieve(paymentIntentId);
}

/**
 * Get the publishable key for frontend use.
 */
export function getPublishableKey(): string {
  return config.stripePublishableKey;
}

/**
 * Test Stripe connection.
 */
export async function testStripeConnection(): Promise<{ ok: boolean; error?: string }> {
  try {
    // Try to retrieve account info
    const balance = await stripe.balance.retrieve();
    logger.info('Stripe connection test successful', {
      available: balance.available.length,
      pending: balance.pending.length,
    });
    return { ok: true };
  } catch (error) {
    logger.error('Stripe connection test failed', {
      error: error instanceof Error ? error.message : String(error),
    });
    return {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

