import { createServer, IncomingMessage, ServerResponse } from 'http';
import type { Socket } from 'net';
import { v4 as uuidv4 } from 'uuid';
import { config, validateConfig } from './config.js';
import { logger } from './logger.js';
import {
  getOrCreateCustomer,
  createSession,
  getSession,
  updateCustomerInteraction,
  markCustomerTimeWaster,
  isRecentTimeWaster,
  lookupReferral,
  createOrUpdateReferral,
  updateSessionState,
  addMessage,
  CustomerRow
} from './db.js';
import { getMongerReply, getOpeningLine, getReferralResponseLine, MongerResponse, testOpenAIConnection } from './monger.js';
import { 
  createPaymentIntent, 
  updatePaymentIntentShipping,
  verifyWebhookSignature,
  getPublishableKey,
  testStripeConnection
} from './stripe.js';
import { db } from './db.js';

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

// Set cookie in response
function setCookie(res: ServerResponse, name: string, value: string, maxAgeDays = 365) {
  const maxAge = maxAgeDays * 24 * 60 * 60;
  const secure = config.cookieSecure ? '; Secure' : '';
  const sameSite = config.cookieSecure ? '; SameSite=None' : '; SameSite=Lax';
  
  res.setHeader('Set-Cookie', 
    `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; HttpOnly${secure}${sameSite}`
  );
}

// API Handlers

interface SessionInitRequest {
  cookieId?: string;
}

interface SessionInitResponse {
  sessionId: string;
  customerId: string;
  mongerOpeningLine: string;
  isRecentTimeWaster: boolean;
  isRepeatCustomer: boolean;
  recentOrdersCount: number;
}

async function handleSessionInit(req: IncomingMessage, res: ServerResponse) {
  const body = await parseBody<SessionInitRequest>(req);
  const cookies = parseCookies(req);
  
  // Get or create customer ID
  let customerId = body.cookieId || cookies['cheeseshirt_id'];
  let isNewCustomer = false;
  
  if (!customerId) {
    customerId = uuidv4();
    isNewCustomer = true;
  }
  
  // Set cookie if new
  if (isNewCustomer) {
    setCookie(res, 'cheeseshirt_id', customerId);
  }
  
  // Get customer record
  const customer = getOrCreateCustomer(customerId);
  
  // Check if time waster
  const timeWaster = isRecentTimeWaster(customerId, config.timeWasterThresholdHours);
  
  // Create new session
  const sessionId = uuidv4();
  createSession(sessionId, customerId);
  
  logger.session('init', sessionId, customerId, { 
    isNewCustomer, 
    isTimeWaster: timeWaster,
    totalShirtsBought: customer.total_shirts_bought 
  });
  
  // Get opening line
  const openingLine = getOpeningLine(customer, timeWaster);
  
  // Store opening line as first assistant message
  if (!timeWaster) {
    addMessage(sessionId, 'assistant', openingLine);
  }
  
  // Update interaction timestamp
  updateCustomerInteraction(customerId);
  
  const response: SessionInitResponse = {
    sessionId,
    customerId,
    mongerOpeningLine: openingLine,
    isRecentTimeWaster: timeWaster,
    isRepeatCustomer: customer.total_shirts_bought > 0,
    recentOrdersCount: customer.total_shirts_bought
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

interface ChatResponse {
  mongerReply: string;
  conversationState: string;
  needsSize: boolean;
  needsPhrase: boolean;
  needsAffirmation: boolean;
  readyForCheckout: boolean;
  readyForPayment: boolean;
  wantsReferralCheck: string | null;
  mood: string;
  collectedSize: string | null;
  collectedPhrase: string | null;
  checkout: CheckoutState;
}

async function handleChat(req: IncomingMessage, res: ServerResponse) {
  const body = await parseBody<ChatRequest>(req);
  
  if (!body.sessionId || !body.userInput) {
    logger.warn('Chat: missing required fields', { hasSessionId: !!body.sessionId, hasUserInput: !!body.userInput });
    return sendError(res, 'Missing sessionId or userInput');
  }
  
  const session = getSession(body.sessionId);
  if (!session) {
    logger.warn('Chat: invalid session', { sessionId: body.sessionId.substring(0, 8) + '...' });
    return sendError(res, 'Invalid session', 404);
  }
  
  const customer = getOrCreateCustomer(session.customer_id);
  
  logger.debug('Chat: processing', { 
    sessionId: body.sessionId.substring(0, 8) + '...', 
    inputLength: body.userInput.length,
    userInputPreview: body.userInput.substring(0, 50)
  });
  
  // Check if time waster trying to come back
  if (isRecentTimeWaster(session.customer_id, config.timeWasterThresholdHours)) {
    logger.info('Chat: blocked time waster', { customerId: session.customer_id.substring(0, 8) + '...' });
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
      }
    });
  }
  
  try {
    const mongerResponse = await getMongerReply(body.sessionId, body.userInput, customer);
    
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
      readyForCheckout: mongerResponse.state.readyForCheckout,
      readyForPayment: mongerResponse.state.readyForPayment,
      wantsReferralCheck: mongerResponse.state.wantsReferralCheck,
      mood: mongerResponse.state.mood,
      collectedSize: mongerResponse.state.size,
      collectedPhrase: mongerResponse.state.phrase,
      checkout: mongerResponse.state.checkout
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
  referrerEmail: string;
}

interface ReferralLookupResponse {
  referrerStatus: 'unknown' | 'buyer' | 'vip' | 'ultra';
  discountPercentage: number;
  mongerLine: string;
}

async function handleReferralLookup(req: IncomingMessage, res: ServerResponse) {
  const body = await parseBody<ReferralLookupRequest>(req);
  
  if (!body.sessionId || !body.referrerEmail) {
    return sendError(res, 'Missing sessionId or referrerEmail');
  }
  
  const session = getSession(body.sessionId);
  if (!session) {
    return sendError(res, 'Invalid session', 404);
  }
  
  const referral = lookupReferral(body.referrerEmail);
  
  let status: 'unknown' | 'buyer' | 'vip' | 'ultra' = 'unknown';
  let discountPercentage = 0;
  
  if (referral) {
    if (referral.total_purchases >= 10) {
      status = 'ultra';
      discountPercentage = 25;
    } else if (referral.is_vip || referral.total_purchases >= 5) {
      status = 'vip';
      discountPercentage = 20;
    } else {
      status = 'buyer';
      discountPercentage = referral.discount_percentage || 10;
    }
    
    // Update session with referrer info
    updateSessionState(body.sessionId, {
      referrerEmail: body.referrerEmail,
      discountCode: discountPercentage > 0 ? `REF${discountPercentage}` : null,
      conversationState: session.conversation_state,
      collectedAffirmation: session.collected_affirmation === 1,
      collectedSize: session.collected_size,
      collectedPhrase: session.collected_phrase
    });
  }
  
  const mongerLine = getReferralResponseLine(status, discountPercentage);
  
  const response: ReferralLookupResponse = {
    referrerStatus: status,
    discountPercentage,
    mongerLine
  };
  
  sendJson(res, response);
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
    updateSessionState(body.sessionId, {
      conversationState: 'checkout_started',
      collectedSize: body.size,
      collectedPhrase: body.phrase,
      collectedAffirmation: true,
      referrerEmail: session.referrer_email,
      discountCode: session.discount_code
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
          updateSessionState(metadata.session_id, {
            conversationState: 'purchase_complete',
            collectedAffirmation: true,
            collectedSize: metadata.size,
            collectedPhrase: metadata.phrase,
            referrerEmail: session.referrer_email,
            discountCode: session.discount_code,
          });
          
          // Increment customer purchase count
          const customer = getOrCreateCustomer(session.customer_id);
          // Note: You may want to add a function to increment purchase count
        }
      }
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
  const url = new URL(req.url || '', `http://${req.headers.host}`);
  const sessionId = url.searchParams.get('sessionId');
  
  if (!sessionId) {
    return sendError(res, 'Missing sessionId');
  }
  
  const session = getSession(sessionId);
  if (!session) {
    return sendError(res, 'Invalid session', 404);
  }
  
  const customer = getOrCreateCustomer(session.customer_id);
  
  let warmthLevel: 'cold' | 'neutral' | 'warm' | 'trusted' = 'neutral';
  if (customer.time_wasted_flag) {
    warmthLevel = 'cold';
  } else if (customer.total_shirts_bought >= 5) {
    warmthLevel = 'trusted';
  } else if (customer.total_shirts_bought > 0) {
    warmthLevel = 'warm';
  }
  
  const response: ProfileResponse = {
    customerId: customer.id,
    totalShirtsBought: customer.total_shirts_bought,
    lastPurchaseAt: customer.last_purchase_at,
    isRepeatCustomer: customer.total_shirts_bought > 0,
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
    size: session.collected_size,
    phrase: session.collected_phrase,
    hasAffirmation: session.collected_affirmation === 1,
    state: session.conversation_state,
    referrerEmail: session.referrer_email,
    discountCode: session.discount_code
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
  
  // Test database
  try {
    const dbTest = db.prepare('SELECT 1 as test').get() as { test: number };
    status.database = { ok: true, test: dbTest.test };
  } catch (error) {
    status.database = { 
      ok: false, 
      error: error instanceof Error ? error.message : String(error) 
    };
  }
  
  // Test OpenAI
  try {
    const openaiResult = await testOpenAIConnection();
    status.openai = openaiResult;
  } catch (error) {
    status.openai = { 
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
    hasOpenAiKey: !!config.openaiApiKey,
    openAiKeyPrefix: config.openaiApiKey ? config.openaiApiKey.substring(0, 7) + '...' : '(missing)',
    openAiModel: config.openaiModel,
    hasStripeKey: !!config.stripeSecretKey,
    stripeKeyPrefix: config.stripeSecretKey ? config.stripeSecretKey.substring(0, 7) + '...' : '(missing)',
    shirtPriceCents: config.shirtPriceCents,
    databasePath: config.databasePath,
    logPath: config.logPath,
    logLevel: config.logLevel,
  };
  
  logger.info('Status check complete', status);
  sendJson(res, status);
}

// Handle time waster marking (called when session ends without purchase)
async function handleMarkTimeWaster(req: IncomingMessage, res: ServerResponse) {
  const body = await parseBody<{ sessionId: string }>(req);
  
  if (!body.sessionId) {
    return sendError(res, 'Missing sessionId');
  }
  
  const session = getSession(body.sessionId);
  if (!session) {
    return sendError(res, 'Invalid session', 404);
  }
  
  markCustomerTimeWaster(session.customer_id);
  sendJson(res, { success: true });
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
    hasOpenAiKey: !!config.openaiApiKey,
    openAiModel: config.openaiModel,
    hasStripeKey: !!config.stripeSecretKey,
    shirtPriceCents: config.shirtPriceCents,
    databasePath: config.databasePath
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

