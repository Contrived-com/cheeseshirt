/**
 * In-memory session store.
 * 
 * Sessions are ephemeral - lost on restart. That's fine because:
 * - Conversations are persisted to disk separately
 * - Order data lives in Stripe until worker-stripe-orders pulls it
 * - Customer state lives in browser cookie
 */

import { logger } from './logger.js';

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

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface Session {
  id: string;
  customerId: string;  // from cookie
  createdAt: string;
  lastMessageAt: string;
  
  // Conversation state
  conversationState: string;
  messages: Message[];
  
  // Collected order data
  collectedSize: string | null;
  collectedPhrase: string | null;
  collectedAffirmation: boolean;
  
  // Referral
  referrerEmail: string | null;
  discountCode: string | null;
  
  // Checkout
  checkoutState: CheckoutState;
  
  // Diagnostic mode
  diagnosticMode: boolean;
}

// In-memory session store
const sessions = new Map<string, Session>();

// Clean up old sessions periodically (sessions older than 24 hours)
const SESSION_TTL_MS = 24 * 60 * 60 * 1000;

function cleanupOldSessions() {
  const now = Date.now();
  let cleaned = 0;
  
  for (const [id, session] of sessions) {
    const lastActivity = new Date(session.lastMessageAt).getTime();
    if (now - lastActivity > SESSION_TTL_MS) {
      sessions.delete(id);
      cleaned++;
    }
  }
  
  if (cleaned > 0) {
    logger.debug('Cleaned up old sessions', { count: cleaned, remaining: sessions.size });
  }
}

// Run cleanup every hour
setInterval(cleanupOldSessions, 60 * 60 * 1000);

/**
 * Create a new session.
 */
export function createSession(sessionId: string, customerId: string): Session {
  const now = new Date().toISOString();
  
  const session: Session = {
    id: sessionId,
    customerId,
    createdAt: now,
    lastMessageAt: now,
    conversationState: 'greeting',
    messages: [],
    collectedSize: null,
    collectedPhrase: null,
    collectedAffirmation: false,
    referrerEmail: null,
    discountCode: null,
    checkoutState: {
      shipping: { name: null, line1: null, city: null, state: null, zip: null, country: 'US' },
      email: null,
    },
    diagnosticMode: false,
  };
  
  sessions.set(sessionId, session);
  logger.debug('Session created', { sessionId: sessionId.substring(0, 8) + '...', customerId: customerId.substring(0, 8) + '...' });
  
  return session;
}

/**
 * Get a session by ID.
 */
export function getSession(sessionId: string): Session | undefined {
  return sessions.get(sessionId);
}

/**
 * Update session state.
 */
export function updateSession(sessionId: string, updates: Partial<Omit<Session, 'id' | 'customerId' | 'createdAt'>>): Session | undefined {
  const session = sessions.get(sessionId);
  if (!session) return undefined;
  
  Object.assign(session, updates, { lastMessageAt: new Date().toISOString() });
  return session;
}

/**
 * Add a message to the session.
 */
export function addMessage(sessionId: string, role: 'user' | 'assistant', content: string): void {
  const session = sessions.get(sessionId);
  if (!session) return;
  
  session.messages.push({
    role,
    content,
    timestamp: new Date().toISOString(),
  });
  session.lastMessageAt = new Date().toISOString();
}

/**
 * Get recent messages from a session.
 */
export function getMessages(sessionId: string, limit = 20): Message[] {
  const session = sessions.get(sessionId);
  if (!session) return [];
  
  return session.messages.slice(-limit);
}

/**
 * Clear messages from a session (e.g., when exiting diagnostic mode).
 */
export function clearMessages(sessionId: string): void {
  const session = sessions.get(sessionId);
  if (!session) return;
  
  session.messages = [];
}

/**
 * Get session count (for monitoring).
 */
export function getSessionCount(): number {
  return sessions.size;
}

