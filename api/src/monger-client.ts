/**
 * Client for the Monger service.
 * 
 * This module handles all communication with the Python Monger service,
 * which hosts the LLM interactions for the Monger character.
 */
import { config } from './config.js';
import { logger } from './logger.js';

// Types matching the Monger service API

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

export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface CurrentState {
  has_affirmation: boolean;
  size: string | null;
  phrase: string | null;
}

export interface CustomerContext {
  total_shirts_bought: number;
  is_repeat_buyer: boolean;
  current_state: CurrentState;
  has_referral: boolean;
  referrer_email: string | null;
  is_checkout_mode: boolean;
  checkout_state: CheckoutState;
}

export interface ChatRequest {
  user_input: string;
  context: CustomerContext;
  conversation_history: ConversationMessage[];
}

export interface MongerState {
  has_affirmation: boolean;
  size: string | null;
  phrase: string | null;
  ready_for_checkout: boolean;
  ready_for_payment: boolean;
  mood: 'suspicious' | 'uneasy' | 'neutral' | 'warm';
  wants_referral_check: string | null;
  checkout: CheckoutState;
}

export interface ChatResponse {
  reply: string;
  state: MongerState;
}

export interface OpeningLineRequest {
  total_shirts_bought: number;
  is_time_waster: boolean;
  referral_status: string | null;
}

export interface OpeningLineResponse {
  line: string;
}

export interface ReferralLineRequest {
  status: string;
  discount_percentage: number;
}

export interface ReferralLineResponse {
  line: string;
}

export interface HealthResponse {
  status: string;
  llm_provider: string;
  llm_ok: boolean;
  llm_model: string | null;
  llm_latency_ms: number | null;
  error: string | null;
}

/**
 * Make a request to the Monger service.
 */
async function mongerRequest<T>(
  method: 'GET' | 'POST',
  endpoint: string,
  body?: unknown
): Promise<T> {
  const url = `${config.mongerServiceUrl}${endpoint}`;
  const startTime = Date.now();
  
  logger.debug('Monger service request', { method, endpoint });
  
  try {
    const options: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    };
    
    if (body) {
      options.body = JSON.stringify(body);
    }
    
    const response = await fetch(url, options);
    const durationMs = Date.now() - startTime;
    
    if (!response.ok) {
      const errorText = await response.text();
      logger.error('Monger service error response', {
        endpoint,
        status: response.status,
        durationMs,
        error: errorText.substring(0, 200),
      });
      throw new Error(`Monger service error: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json() as T;
    
    logger.debug('Monger service response', {
      endpoint,
      durationMs,
      status: response.status,
    });
    
    return data;
    
  } catch (error) {
    const durationMs = Date.now() - startTime;
    logger.error('Monger service request failed', {
      endpoint,
      durationMs,
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}

/**
 * Get a response from the Monger via the Monger service.
 */
export async function chat(request: ChatRequest): Promise<ChatResponse> {
  return mongerRequest<ChatResponse>('POST', '/chat', request);
}

/**
 * Get an opening line from the Monger.
 */
export async function getOpeningLine(request: OpeningLineRequest): Promise<OpeningLineResponse> {
  return mongerRequest<OpeningLineResponse>('POST', '/opening-line', request);
}

/**
 * Get a referral response line from the Monger.
 */
export async function getReferralLine(request: ReferralLineRequest): Promise<ReferralLineResponse> {
  return mongerRequest<ReferralLineResponse>('POST', '/referral-line', request);
}

/**
 * Test the Monger service connection.
 */
export async function testConnection(): Promise<HealthResponse> {
  return mongerRequest<HealthResponse>('GET', '/health');
}

