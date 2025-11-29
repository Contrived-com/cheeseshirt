/**
 * Monger integration module.
 * 
 * This module provides the interface between the API and the Monger service.
 * All LLM interactions are delegated to the Python Monger service.
 */
import { logger } from './logger.js';
import { 
  getSession, 
  updateSessionState, 
  addMessage, 
  getSessionMessages,
  SessionRow,
  CustomerRow 
} from './db.js';
import * as mongerClient from './monger-client.js';

// Re-export types for backward compatibility
export interface ShippingAddress {
  name: string | null;
  line1: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  country: string;
}

export interface CheckoutState {
  shipping: ShippingAddress;
  email: string | null;
}

export interface MongerResponse {
  reply: string;
  state: {
    hasAffirmation: boolean;
    size: string | null;
    phrase: string | null;
    pendingConfirmation: boolean;
    readyForCheckout: boolean;
    readyForPayment: boolean;
    mood: 'suspicious' | 'uneasy' | 'neutral' | 'warm';
    wantsReferralCheck: string | null;
    checkout: CheckoutState;
  };
}

/**
 * Get an opening line for the Monger.
 */
export function getOpeningLine(
  customer: CustomerRow, 
  isRecentTimeWaster: boolean, 
  referralStatus?: string
): string {
  // This is now synchronous for backward compatibility,
  // but we'll make an async version available too
  // For now, we use cached/static lines
  
  // The actual call happens in server.ts via getOpeningLineAsync
  // This function is kept for backward compatibility
  
  if (isRecentTimeWaster) {
    return "you wasted the monger's time.  he'll be back later.";
  }
  
  if (customer.total_shirts_bought > 0) {
    const lines = [
      "you again.  good.  you here for another layer?",
      "back already.  the formula treating you right?",
      "knew you'd be back.  what phrase this time?"
    ];
    return lines[Math.floor(Math.random() * lines.length)];
  }
  
  if (referralStatus === 'vip') {
    return "heard you were coming.  good people vouch for you.  you here for a shirt?";
  }
  
  const lines = [
    "you here for a shirt?",
    "step closer.  you here for a shirt?",
    "keep your voice low.  you here for a shirt?"
  ];
  return lines[Math.floor(Math.random() * lines.length)];
}

/**
 * Get an opening line asynchronously via the Monger service.
 */
export async function getOpeningLineAsync(
  customer: CustomerRow, 
  isRecentTimeWaster: boolean, 
  referralStatus?: string
): Promise<string> {
  try {
    const response = await mongerClient.getOpeningLine({
      total_shirts_bought: customer.total_shirts_bought,
      is_time_waster: isRecentTimeWaster,
      referral_status: referralStatus || null,
    });
    return response.line;
  } catch (error) {
    logger.error('Failed to get opening line from Monger service, using fallback', {
      error: error instanceof Error ? error.message : String(error)
    });
    // Fallback to local logic
    return getOpeningLine(customer, isRecentTimeWaster, referralStatus);
  }
}

/**
 * Get a reply from the Monger via the Monger service.
 */
export async function getMongerReply(
  sessionId: string,
  userInput: string,
  customer: CustomerRow
): Promise<MongerResponse> {
  const session = getSession(sessionId);
  if (!session) {
    logger.error('getMongerReply: session not found', { sessionId: sessionId.substring(0, 8) + '...' });
    throw new Error('Session not found');
  }
  
  // Get conversation history
  const messageHistory = getSessionMessages(sessionId, 10).reverse();
  
  // Check if in checkout mode
  const isCheckoutMode = session.conversation_state === 'checkout_started' || 
                         session.conversation_state === 'collecting_shipping';
  
  // Parse existing checkout state
  let checkoutState: mongerClient.CheckoutState = {
    shipping: { name: null, line1: null, city: null, state: null, zip: null, country: 'US' },
    email: null
  };
  
  if (session.checkout_state) {
    try {
      checkoutState = JSON.parse(session.checkout_state);
    } catch (e) {
      // ignore parse errors
    }
  }
  
  // Build the request to the Monger service
  const chatRequest: mongerClient.ChatRequest = {
    user_input: userInput,
    context: {
      total_shirts_bought: customer.total_shirts_bought,
      is_repeat_buyer: customer.total_shirts_bought > 0,
      current_state: {
        has_affirmation: session.collected_affirmation === 1,
        size: session.collected_size,
        phrase: session.collected_phrase,
      },
      has_referral: !!session.referrer_email,
      referrer_email: session.referrer_email,
      is_checkout_mode: isCheckoutMode,
      checkout_state: checkoutState,
    },
    conversation_history: messageHistory.map(msg => ({
      role: msg.role as 'user' | 'assistant',
      content: msg.content,
    })),
  };
  
  const startTime = Date.now();
  
  logger.debug('Calling Monger service', {
    sessionId: sessionId.substring(0, 8) + '...',
    historyMessages: messageHistory.length,
    userInputLength: userInput.length,
    isCheckoutMode,
  });
  
  try {
    const response = await mongerClient.chat(chatRequest);
    const durationMs = Date.now() - startTime;
    
    logger.debug('Monger service response', {
      sessionId: sessionId.substring(0, 8) + '...',
      durationMs,
      mood: response.state.mood,
      readyForCheckout: response.state.ready_for_checkout,
    });
    
    // Convert response to the format expected by the API
    const normalizedResponse: MongerResponse = {
      reply: response.reply,
      state: {
        hasAffirmation: response.state.has_affirmation,
        size: response.state.size,
        phrase: response.state.phrase,
        pendingConfirmation: response.state.pending_confirmation,
        readyForCheckout: response.state.ready_for_checkout,
        readyForPayment: response.state.ready_for_payment,
        mood: response.state.mood,
        wantsReferralCheck: response.state.wants_referral_check,
        checkout: response.state.checkout,
      },
    };
    
    // Store messages
    addMessage(sessionId, 'user', userInput);
    addMessage(sessionId, 'assistant', normalizedResponse.reply);
    
    // Determine conversation state
    let convState = 'conversation';
    if (normalizedResponse.state.readyForPayment) {
      convState = 'ready_for_payment';
    } else if (normalizedResponse.state.readyForCheckout) {
      convState = 'collecting_shipping';
    }
    
    // Update session state
    updateSessionState(sessionId, {
      conversationState: convState,
      collectedAffirmation: normalizedResponse.state.hasAffirmation,
      collectedSize: normalizedResponse.state.size,
      collectedPhrase: normalizedResponse.state.phrase,
      checkoutState: JSON.stringify(normalizedResponse.state.checkout),
    });
    
    return normalizedResponse;
    
  } catch (error) {
    const durationMs = Date.now() - startTime;
    
    logger.error('Monger service error', {
      sessionId: sessionId.substring(0, 8) + '...',
      durationMs,
      error: error instanceof Error ? error.message : String(error),
    });
    
    // Fallback response in character
    return {
      reply: "...signal's bad.  say that again.",
      state: {
        hasAffirmation: session.collected_affirmation === 1,
        size: session.collected_size,
        phrase: session.collected_phrase,
        pendingConfirmation: false,
        readyForCheckout: false,
        readyForPayment: false,
        mood: 'neutral',
        wantsReferralCheck: null,
        checkout: checkoutState,
      },
    };
  }
}

/**
 * Test the Monger service connection.
 */
export async function testMongerServiceConnection(): Promise<{ 
  ok: boolean; 
  llmProvider?: string;
  model?: string; 
  latencyMs?: number; 
  error?: string 
}> {
  try {
    logger.info('Testing Monger service connection');
    
    const health = await mongerClient.testConnection();
    
    logger.info('Monger service connection test', { 
      status: health.status,
      llmProvider: health.llm_provider,
      llmOk: health.llm_ok,
      latencyMs: health.llm_latency_ms,
    });
    
    return { 
      ok: health.llm_ok, 
      llmProvider: health.llm_provider,
      model: health.llm_model || undefined,
      latencyMs: health.llm_latency_ms || undefined,
      error: health.error || undefined,
    };
  } catch (error) {
    logger.error('Monger service connection test failed', {
      error: error instanceof Error ? error.message : String(error)
    });
    
    return { 
      ok: false, 
      error: error instanceof Error ? error.message : String(error)
    };
  }
}

/**
 * Get referral-aware response line from the Monger service.
 */
export async function getReferralResponseLineAsync(
  status: string, 
  discountPercentage: number
): Promise<string> {
  try {
    const response = await mongerClient.getReferralLine({
      status,
      discount_percentage: discountPercentage,
    });
    return response.line;
  } catch (error) {
    logger.error('Failed to get referral line from Monger service, using fallback', {
      error: error instanceof Error ? error.message : String(error)
    });
    // Fallback
    return getReferralResponseLine(status, discountPercentage);
  }
}

/**
 * Get referral-aware response line (sync fallback).
 */
export function getReferralResponseLine(status: string, discountPercentage: number): string {
  const templates: Record<string, string> = {
    vip: `any friend of theirs is a friend of mine.  ${discountPercentage}% off.`,
    ultra: `any friend of theirs is a friend of mine.  ${discountPercentage}% off.`,
    buyer: `friend of theirs huh.  alright.  ${discountPercentage}% off for you.`,
    unknown: `never heard of em.  no discount, but you can still get a shirt.`,
  };
  
  return templates[status] || templates.unknown;
}

/**
 * Get the fallback response.
 */
export function getFallbackResponse() {
  return {
    line: "...signal's bad.  say that again.",
    mood: "neutral"
  };
}

// =============================================================================
// Diagnostic Mode
// =============================================================================

// Trigger phrases for entering/exiting diagnostic mode
const DIAGNOSTIC_ENTER_PHRASES = ['diagnostic', 'enter diagnostic', 'diagnostic mode'];
const DIAGNOSTIC_EXIT_PHRASES = ['leave diagnostic', 'exit diagnostic', 'back to character', 'resume character'];

/**
 * Check if user input should trigger diagnostic mode entry.
 */
export function shouldEnterDiagnostic(userInput: string): boolean {
  const lower = userInput.toLowerCase().trim();
  return DIAGNOSTIC_ENTER_PHRASES.some(phrase => lower === phrase || lower.startsWith(phrase + ' '));
}

/**
 * Check if user input should trigger diagnostic mode exit.
 */
export function shouldExitDiagnostic(userInput: string): boolean {
  const lower = userInput.toLowerCase().trim();
  return DIAGNOSTIC_EXIT_PHRASES.some(phrase => lower === phrase || lower.startsWith(phrase));
}

/**
 * Get a response in diagnostic mode via the Monger service.
 */
export async function getDiagnosticReply(
  sessionId: string,
  userInput: string
): Promise<{ reply: string; diagnosticData?: Record<string, unknown> }> {
  // Get conversation history for diagnostic mode
  const messageHistory = getSessionMessages(sessionId, 10).reverse();
  
  logger.debug('Diagnostic chat request', {
    sessionId: sessionId.substring(0, 8) + '...',
    userInputLength: userInput.length,
  });
  
  try {
    const response = await mongerClient.diagnosticChat({
      user_input: userInput,
      conversation_history: messageHistory.map(msg => ({
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
      })),
    });
    
    // Store messages
    addMessage(sessionId, 'user', userInput);
    addMessage(sessionId, 'assistant', response.reply);
    
    return {
      reply: response.reply,
      diagnosticData: response.diagnostic_data || undefined,
    };
    
  } catch (error) {
    logger.error('Diagnostic chat error', {
      sessionId: sessionId.substring(0, 8) + '...',
      error: error instanceof Error ? error.message : String(error),
    });
    
    return {
      reply: `Diagnostic mode error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Get the diagnostic mode entry message.
 */
export function getDiagnosticEntryMessage(): string {
  return `[DIAGNOSTIC MODE ENABLED]

I've dropped character. I'm now a helpful assistant for the cheeseshirt system.

You can ask me about:
• Service health and versions
• Log files (try "show me the api logs")  
• System status
• Troubleshooting help

Say "leave diagnostic" to return me to character.`;
}

/**
 * Get the diagnostic mode exit message.
 */
export function getDiagnosticExitMessage(): string {
  return `[DIAGNOSTIC MODE DISABLED]

...where was i.  right.  you here for a shirt?`;
}
