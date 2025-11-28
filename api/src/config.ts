import { config as dotenvConfig } from 'dotenv';
import { resolve } from 'path';
import { existsSync } from 'fs';

// Look for .env in current dir first, then project root (for local dev)
const localEnv = resolve(process.cwd(), '.env');
const rootEnv = resolve(process.cwd(), '../.env');

if (existsSync(localEnv)) {
  dotenvConfig({ path: localEnv });
} else if (existsSync(rootEnv)) {
  dotenvConfig({ path: rootEnv });
} else {
  dotenvConfig(); // fall back to default behavior
}

export const config = {
  // Monger Service (handles all LLM interactions)
  mongerServiceUrl: process.env.MONGER_SERVICE_URL || 'http://monger:3002',
  
  // Stripe
  stripeSecretKey: process.env.STRIPE_SECRET_KEY || '',
  stripePublishableKey: process.env.STRIPE_PUBLISHABLE_KEY || '',
  stripeWebhookSecret: process.env.STRIPE_WEBHOOK_SECRET || '',
  
  // Product pricing (in cents)
  shirtPriceCents: parseInt(process.env.SHIRT_PRICE_CENTS || '3500', 10),  // $35.00
  
  // Server
  port: parseInt(process.env.PORT || '3001', 10),
  host: process.env.HOST || '0.0.0.0',
  
  // Site URL (for receipts, etc)
  siteUrl: process.env.SITE_URL || 'https://cheeseshirt.com',
  
  // Database
  databasePath: process.env.DATABASE_PATH || './data/cheeseshirt.db',
  
  // Cookie
  cookieDomain: process.env.COOKIE_DOMAIN || 'localhost',
  cookieSecure: process.env.COOKIE_SECURE === 'true',
  
  // Time-waster threshold
  timeWasterThresholdHours: parseInt(process.env.TIME_WASTER_THRESHOLD_HOURS || '24', 10),
  
  // Logging
  logPath: process.env.LOG_PATH || '',  // e.g. /app/logs/cheeseshirt-api.log
  logLevel: (process.env.LOG_LEVEL || 'info') as 'debug' | 'info' | 'warn' | 'error',
} as const;

export function validateConfig(): void {
  const required = ['stripeSecretKey', 'mongerServiceUrl'];
  const missing = required.filter(key => !config[key as keyof typeof config]);
  
  if (missing.length > 0) {
    console.warn(`Warning: Missing configuration: ${missing.join(', ')}`);
  }
}
