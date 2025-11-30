/**
 * Conversation file persistence.
 * 
 * Writes conversations to append-only JSONL files.
 * Each customer (by cookie ID) gets their own file.
 * Sessions are marked with session IDs that can be correlated
 * with Stripe PaymentIntent metadata by workers.
 * 
 * File format (JSONL - one JSON object per line):
 *   {"t":"start","sid":"abc-123","ts":"2024-01-15T10:30:00Z"}
 *   {"r":"assistant","c":"you here for a shirt?","ts":"..."}
 *   {"r":"user","c":"yeah","ts":"..."}
 *   {"t":"end","sid":"abc-123","ts":"..."}
 */

import { appendFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { config } from './config.js';
import { logger } from './logger.js';

// Ensure conversations directory exists
function ensureConversationsDir(): string {
  const dir = config.conversationsPath;
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
    logger.info('Created conversations directory', { path: dir });
  }
  return dir;
}

/**
 * Get the conversation file path for a customer.
 */
function getConversationFilePath(customerId: string): string {
  const dir = ensureConversationsDir();
  // Sanitize customerId to be safe for filenames
  const safeId = customerId.replace(/[^a-zA-Z0-9-_]/g, '_');
  return join(dir, `${safeId}.jsonl`);
}

/**
 * Append a line to the conversation file.
 */
function appendToFile(customerId: string, data: Record<string, unknown>): void {
  try {
    const filePath = getConversationFilePath(customerId);
    const line = JSON.stringify(data) + '\n';
    appendFileSync(filePath, line, 'utf-8');
  } catch (error) {
    logger.error('Failed to write conversation', {
      customerId: customerId.substring(0, 8) + '...',
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

/**
 * Log the start of a new session.
 */
export function logSessionStart(customerId: string, sessionId: string): void {
  appendToFile(customerId, {
    t: 'start',
    sid: sessionId,
    ts: new Date().toISOString(),
  });
  
  logger.debug('Conversation session started', {
    customerId: customerId.substring(0, 8) + '...',
    sessionId: sessionId.substring(0, 8) + '...',
  });
}

/**
 * Log a message in the conversation.
 */
export function logMessage(customerId: string, sessionId: string, role: 'user' | 'assistant', content: string): void {
  appendToFile(customerId, {
    r: role,
    c: content,
    sid: sessionId,
    ts: new Date().toISOString(),
  });
}

/**
 * Log the end of a session.
 */
export function logSessionEnd(customerId: string, sessionId: string, reason?: string): void {
  appendToFile(customerId, {
    t: 'end',
    sid: sessionId,
    reason: reason || 'normal',
    ts: new Date().toISOString(),
  });
  
  logger.debug('Conversation session ended', {
    customerId: customerId.substring(0, 8) + '...',
    sessionId: sessionId.substring(0, 8) + '...',
    reason,
  });
}

/**
 * Log a purchase completion (for easier correlation).
 */
export function logPurchase(customerId: string, sessionId: string, paymentIntentId: string): void {
  appendToFile(customerId, {
    t: 'purchase',
    sid: sessionId,
    pi: paymentIntentId,
    ts: new Date().toISOString(),
  });
  
  logger.info('Conversation purchase logged', {
    customerId: customerId.substring(0, 8) + '...',
    sessionId: sessionId.substring(0, 8) + '...',
    paymentIntentId,
  });
}

