import Database, { Database as DatabaseType } from 'better-sqlite3';
import { config } from './config.js';
import { mkdirSync, existsSync } from 'fs';
import { dirname } from 'path';

// Simple console log for early startup (before logger is available)
const dbLog = (msg: string, data?: object) => {
  const ts = new Date().toISOString();
  console.log(`[${ts}] [DB] ${msg}`, data ? JSON.stringify(data) : '');
};

// Ensure data directory exists
const dbDir = dirname(config.databasePath);
dbLog('Initializing database', { path: config.databasePath, dir: dbDir });

if (!existsSync(dbDir)) {
  dbLog('Creating database directory', { dir: dbDir });
  mkdirSync(dbDir, { recursive: true });
}

let db: DatabaseType;
try {
  db = new Database(config.databasePath);
  dbLog('Database connection opened');
} catch (error) {
  dbLog('FATAL: Failed to open database', { 
    error: error instanceof Error ? error.message : String(error) 
  });
  throw error;
}

export { db };

// Initialize database schema
dbLog('Creating schema (if not exists)');
try {
  db.exec(`
  CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    total_shirts_bought INTEGER DEFAULT 0,
    last_purchase_at TEXT,
    last_interaction_at TEXT,
    time_wasted_flag INTEGER DEFAULT 0,
    referral_email TEXT,
    notes TEXT
  );
  
  CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_message_at TEXT,
    conversation_state TEXT DEFAULT 'greeting',
    collected_size TEXT,
    collected_phrase TEXT,
    collected_affirmation INTEGER DEFAULT 0,
    referrer_email TEXT,
    discount_code TEXT,
    checkout_state TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
  );
  
  CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
  );
  
  CREATE TABLE IF NOT EXISTS referrals (
    email TEXT PRIMARY KEY,
    status TEXT DEFAULT 'buyer',
    total_purchases INTEGER DEFAULT 1,
    discount_percentage INTEGER DEFAULT 10,
    is_vip INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  
  CREATE INDEX IF NOT EXISTS idx_sessions_customer ON sessions(customer_id);
  CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
`);

  // Migration: add checkout_state column if it doesn't exist
  const sessionCols = db.prepare("PRAGMA table_info(sessions)").all() as { name: string }[];
  if (!sessionCols.find(c => c.name === 'checkout_state')) {
    dbLog('Migrating: adding checkout_state column to sessions');
    db.exec('ALTER TABLE sessions ADD COLUMN checkout_state TEXT');
  }
  
  // Migration: add diagnostic_mode column if it doesn't exist
  if (!sessionCols.find(c => c.name === 'diagnostic_mode')) {
    dbLog('Migrating: adding diagnostic_mode column to sessions');
    db.exec('ALTER TABLE sessions ADD COLUMN diagnostic_mode INTEGER DEFAULT 0');
  }
  
  dbLog('Schema ready');
} catch (error) {
  dbLog('FATAL: Failed to create schema', { 
    error: error instanceof Error ? error.message : String(error) 
  });
  throw error;
}

// Customer operations
export function getOrCreateCustomer(customerId: string) {
  let customer = db.prepare('SELECT * FROM customers WHERE id = ?').get(customerId) as CustomerRow | undefined;
  
  if (!customer) {
    db.prepare('INSERT INTO customers (id) VALUES (?)').run(customerId);
    customer = db.prepare('SELECT * FROM customers WHERE id = ?').get(customerId) as CustomerRow;
  }
  
  return customer;
}

export function updateCustomerInteraction(customerId: string) {
  db.prepare(`
    UPDATE customers 
    SET last_interaction_at = CURRENT_TIMESTAMP 
    WHERE id = ?
  `).run(customerId);
}

export function markCustomerTimeWaster(customerId: string) {
  db.prepare(`
    UPDATE customers 
    SET time_wasted_flag = 1, last_interaction_at = CURRENT_TIMESTAMP 
    WHERE id = ?
  `).run(customerId);
}

export function clearTimeWasterFlag(customerId: string) {
  db.prepare('UPDATE customers SET time_wasted_flag = 0 WHERE id = ?').run(customerId);
}

export function recordPurchase(customerId: string) {
  db.prepare(`
    UPDATE customers 
    SET total_shirts_bought = total_shirts_bought + 1,
        last_purchase_at = CURRENT_TIMESTAMP,
        time_wasted_flag = 0
    WHERE id = ?
  `).run(customerId);
}

// Session operations
export function createSession(sessionId: string, customerId: string) {
  db.prepare(`
    INSERT INTO sessions (id, customer_id, last_message_at)
    VALUES (?, ?, CURRENT_TIMESTAMP)
  `).run(sessionId, customerId);
  
  return getSession(sessionId);
}

export function getSession(sessionId: string) {
  return db.prepare('SELECT * FROM sessions WHERE id = ?').get(sessionId) as SessionRow | undefined;
}

export function updateSessionState(sessionId: string, updates: Partial<SessionUpdates>) {
  const fields: string[] = [];
  const values: (string | number | null)[] = [];
  
  if (updates.conversationState !== undefined) {
    fields.push('conversation_state = ?');
    values.push(updates.conversationState);
  }
  if (updates.collectedSize !== undefined) {
    fields.push('collected_size = ?');
    values.push(updates.collectedSize);
  }
  if (updates.collectedPhrase !== undefined) {
    fields.push('collected_phrase = ?');
    values.push(updates.collectedPhrase);
  }
  if (updates.collectedAffirmation !== undefined) {
    fields.push('collected_affirmation = ?');
    values.push(updates.collectedAffirmation ? 1 : 0);
  }
  if (updates.referrerEmail !== undefined) {
    fields.push('referrer_email = ?');
    values.push(updates.referrerEmail);
  }
  if (updates.discountCode !== undefined) {
    fields.push('discount_code = ?');
    values.push(updates.discountCode);
  }
  if (updates.checkoutState !== undefined) {
    fields.push('checkout_state = ?');
    values.push(updates.checkoutState);
  }
  if (updates.diagnosticMode !== undefined) {
    fields.push('diagnostic_mode = ?');
    values.push(updates.diagnosticMode ? 1 : 0);
  }
  
  fields.push('last_message_at = CURRENT_TIMESTAMP');
  values.push(sessionId);
  
  if (fields.length > 1) {
    db.prepare(`UPDATE sessions SET ${fields.join(', ')} WHERE id = ?`).run(...values);
  }
}

// Message operations
export function addMessage(sessionId: string, role: 'user' | 'assistant', content: string) {
  db.prepare(`
    INSERT INTO messages (session_id, role, content)
    VALUES (?, ?, ?)
  `).run(sessionId, role, content);
}

export function getSessionMessages(sessionId: string, limit = 20) {
  return db.prepare(`
    SELECT role, content FROM messages 
    WHERE session_id = ? 
    ORDER BY created_at DESC 
    LIMIT ?
  `).all(sessionId, limit) as MessageRow[];
}

// Referral operations
export function lookupReferral(email: string) {
  return db.prepare('SELECT * FROM referrals WHERE email = ?').get(email.toLowerCase()) as ReferralRow | undefined;
}

export function createOrUpdateReferral(email: string, totalPurchases: number) {
  const existing = lookupReferral(email);
  
  if (existing) {
    db.prepare(`
      UPDATE referrals 
      SET total_purchases = ?, 
          discount_percentage = CASE 
            WHEN ? >= 10 THEN 25 
            WHEN ? >= 5 THEN 20 
            WHEN ? >= 3 THEN 15 
            ELSE 10 
          END,
          is_vip = CASE WHEN ? >= 5 THEN 1 ELSE 0 END
      WHERE email = ?
    `).run(totalPurchases, totalPurchases, totalPurchases, totalPurchases, totalPurchases, email.toLowerCase());
  } else {
    db.prepare(`
      INSERT INTO referrals (email, total_purchases, discount_percentage, is_vip)
      VALUES (?, ?, ?, ?)
    `).run(email.toLowerCase(), totalPurchases, totalPurchases >= 3 ? 15 : 10, totalPurchases >= 5 ? 1 : 0);
  }
  
  return lookupReferral(email);
}

// Check if customer is a recent time-waster
export function isRecentTimeWaster(customerId: string, thresholdHours: number): boolean {
  const customer = getOrCreateCustomer(customerId);
  
  if (!customer.time_wasted_flag) return false;
  if (!customer.last_interaction_at) return false;
  
  const lastInteraction = new Date(customer.last_interaction_at);
  const hoursSince = (Date.now() - lastInteraction.getTime()) / (1000 * 60 * 60);
  
  return hoursSince < thresholdHours;
}

// Types
export interface CustomerRow {
  id: string;
  created_at: string;
  total_shirts_bought: number;
  last_purchase_at: string | null;
  last_interaction_at: string | null;
  time_wasted_flag: number;
  referral_email: string | null;
  notes: string | null;
}

export interface SessionRow {
  id: string;
  customer_id: string;
  created_at: string;
  last_message_at: string | null;
  conversation_state: string;
  collected_size: string | null;
  collected_phrase: string | null;
  collected_affirmation: number;
  referrer_email: string | null;
  discount_code: string | null;
  checkout_state: string | null;
  diagnostic_mode: number;
}

export interface MessageRow {
  role: string;
  content: string;
}

export interface ReferralRow {
  email: string;
  status: string;
  total_purchases: number;
  discount_percentage: number;
  is_vip: number;
  created_at: string;
}

export interface SessionUpdates {
  conversationState: string;
  collectedSize: string | null;
  collectedPhrase: string | null;
  collectedAffirmation: boolean;
  referrerEmail: string | null;
  discountCode: string | null;
  checkoutState: string | null;
  diagnosticMode: boolean;
}

