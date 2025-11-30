import { createServer, IncomingMessage, ServerResponse } from 'http';
import type { Socket } from 'net';
import { v4 as uuidv4 } from 'uuid';
import { config, validateConfig } from './config.js';
import { logger } from './logger.js';
import {
  createSession,
  getSession,
  updateSession,
  addMessage as addSessionMessage,
  getMessages,
  clearMessages,
  getSessionCount,
  Session,
} from './sessions.js';
import {
  logSessionStart,
  logMessage,
  logSessionEnd,
  logPurchase,
} from './conversations.js';
import { 
  getMongerReply, 
  getOpeningLine, 
  getOpeningLineAsync, 
  getReferralResponseLine, 
  getReferralResponseLineAsync, 
  MongerResponse, 
  testMongerServiceConnection,
  shouldEnterDiagnostic,
  shouldExitDiagnostic,
  getDiagnosticReply,
  getDiagnosticEntryMessage,
  getDiagnosticExitMessage,
} from './monger.js';
import * as mongerClient from './monger-client.js';
import { 
  createPaymentIntent, 
  updatePaymentIntentShipping,
  verifyWebhookSignature,
  getPublishableKey,
  testStripeConnection
} from './stripe.js';

// Initialize logger before anything else
logger.init(config.logPath || undefined, config.logLevel);

// Global error handlers - catch crashes and log before exit
process.on('uncaughtException', (error: Error) => {
  logger.error('FATAL: Uncaught Exception', {
    name: error.name,
    message: error.message,
    stack: error.stack,
  });
  // Give the logger time to write, then exit
  setTimeout(() => process.exit(1), 100);
});

process.on('unhandledRejection', (reason: unknown, promise: Promise<unknown>) => {
  logger.error('FATAL: Unhandled Promise Rejection', {
    reason: reason instanceof Error 
      ? { name: reason.name, message: reason.message, stack: reason.stack }
      : String(reason),
  });
  // Give the logger time to write, then exit
  setTimeout(() => process.exit(1), 100);
});

process.on('SIGTERM', () => {
  logger.info('Received SIGTERM, shutting down gracefully');
  setTimeout(() => process.exit(0), 100);
});

process.on('SIGINT', () => {
  logger.info('Received SIGINT, shutting down gracefully');
  setTimeout(() => process.exit(0), 100);
});

logger.info('Process handlers registered', { pid: process.pid });

validateConfig();

// CORS headers for cross-origin requests
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Cookie',
  'Access-Control-Allow-Credentials': 'true',
};

// Parse JSON body from request
async function parseBody<T>(req: IncomingMessage): Promise<T> {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {} as T);
      } catch (e) {
        reject(new Error('Invalid JSON'));
      }
    });
    req.on('error', reject);
  });
}

// Parse raw body from request (for webhook verification)
async function parseRawBody(req: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on('data', chunk => chunks.push(chunk));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

// Send JSON response
function sendJson(res: ServerResponse, data: unknown, status = 200) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    ...CORS_HEADERS
  });
  res.end(JSON.stringify(data));
}

// Send error response
function sendError(res: ServerResponse, message: string, status = 400) {
  sendJson(res, { error: message }, status);
}

// Customer state stored in cookie
interface CustomerState {
  id: string;
  shirtsBought: number;
  lastPurchase: string | null;
  blockedUntil: string | null;
}

// Parse cookie from request
function parseCookies(req: IncomingMessage): Record<string, string> {
  const cookies: Record<string, string> = {};
  const cookieHeader = req.headers.cookie;
  
  if (cookieHeader) {
    cookieHeader.split(';').forEach(cookie => {
      const [name, value] = cookie.trim().split('=');
      if (name && value) {
        cookies[name] = decodeURIComponent(value);
      }
    });
  }
  
  return cookies;
}

// Parse customer state from cookie
function parseCustomerState(cookies: Record<string, string>): CustomerState | null {
  const stateCookie = cookies['cheeseshirt_customer'];
  if (!stateCookie) return null;
  
  try {
    return JSON.parse(stateCookie) as CustomerState;
  } catch {
    return null;
  }
}

// Get or create customer state
function getOrCreateCustomerState(cookies: Record<string, string>): CustomerState {
  const existing = parseCustomerState(cookies);
  if (existing && existing.id) return existing;
  
  return {
    id: uuidv4(),
    shirtsBought: 0,
    lastPurchase: null,
    blockedUntil: null,
  };
}

// Check if customer is currently blocked (time-waster)
function isCustomerBlocked(customer: CustomerState): boolean {
  if (!customer.blockedUntil) return false;
  return new Date(customer.blockedUntil) > new Date();
}

// Set cookie in response
function setCookie(res: ServerResponse, name: string, value: string, maxAgeDays = 365) {
  const maxAge = maxAgeDays * 24 * 60 * 60;
  const secure = config.cookieSecure ? '; Secure' : '';
  const sameSite = config.cookieSecure ? '; SameSite=None' : '; SameSite=Lax';
  
  res.setHeader('Set-Cookie', 
    `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; HttpOnly${secure}${sameSite}`
  );
}

// Set customer state cookie
function setCustomerStateCookie(res: ServerResponse, customer: CustomerState) {
  setCookie(res, 'cheeseshirt_customer', JSON.stringify(customer));
}

// API Handlers

interface SessionInitRequest {
  // Frontend can pass customer state if cookie wasn't readable
  customerState?: CustomerState;
}

interface SessionInitResponse {
  sessionId: string;
  customerId: string;
  mongerOpeningLine: string;
  isRecentTimeWaster: boolean;
  isRepeatCustomer: boolean;
  recentOrdersCount: number;
  customerState: CustomerState;
}

async function handleSessionInit(req: IncomingMessage, res: ServerResponse) {
  const body = await parseBody<SessionInitRequest>(req);
  const cookies = parseCookies(req);
  
  // Get or create customer state from cookie (or body fallback)
  let customer = body.customerState || getOrCreateCustomerState(cookies);
  const isNewCustomer = customer.shirtsBought === 0 && !customer.lastPurchase;
  
  // Check if blocked (time-waster)
  const isBlocked = isCustomerBlocked(customer);
  
  // Create new session
  const sessionId = uuidv4();
  createSession(sessionId, customer.id);
  
  // Log conversation start to file
  logSessionStart(customer.id, sessionId);
  
  logger.session('init', sessionId, customer.id, { 
    isNewCustomer, 
    isBlocked,
    shirtsBought: customer.shirtsBought,
  });
  
  // Get opening line (try async first, fallback to sync)
  let openingLine: string;
  const customerForMonger = {
    id: customer.id,
    total_shirts_bought: customer.shirtsBought,
    last_purchase_at: customer.lastPurchase,
    is_blocked: isBlocked,
    blocked_until: customer.blockedUntil,
  };
  
  try {
    openingLine = await getOpeningLineAsync(customerForMonger, isBlocked);
  } catch (error) {
    // Fallback to sync version if service is unavailable
    openingLine = getOpeningLine(customerForMonger, isBlocked);
  }
  
  // Store opening line as first assistant message
  if (!isBlocked) {
    addSessionMessage(sessionId, 'assistant', openingLine);
    logMessage(customer.id, sessionId, 'assistant', openingLine);
  }
  
  // Update customer state cookie
  setCustomerStateCookie(res, customer);
  
  const response: SessionInitResponse = {
    sessionId,
    customerId: customer.id,
    mongerOpeningLine: openingLine,
    isRecentTimeWaster: isBlocked,
    isRepeatCustomer: customer.shirtsBought > 0,
    recentOrdersCount: customer.shirtsBought,
    customerState: customer,
  };
  
  sendJson(res, response);
}

interface ChatRequest {
  sessionId: string;
  userInput: string;
}

interface CheckoutShipping {
  name: string | null;
  line1: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  country: string;
}

interface CheckoutState {
  shipping: CheckoutShipping;
  email: string | null;
}

interface UIHints {
  skipTypewriter: boolean;
  showPaymentForm: boolean;
  blocked: boolean;
  inputDisabled: boolean;
}

interface ChatResponse {
  mongerReply: string;
  conversationState: string;
  needsSize: boolean;
  needsPhrase: boolean;
  needsAffirmation: boolean;
  pendingConfirmation: boolean;
  readyForCheckout: boolean;
  readyForPayment: boolean;
  wantsReferralCheck: string | null;
  mood: string;
  collectedSize: string | null;
  collectedPhrase: string | null;
  checkout: CheckoutState;
  uiHints: UIHints;
}

async function handleChat(req: IncomingMessage, res: ServerResponse) {
  const body = await parseBody<ChatRequest>(req);
  const cookies = parseCookies(req);
  
  if (!body.sessionId || !body.userInput) {
    logger.warn('Chat: missing required fields', { hasSessionId: !!body.sessionId, hasUserInput: !!body.userInput });
    return sendError(res, 'Missing sessionId or userInput');
  }
  
  const session = getSession(body.sessionId);
  if (!session) {
    logger.warn('Chat: invalid session', { sessionId: body.sessionId.substring(0, 8) + '...' });
    return sendError(res, 'Invalid session', 404);
  }
  
  // Get customer state from cookie
  const customer = getOrCreateCustomerState(cookies);
  const inDiagnosticMode = session.diagnosticMode;
  
  logger.debug('Chat: processing', { 
    sessionId: body.sessionId.substring(0, 8) + '...', 
    inputLength: body.userInput.length,
    userInputPreview: body.userInput.substring(0, 50),
    diagnosticMode: inDiagnosticMode
  });
  
  // Check for diagnostic mode entry/exit
  if (!inDiagnosticMode && shouldEnterDiagnostic(body.userInput)) {
    logger.info('Chat: entering diagnostic mode', { sessionId: body.sessionId.substring(0, 8) + '...' });
    updateSession(body.sessionId, {
      conversationState: 'diagnostic',
      diagnosticMode: true,
    });
    
    return sendJson(res, {
      mongerReply: getDiagnosticEntryMessage(),
      conversationState: 'diagnostic',
      needsSize: !session.collectedSize,
      needsPhrase: !session.collectedPhrase,
      needsAffirmation: !session.collectedAffirmation,
      readyForCheckout: false,
      readyForPayment: false,
      wantsReferralCheck: null,
      mood: 'neutral',
      collectedSize: session.collectedSize,
      collectedPhrase: session.collectedPhrase,
      checkout: session.checkoutState,
      uiHints: { skipTypewriter: true, showPaymentForm: false, blocked: false, inputDisabled: false },
      diagnosticMode: true,
    });
  }
  
  if (inDiagnosticMode && shouldExitDiagnostic(body.userInput)) {
    logger.info('Chat: exiting diagnostic mode', { sessionId: body.sessionId.substring(0, 8) + '...' });
    
    // Clear conversation history to avoid confusing the LLM with diagnostic context
    clearMessages(body.sessionId);
    logger.debug('Chat: cleared session messages for clean exit from diagnostic mode');
    
    updateSession(body.sessionId, {
      conversationState: 'conversation',
      diagnosticMode: false,
    });
    
    return sendJson(res, {
      mongerReply: getDiagnosticExitMessage(),
      conversationState: 'conversation',
      needsSize: !session.collectedSize,
      needsPhrase: !session.collectedPhrase,
      needsAffirmation: !session.collectedAffirmation,
      readyForCheckout: false,
      readyForPayment: false,
      wantsReferralCheck: null,
      mood: 'neutral',
      collectedSize: session.collectedSize,
      collectedPhrase: session.collectedPhrase,
      checkout: session.checkoutState,
      uiHints: { skipTypewriter: false, showPaymentForm: false, blocked: false, inputDisabled: false },
      diagnosticMode: false,
    });
  }
  
  // Handle diagnostic mode chat
  if (inDiagnosticMode) {
    try {
      const diagnosticResponse = await getDiagnosticReply(body.sessionId, body.userInput);
      
      return sendJson(res, {
        mongerReply: diagnosticResponse.reply,
        conversationState: 'diagnostic',
        needsSize: false,
        needsPhrase: false,
        needsAffirmation: false,
        readyForCheckout: false,
        readyForPayment: false,
        wantsReferralCheck: null,
        mood: 'neutral',
        collectedSize: session.collectedSize,
        collectedPhrase: session.collectedPhrase,
        checkout: session.checkoutState,
        uiHints: { skipTypewriter: true, showPaymentForm: false, blocked: false, inputDisabled: false },
        diagnosticMode: true,
        diagnosticData: diagnosticResponse.diagnosticData,
      });
      
    } catch (error) {
      logger.error('Chat: diagnostic handler error', { 
        sessionId: body.sessionId.substring(0, 8) + '...',
        error: error instanceof Error ? error.message : String(error)
      });
      return sendError(res, 'Diagnostic error', 500);
    }
  }
  
  // Check if customer is blocked (time-waster from cookie)
  if (isCustomerBlocked(customer)) {
    logger.info('Chat: blocked time waster', { customerId: customer.id.substring(0, 8) + '...' });
    return sendJson(res, {
      mongerReply: "you wasted the monger's time.  he'll be back later.",
      conversationState: 'blocked',
      needsSize: false,
      needsPhrase: false,
      needsAffirmation: false,
      readyForCheckout: false,
      readyForPayment: false,
      wantsReferralCheck: null,
      mood: 'suspicious',
      collectedSize: null,
      collectedPhrase: null,
      checkout: {
        shipping: { name: null, line1: null, city: null, state: null, zip: null, country: 'US' },
        email: null
      },
      uiHints: { skipTypewriter: false, showPaymentForm: false, blocked: true, inputDisabled: true }
    });
  }
  
  // Normal character chat
  try {
    // Build customer object for monger (from cookie state)
    const customerForMonger = {
      id: customer.id,
      total_shirts_bought: customer.shirtsBought,
      last_purchase_at: customer.lastPurchase,
      is_blocked: isCustomerBlocked(customer),
      blocked_until: customer.blockedUntil,
    };
    
    const mongerResponse = await getMongerReply(body.sessionId, body.userInput, customerForMonger);
    
    // Log the conversation to file
    logMessage(customer.id, body.sessionId, 'user', body.userInput);
    logMessage(customer.id, body.sessionId, 'assistant', mongerResponse.reply);
    
    logger.debug('Chat: response generated', {
      sessionId: body.sessionId.substring(0, 8) + '...',
      mood: mongerResponse.state.mood,
      readyForCheckout: mongerResponse.state.readyForCheckout,
      hasSize: !!mongerResponse.state.size,
      hasPhrase: !!mongerResponse.state.phrase
    });
    
    // Determine conversation state string
    let convStateStr = 'conversation';
    if (mongerResponse.state.readyForPayment) {
      convStateStr = 'ready_for_payment';
    } else if (mongerResponse.state.readyForCheckout) {
      convStateStr = 'collecting_shipping';
    }
    
    const response: ChatResponse = {
      mongerReply: mongerResponse.reply,
      conversationState: convStateStr,
      needsSize: !mongerResponse.state.size,
      needsPhrase: !mongerResponse.state.phrase,
      needsAffirmation: !mongerResponse.state.hasAffirmation,
      pendingConfirmation: mongerResponse.state.pendingConfirmation,
      readyForCheckout: mongerResponse.state.readyForCheckout,
      readyForPayment: mongerResponse.state.readyForPayment,
      wantsReferralCheck: mongerResponse.state.wantsReferralCheck,
      mood: mongerResponse.state.mood,
      collectedSize: mongerResponse.state.size,
      collectedPhrase: mongerResponse.state.phrase,
      checkout: mongerResponse.state.checkout,
      uiHints: mongerResponse.uiHints,
    };
    
    sendJson(res, response);
    
  } catch (error) {
    logger.error('Chat: handler error', { 
      sessionId: body.sessionId.substring(0, 8) + '...',
      error: error instanceof Error ? { name: error.name, message: error.message, stack: error.stack } : String(error)
    });
    sendError(res, 'Internal error', 500);
  }
}

interface ReferralLookupRequest {
  sessionId: string;
  referrerQuery: string;  // Name, email, or phone
}

interface ReferralLookupResponse {
  found: boolean;
  referrerStatus: 'unknown' | 'buyer' | 'vip' | 'ultra' | 'friend_of';
  discountPercentage: number;
  mongerLine: string;
  referrerName: string | null;
  matchType: string | null;
  connectedThrough: string | null;
}

async function handleReferralLookup(req: IncomingMessage, res: ServerResponse) {
  const body = await parseBody<ReferralLookupRequest>(req);
  
  if (!body.sessionId || !body.referrerQuery) {
    return sendError(res, 'Missing sessionId or referrerQuery');
  }
  
  const session = getSession(body.sessionId);
  if (!session) {
    return sendError(res, 'Invalid session', 404);
  }
  
  logger.debug('Referral lookup', { 
    sessionId: body.sessionId.substring(0, 8) + '...', 
    query: body.referrerQuery.substring(0, 20) + '...' 
  });
  
  try {
    // Query the Monger's referral network
    const lookupResult = await mongerClient.lookupReferral({ query: body.referrerQuery });
    
    // Map tier to status
    let status: 'unknown' | 'buyer' | 'vip' | 'ultra' | 'friend_of' = 'unknown';
    if (lookupResult.found && lookupResult.tier) {
      status = lookupResult.tier as typeof status;
    }
    
    // Update session with referrer info
    if (lookupResult.found) {
      updateSession(body.sessionId, {
        referrerEmail: body.referrerQuery,
        discountCode: lookupResult.discount > 0 ? `REF${lookupResult.discount}` : null,
      });
    }
    
    const response: ReferralLookupResponse = {
      found: lookupResult.found,
      referrerStatus: status,
      discountPercentage: lookupResult.discount,
      mongerLine: lookupResult.monger_line,
      referrerName: lookupResult.name,
      matchType: lookupResult.match_type,
      connectedThrough: lookupResult.connected_through,
    };
    
    logger.info('Referral lookup result', { 
      found: lookupResult.found, 
      tier: status, 
      discount: lookupResult.discount 
    });
    
    sendJson(res, response);
    
  } catch (error) {
    logger.error('Referral lookup failed', { 
      error: error instanceof Error ? error.message : String(error) 
    });
    
    // Fallback response
    const fallbackLine = getReferralResponseLine('unknown', 0);
    sendJson(res, {
      found: false,
      referrerStatus: 'unknown',
      discountPercentage: 0,
      mongerLine: fallbackLine,
      referrerName: null,
      matchType: null,
      connectedThrough: null,
    });
  }
}

// ============================================
// Stripe Payment Handlers
// ============================================

// Get Stripe config for frontend
async function handleStripeConfig(req: IncomingMessage, res: ServerResponse) {
  sendJson(res, {
    publishableKey: getPublishableKey(),
    shirtPriceCents: config.shirtPriceCents,
  });
}

interface CreatePaymentIntentRequest {
  sessionId: string;
  size: string;
  phrase: string;
  email: string;
  customerName: string;
}

// Create a PaymentIntent for embedded checkout
async function handleCreatePaymentIntent(req: IncomingMessage, res: ServerResponse) {
  const body = await parseBody<CreatePaymentIntentRequest>(req);
  
  if (!body.sessionId || !body.size || !body.phrase || !body.email) {
    logger.warn('PaymentIntent: missing required fields', { 
      hasSessionId: !!body.sessionId, 
      hasSize: !!body.size, 
      hasPhrase: !!body.phrase,
      hasEmail: !!body.email
    });
    return sendError(res, 'Missing required fields');
  }
  
  // Validate phrase length
  if (body.phrase.length > 500) {
    return sendError(res, 'Phrase too long (max 500 characters)');
  }
  
  const session = getSession(body.sessionId);
  if (!session) {
    logger.warn('PaymentIntent: invalid session', { sessionId: body.sessionId.substring(0, 8) + '...' });
    return sendError(res, 'Invalid session', 404);
  }
  
  logger.info('PaymentIntent: creating', { 
    sessionId: body.sessionId.substring(0, 8) + '...',
    size: body.size,
    phraseLength: body.phrase.length,
    email: body.email.substring(0, 3) + '***'
  });
  
  try {
    const result = await createPaymentIntent({
      sessionId: body.sessionId,
      size: body.size,
      phrase: body.phrase,
      email: body.email,
      customerName: body.customerName || '',
    });
    
    // Update session state
    updateSession(body.sessionId, {
      conversationState: 'checkout_started',
      collectedSize: body.size,
      collectedPhrase: body.phrase,
      collectedAffirmation: true,
    });
    
    logger.info('PaymentIntent: created successfully', { 
      sessionId: body.sessionId.substring(0, 8) + '...',
      paymentIntentId: result.paymentIntentId,
      amount: result.amount
    });
    
    sendJson(res, {
      clientSecret: result.clientSecret,
      paymentIntentId: result.paymentIntentId,
      amount: result.amount,
      currency: result.currency,
    });
    
  } catch (error) {
    logger.error('PaymentIntent: creation failed', { 
      sessionId: body.sessionId.substring(0, 8) + '...',
      error: error instanceof Error ? error.message : String(error)
    });
    sendError(res, 'Failed to create payment', 500);
  }
}

interface UpdateShippingRequest {
  paymentIntentId: string;
  shipping: {
    name: string;
    phone?: string;
    address: {
      line1: string;
      line2?: string;
      city: string;
      state: string;
      postal_code: string;
      country: string;
    };
  };
}

// Update PaymentIntent with shipping address
async function handleUpdateShipping(req: IncomingMessage, res: ServerResponse) {
  const body = await parseBody<UpdateShippingRequest>(req);
  
  if (!body.paymentIntentId || !body.shipping || !body.shipping.address) {
    return sendError(res, 'Missing paymentIntentId or shipping address');
  }
  
  try {
    await updatePaymentIntentShipping(body.paymentIntentId, body.shipping);
    sendJson(res, { success: true });
  } catch (error) {
    logger.error('UpdateShipping: failed', { 
      paymentIntentId: body.paymentIntentId,
      error: error instanceof Error ? error.message : String(error)
    });
    sendError(res, 'Failed to update shipping', 500);
  }
}

// Handle Stripe webhook events
async function handleStripeWebhook(req: IncomingMessage, res: ServerResponse) {
  const signature = req.headers['stripe-signature'] as string;
  
  if (!signature) {
    logger.warn('Stripe webhook: missing signature');
    return sendError(res, 'Missing stripe-signature header', 400);
  }
  
  let rawBody: Buffer;
  try {
    rawBody = await parseRawBody(req);
  } catch (error) {
    logger.error('Stripe webhook: failed to read body');
    return sendError(res, 'Failed to read request body', 400);
  }
  
  let event;
  try {
    event = verifyWebhookSignature(rawBody, signature);
  } catch (error) {
    logger.error('Stripe webhook: signature verification failed', {
      error: error instanceof Error ? error.message : String(error)
    });
    return sendError(res, 'Invalid signature', 400);
  }
  
  logger.info('Stripe webhook: received', { type: event.type, id: event.id });
  
  // Handle specific event types
  switch (event.type) {
    case 'payment_intent.succeeded': {
      const paymentIntent = event.data.object as any;
      const metadata = paymentIntent.metadata || {};
      
      logger.info('Payment succeeded', {
        paymentIntentId: paymentIntent.id,
        amount: paymentIntent.amount,
        sessionId: metadata.session_id?.substring(0, 8) + '...',
        size: metadata.size,
        phraseLength: metadata.phrase?.length,
      });
      
      // Update session to mark purchase complete
      if (metadata.session_id) {
        const session = getSession(metadata.session_id);
        if (session) {
          updateSession(metadata.session_id, {
            conversationState: 'purchase_complete',
            collectedAffirmation: true,
            collectedSize: metadata.size,
            collectedPhrase: metadata.phrase,
          });
          
          // Log purchase to conversation file for correlation
          logPurchase(session.customerId, metadata.session_id, paymentIntent.id);
        }
      }
      
      // Note: Customer state (shirtsBought) is updated on the frontend
      // when it receives the success callback. The cookie is the source of truth.
      break;
    }
    
    case 'payment_intent.payment_failed': {
      const paymentIntent = event.data.object as any;
      logger.warn('Payment failed', {
        paymentIntentId: paymentIntent.id,
        sessionId: paymentIntent.metadata?.session_id?.substring(0, 8) + '...',
        error: paymentIntent.last_payment_error?.message,
      });
      break;
    }
    
    default:
      logger.debug('Stripe webhook: unhandled event type', { type: event.type });
  }
  
  // Acknowledge receipt
  sendJson(res, { received: true });
}

interface ProfileResponse {
  customerId: string;
  totalShirtsBought: number;
  lastPurchaseAt: string | null;
  isRepeatCustomer: boolean;
  warmthLevel: 'cold' | 'neutral' | 'warm' | 'trusted';
}

async function handleProfile(req: IncomingMessage, res: ServerResponse) {
  const cookies = parseCookies(req);
  
  // Get customer state from cookie
  const customer = getOrCreateCustomerState(cookies);
  
  let warmthLevel: 'cold' | 'neutral' | 'warm' | 'trusted' = 'neutral';
  if (isCustomerBlocked(customer)) {
    warmthLevel = 'cold';
  } else if (customer.shirtsBought >= 5) {
    warmthLevel = 'trusted';
  } else if (customer.shirtsBought > 0) {
    warmthLevel = 'warm';
  }
  
  const response: ProfileResponse = {
    customerId: customer.id,
    totalShirtsBought: customer.shirtsBought,
    lastPurchaseAt: customer.lastPurchase,
    isRepeatCustomer: customer.shirtsBought > 0,
    warmthLevel
  };
  
  sendJson(res, response);
}

// Get session info
async function handleGetSession(req: IncomingMessage, res: ServerResponse, sessionId: string) {
  const session = getSession(sessionId);
  if (!session) {
    return sendError(res, 'Invalid session', 404);
  }
  
  sendJson(res, {
    size: session.collectedSize,
    phrase: session.collectedPhrase,
    hasAffirmation: session.collectedAffirmation,
    state: session.conversationState,
    referrerEmail: session.referrerEmail,
    discountCode: session.discountCode
  });
}

// Status/diagnostic endpoint
async function handleStatus(req: IncomingMessage, res: ServerResponse) {
  logger.info('Status check requested');
  
  const status: Record<string, unknown> = {
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    node: process.version,
    pid: process.pid,
  };
  
  // Session store info
  status.sessions = {
    activeCount: getSessionCount(),
  };
  
  // Test Monger Service (which tests LLM connection)
  try {
    const mongerResult = await testMongerServiceConnection();
    status.monger = mongerResult;
  } catch (error) {
    status.monger = { 
      ok: false, 
      error: error instanceof Error ? error.message : String(error) 
    };
  }
  
  // Test Stripe
  try {
    const stripeResult = await testStripeConnection();
    status.stripe = stripeResult;
  } catch (error) {
    status.stripe = { 
      ok: false, 
      error: error instanceof Error ? error.message : String(error) 
    };
  }
  
  // Config (sanitized)
  status.config = {
    mongerServiceUrl: config.mongerServiceUrl,
    hasStripeKey: !!config.stripeSecretKey,
    stripeKeyPrefix: config.stripeSecretKey ? config.stripeSecretKey.substring(0, 7) + '...' : '(missing)',
    shirtPriceCents: config.shirtPriceCents,
    conversationsPath: config.conversationsPath,
    logPath: config.logPath,
    logLevel: config.logLevel,
  };
  
  logger.info('Status check complete', status);
  sendJson(res, status);
}

// Handle time waster marking (called when session ends without purchase)
async function handleMarkTimeWaster(req: IncomingMessage, res: ServerResponse) {
  const body = await parseBody<{ sessionId: string }>(req);
  const cookies = parseCookies(req);
  
  if (!body.sessionId) {
    return sendError(res, 'Missing sessionId');
  }
  
  const session = getSession(body.sessionId);
  if (!session) {
    return sendError(res, 'Invalid session', 404);
  }
  
  // Get customer state and set blocked until
  const customer = getOrCreateCustomerState(cookies);
  const blockedUntil = new Date(Date.now() + config.timeWasterThresholdHours * 60 * 60 * 1000);
  customer.blockedUntil = blockedUntil.toISOString();
  
  // Update cookie with blocked status
  setCustomerStateCookie(res, customer);
  
  // Log session end
  logSessionEnd(customer.id, body.sessionId, 'time_waster');
  
  sendJson(res, { success: true, blockedUntil: customer.blockedUntil });
}

// Request router
async function handleRequest(req: IncomingMessage, res: ServerResponse) {
  const startTime = Date.now();
  const url = new URL(req.url || '/', `http://${req.headers.host}`);
  const path = url.pathname;
  const method = req.method || 'GET';
  
  // Handle CORS preflight
  if (method === 'OPTIONS') {
    res.writeHead(204, CORS_HEADERS);
    res.end();
    return;
  }
  
  // Skip logging for health checks (too noisy)
  const isHealthCheck = path === '/api/health';
  
  if (!isHealthCheck) {
    logger.request(method, path);
  }
  
  // Capture response status for logging
  const originalEnd = res.end.bind(res);
  let statusCode = 200;
  res.end = function(chunk?: any, encoding?: any, callback?: any) {
    if (!isHealthCheck) {
      logger.response(method, path, res.statusCode || statusCode, Date.now() - startTime);
    }
    return originalEnd(chunk, encoding, callback);
  } as typeof res.end;
  
  try {
    // Route requests
    if (path === '/api/session/init' && method === 'POST') {
      await handleSessionInit(req, res);
    } else if (path.startsWith('/api/session/') && method === 'GET') {
      const sessionId = path.replace('/api/session/', '');
      await handleGetSession(req, res, sessionId);
    } else if (path === '/api/chat' && method === 'POST') {
      await handleChat(req, res);
    } else if (path === '/api/referral-lookup' && method === 'POST') {
      await handleReferralLookup(req, res);
    // Stripe endpoints
    } else if (path === '/api/stripe/config' && method === 'GET') {
      await handleStripeConfig(req, res);
    } else if (path === '/api/stripe/create-payment-intent' && method === 'POST') {
      await handleCreatePaymentIntent(req, res);
    } else if (path === '/api/stripe/update-shipping' && method === 'POST') {
      await handleUpdateShipping(req, res);
    } else if (path === '/api/stripe/webhook' && method === 'POST') {
      await handleStripeWebhook(req, res);
    // Other endpoints
    } else if (path === '/api/profile' && method === 'GET') {
      await handleProfile(req, res);
    } else if (path === '/api/mark-time-waster' && method === 'POST') {
      await handleMarkTimeWaster(req, res);
    } else if (path === '/api/health' && method === 'GET') {
      sendJson(res, { status: 'ok', timestamp: new Date().toISOString() });
    } else if (path === '/api/version' && method === 'GET') {
      sendJson(res, { 
        service: 'cheeseshirt-api', 
        version: '1.0.0',
        node: process.version,
      });
    } else if (path === '/api/status' && method === 'GET') {
      await handleStatus(req, res);
    } else {
      sendError(res, 'Not found', 404);
    }
  } catch (error) {
    logger.error('Request handler error', { 
      method, 
      path,
      error: error instanceof Error ? { name: error.name, message: error.message, stack: error.stack } : String(error)
    });
    sendError(res, 'Internal server error', 500);
  }
}

// Create and start server
const server = createServer(handleRequest);

server.listen(config.port, config.host, () => {
  logger.info('Server started', {
    host: config.host,
    port: config.port,
    nodeEnv: process.env.NODE_ENV || 'development',
    logPath: config.logPath || '(console only)',
    logLevel: config.logLevel,
    mongerServiceUrl: config.mongerServiceUrl,
    hasStripeKey: !!config.stripeSecretKey,
    shirtPriceCents: config.shirtPriceCents,
    conversationsPath: config.conversationsPath,
  });
  
  logger.info('Endpoints available', {
    endpoints: [
      'POST /api/session/init',
      'POST /api/chat',
      'POST /api/referral-lookup',
      'GET  /api/stripe/config',
      'POST /api/stripe/create-payment-intent',
      'POST /api/stripe/update-shipping',
      'POST /api/stripe/webhook',
      'GET  /api/profile',
      'GET  /api/health',
      'GET  /api/status (diagnostic)'
    ]
  });
});

// Log all connections at the socket level
server.on('connection', (socket: Socket) => {
  const remoteAddr = socket.remoteAddress;
  logger.debug('New TCP connection', { remoteAddress: remoteAddr });
});

