import { config as dotenvConfig } from 'dotenv';
import { resolve } from 'path';

dotenvConfig({ path: resolve(process.cwd(), '.env') });

export const config = {
  // OpenAI
  openaiApiKey: process.env.OPENAI_API_KEY || '',
  openaiModel: process.env.OPENAI_MODEL || 'gpt-4o',
  
  // Shopify
  shopifyStoreUrl: process.env.SHOPIFY_STORE_URL || '',
  shopifyAccessToken: process.env.SHOPIFY_ACCESS_TOKEN || '',
  shopifyApiVersion: process.env.SHOPIFY_API_VERSION || '2024-01',
  shopifyProductId: process.env.SHOPIFY_PRODUCT_ID || '',
  
  // Server
  port: parseInt(process.env.PORT || '3001', 10),
  host: process.env.HOST || '0.0.0.0',
  
  // Database
  databasePath: process.env.DATABASE_PATH || './data/cheeseshirt.db',
  
  // Cookie
  cookieDomain: process.env.COOKIE_DOMAIN || 'localhost',
  cookieSecure: process.env.COOKIE_SECURE === 'true',
  
  // Time-waster threshold
  timeWasterThresholdHours: parseInt(process.env.TIME_WASTER_THRESHOLD_HOURS || '24', 10),
} as const;

export function validateConfig(): void {
  const required = ['openaiApiKey'];
  const missing = required.filter(key => !config[key as keyof typeof config]);
  
  if (missing.length > 0) {
    console.warn(`Warning: Missing configuration: ${missing.join(', ')}`);
  }
}

