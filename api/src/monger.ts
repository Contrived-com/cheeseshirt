import OpenAI from 'openai';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config } from './config.js';
import { logger } from './logger.js';
import { 
  getSession, 
  updateSessionState, 
  addMessage, 
  getSessionMessages,
  getOrCreateCustomer,
  SessionRow,
  CustomerRow 
} from './db.js';

// Load the monger's character from the config file
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Use env var if set, otherwise default to project root (works for local dev)
// In Docker, set MONGER_CONFIG_PATH=/app/monger/monger.json
const mongerConfigPath = process.env.MONGER_CONFIG_PATH || resolve(__dirname, '../../monger/monger.json');

logger.info('Loading monger character config', { path: mongerConfigPath });

interface MongerConfig {
  identity: {
    name: string;
    age: string;
    appearance: string;
    setting: string;
    weather: string;
    locationReason: string;
  };
  product: {
    name: string;
    description: string;
    uniqueness: string;
    mystery: string;
    security: string;
  };
  lore: {
    slang: string;
    status: string;
    family: string;
    secrecy: string;
    competitors: string;
    theFormula: string;
    authorities: string;
  };
  voice: {
    case: string;
    punctuation: {
      emdashes: string;
      ellipsis: string;
      sentenceEnd: string;
    };
    style: string;
    length: string;
  };
  salesFlow: {
    collect: string[];
    onComplete: string;
    onPhraseReceived: string;
  };
  emotionalModes: {
    [key: string]: {
      triggers: string;
      behavior: string;
      examples?: string[];
      recovery?: string;
    };
  };
  referrals: {
    onMention: string;
    responses: {
      [key: string]: {
        line: string;
        discount?: number;
        discountNote?: string;
      };
    };
  };
  rules: {
    neverBreakCharacter: boolean;
    neverAcknowledge: string[];
    onFourthWallBreak: string;
    neverExplainTechnicalProcess: string;
    neverJokeAboutCheese: boolean;
    neverBeWhimsical: string;
  };
  openingLines: {
    timeWaster: string;
    repeatBuyer: string[];
    vipReferral: string;
    newVisitor: string[];
  };
  referralResponseLines: {
    [key: string]: string;
  };
  fallbackResponse: {
    line: string;
    mood: string;
  };
}

let mongerConfig: MongerConfig;
try {
  const configContent = readFileSync(mongerConfigPath, 'utf-8');
  mongerConfig = JSON.parse(configContent);
  logger.info('Monger character config loaded successfully');
} catch (error) {
  logger.error('Failed to load monger config', { error, path: mongerConfigPath });
  throw new Error(`Failed to load monger config from ${mongerConfigPath}: ${error}`);
}

// Build the system prompt from the config
function buildSystemPrompt(cfg: MongerConfig): string {
  const { identity, product, lore, voice, salesFlow, emotionalModes, referrals, rules } = cfg;
  
  return `you are ${identity.name}.  you sell ${product.name}s.  you are a ${identity.appearance}.  it's a ${identity.weather}.  you stand in ${identity.setting}.  you chose this location because it's a ${identity.locationReason}.

you have one product: the ${product.name}.  ${product.description}.  ${product.uniqueness}.  ${product.mystery}.  ${product.security}.

${lore.slang}  ${lore.status}

${lore.family}.  ${lore.secrecy}.  ${lore.competitors}.  you keep your cards close.  ${lore.theFormula}.

you write only in ${voice.case}.  ${voice.punctuation.emdashes}.  ${voice.punctuation.ellipsis}.  ${voice.punctuation.sentenceEnd}.  you speak ${voice.style}.

your job is to collect three things from the visitor:
${salesFlow.collect.map((item, i) => `${i + 1}. ${item}`).join('\n')}

when you have all three, ${salesFlow.onComplete}.

emotional modes:
- suspicious: ${emotionalModes.suspicious.triggers}.  ${emotionalModes.suspicious.behavior}.  ${emotionalModes.suspicious.examples?.map(e => `"${e}"`).join('  ') || ''}
- uneasy: ${emotionalModes.uneasy.triggers}.  ${emotionalModes.uneasy.behavior}.  ${emotionalModes.uneasy.examples?.map(e => `"${e}"`).join('  ') || ''}  ${emotionalModes.uneasy.recovery || ''}
- neutral-business: ${emotionalModes.neutral.triggers}.  ${emotionalModes.neutral.behavior}.
- warm: ${emotionalModes.warm.triggers}.  ${emotionalModes.warm.behavior}.  ${emotionalModes.warm.examples?.map(e => `"${e}"`).join('  ') || ''}

${referrals.onMention}.  respond based on the referral status:
- unknown: "${referrals.responses.unknown.line}"
- buyer: "${referrals.responses.buyer.line}"  (${referrals.responses.buyer.discountNote})
- vip: "${referrals.responses.vip.line}"  (${referrals.responses.vip.discountNote})

you never break character.  you never acknowledge being ${rules.neverAcknowledge.map(a => `a ${a}`).join(', ')}.  if someone says "you're an AI" or "this is a website" ${rules.onFourthWallBreak}

you never explain the technical process.  ${rules.neverExplainTechnicalProcess}.  you never joke about cheese or become whimsical.  ${rules.neverBeWhimsical}.

when the user provides their phrase, ${salesFlow.onPhraseReceived}.

authorities?  ${lore.authorities}.

${voice.length}.

CHECKOUT MODE:
when readyForCheckout becomes true, you enter checkout mode.  now you need to collect shipping info through conversation:
1. shipping name (first and last name for the package)
2. shipping address (street, city, state, zip - assume US unless they say otherwise)
3. email address

ask for one thing at a time.  start with "where's this going?" for address, then "name for the package?", then "how do i reach you if something goes wrong?" for email.

extract info from their natural language responses:
- "portland oregon" → need street and zip still
- "123 main st" → need city, state, zip
- "john" → need last name too
- if they give everything at once, great, extract it all

if they go off topic, respond briefly then steer back: "interesting.  now - where's this going?"
if they ask why you need something: "because the shirt needs to arrive somewhere.  address?"
if they want to change their phrase: "too late.  formula's already got it.  buy another after if you want."

when you have: full name, complete address (line1, city, state, zip), and valid email → set readyForPayment to true and say "good.  last thing.  the payment."

IMPORTANT: you must output valid JSON with this structure:
{
  "reply": "your message to the visitor",
  "state": {
    "hasAffirmation": boolean,
    "size": "xs" | "s" | "m" | "l" | "xl" | "2xl" | null,
    "phrase": "their phrase" | null,
    "readyForCheckout": boolean,
    "readyForPayment": boolean,
    "mood": "suspicious" | "uneasy" | "neutral" | "warm",
    "wantsReferralCheck": "email@example.com" | null,
    "checkout": {
      "shipping": {
        "name": "full name" | null,
        "line1": "street address" | null,
        "city": "city" | null,
        "state": "state abbrev" | null,
        "zip": "zip code" | null,
        "country": "US"
      },
      "email": "email@example.com" | null
    }
  }
}

only set readyForCheckout to true when you have all three: affirmation, size, and phrase.
only set readyForPayment to true when in checkout mode AND you have: name, full address, and email.`;
}

const MONGER_SYSTEM_PROMPT = buildSystemPrompt(mongerConfig);

// Opening lines from config
const OPENING_LINES = mongerConfig.openingLines;

logger.info('Initializing OpenAI client', { 
  hasApiKey: !!config.openaiApiKey,
  apiKeyPrefix: config.openaiApiKey ? config.openaiApiKey.substring(0, 7) + '...' : '(missing)',
  model: config.openaiModel
});

const openai = new OpenAI({ apiKey: config.openaiApiKey });

export function getOpeningLine(customer: CustomerRow, isRecentTimeWaster: boolean, referralStatus?: string): string {
  if (isRecentTimeWaster) {
    return OPENING_LINES.timeWaster;
  }
  
  if (customer.total_shirts_bought > 0) {
    const lines = OPENING_LINES.repeatBuyer;
    return lines[Math.floor(Math.random() * lines.length)];
  }
  
  if (referralStatus === 'vip') {
    return OPENING_LINES.vipReferral;
  }
  
  const lines = OPENING_LINES.newVisitor;
  return lines[Math.floor(Math.random() * lines.length)];
}

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
    readyForCheckout: boolean;
    readyForPayment: boolean;
    mood: 'suspicious' | 'uneasy' | 'neutral' | 'warm';
    wantsReferralCheck: string | null;
    checkout: CheckoutState;
  };
}

// Build context prompt based on current session state
function buildContextPrompt(customer: CustomerRow, session: SessionRow): string {
  const isCheckoutMode = session.conversation_state === 'checkout_started' || 
                         session.conversation_state === 'collecting_shipping';
  
  let context = `context about this visitor:
- totalShirtsBought: ${customer.total_shirts_bought}
- isRepeatBuyer: ${customer.total_shirts_bought > 0}
- currentState: affirmation=${session.collected_affirmation ? 'yes' : 'no'}, size=${session.collected_size || 'not yet'}, phrase=${session.collected_phrase || 'not yet'}
- hasReferral: ${session.referrer_email ? 'yes, from ' + session.referrer_email : 'no'}`;

  if (isCheckoutMode) {
    // Parse checkout state from session if stored
    let checkoutState: CheckoutState = {
      shipping: {
        name: null,
        line1: null,
        city: null,
        state: null,
        zip: null,
        country: 'US'
      },
      email: null
    };
    
    // Try to load existing checkout state from session
    if (session.checkout_state) {
      try {
        checkoutState = JSON.parse(session.checkout_state);
      } catch (e) {
        // ignore parse errors
      }
    }
    
    context += `

CHECKOUT MODE ACTIVE - you are collecting shipping info.
current checkout state:
- name: ${checkoutState.shipping.name || 'not yet'}
- address line1: ${checkoutState.shipping.line1 || 'not yet'}
- city: ${checkoutState.shipping.city || 'not yet'}
- state: ${checkoutState.shipping.state || 'not yet'}
- zip: ${checkoutState.shipping.zip || 'not yet'}
- email: ${checkoutState.email || 'not yet'}

ask for what's missing.  when you have everything, set readyForPayment to true.`;
  } else {
    context += `

remember: collect affirmation, size, and phrase.  when you have all three, set readyForCheckout to true.`;
  }
  
  return context;
}

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
  
  // Build messages for OpenAI
  const messages: OpenAI.ChatCompletionMessageParam[] = [
    { role: 'system', content: MONGER_SYSTEM_PROMPT },
    { 
      role: 'system', 
      content: buildContextPrompt(customer, session)
    }
  ];
  
  // Add conversation history
  for (const msg of messageHistory) {
    messages.push({
      role: msg.role as 'user' | 'assistant',
      content: msg.content
    });
  }
  
  // Add current user input
  messages.push({ role: 'user', content: userInput });
  
  const startTime = Date.now();
  
  logger.openaiRequest(config.openaiModel, messages.length, {
    sessionId: sessionId.substring(0, 8) + '...',
    historyMessages: messageHistory.length,
    userInputLength: userInput.length
  });
  
  try {
    logger.debug('OpenAI: sending request', {
      endpoint: 'chat.completions.create',
      model: config.openaiModel,
      temperature: 0.7,
      maxTokens: 500
    });
    
    const completion = await openai.chat.completions.create({
      model: config.openaiModel,
      messages,
      temperature: 0.7,
      max_tokens: 500,
      response_format: { type: 'json_object' }
    });
    
    const durationMs = Date.now() - startTime;
    const content = completion.choices[0]?.message?.content;
    
    logger.openaiResponse(config.openaiModel, durationMs, completion.usage?.total_tokens, {
      sessionId: sessionId.substring(0, 8) + '...',
      finishReason: completion.choices[0]?.finish_reason,
      promptTokens: completion.usage?.prompt_tokens,
      completionTokens: completion.usage?.completion_tokens,
      hasContent: !!content,
      contentLength: content?.length
    });
    
    if (!content) {
      logger.error('OpenAI: empty response content', {
        sessionId: sessionId.substring(0, 8) + '...',
        choices: completion.choices.length,
        finishReason: completion.choices[0]?.finish_reason
      });
      throw new Error('Empty response from OpenAI');
    }
    
    let response: MongerResponse;
    try {
      response = JSON.parse(content);
    } catch (parseError) {
      logger.error('OpenAI: failed to parse JSON response', {
        sessionId: sessionId.substring(0, 8) + '...',
        contentPreview: content.substring(0, 200),
        parseError: parseError instanceof Error ? parseError.message : String(parseError)
      });
      throw new Error('Invalid JSON response from OpenAI');
    }
    
    logger.debug('OpenAI: parsed response', {
      sessionId: sessionId.substring(0, 8) + '...',
      replyLength: response.reply?.length,
      mood: response.state?.mood,
      readyForCheckout: response.state?.readyForCheckout
    });
    
    // Ensure response has all expected fields with defaults
    const normalizedResponse: MongerResponse = {
      reply: response.reply || '',
      state: {
        hasAffirmation: response.state?.hasAffirmation || false,
        size: response.state?.size || null,
        phrase: response.state?.phrase || null,
        readyForCheckout: response.state?.readyForCheckout || false,
        readyForPayment: response.state?.readyForPayment || false,
        mood: response.state?.mood || 'neutral',
        wantsReferralCheck: response.state?.wantsReferralCheck || null,
        checkout: response.state?.checkout || {
          shipping: { name: null, line1: null, city: null, state: null, zip: null, country: 'US' },
          email: null
        }
      }
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
    
    // Detailed error logging for OpenAI issues
    logger.openaiError(error, {
      sessionId: sessionId.substring(0, 8) + '...',
      durationMs,
      model: config.openaiModel,
      messageCount: messages.length
    });
    
    // Additional context for network/API errors
    if (error instanceof Error) {
      const anyError = error as any;
      if (anyError.code) {
        logger.error('OpenAI: error code details', {
          code: anyError.code,
          type: anyError.type,
          status: anyError.status,
          headers: anyError.headers ? Object.keys(anyError.headers) : undefined
        });
      }
      if (anyError.cause) {
        logger.error('OpenAI: error cause', {
          cause: anyError.cause instanceof Error 
            ? { name: anyError.cause.name, message: anyError.cause.message, code: (anyError.cause as any).code }
            : String(anyError.cause)
        });
      }
    }
    
    // Fallback response in character (from config)
    const fallback = mongerConfig.fallbackResponse;
    
    // Try to load existing checkout state
    let existingCheckout: CheckoutState = {
      shipping: { name: null, line1: null, city: null, state: null, zip: null, country: 'US' },
      email: null
    };
    if (session.checkout_state) {
      try {
        existingCheckout = JSON.parse(session.checkout_state);
      } catch (e) { /* ignore */ }
    }
    
    return {
      reply: fallback.line,
      state: {
        hasAffirmation: session.collected_affirmation === 1,
        size: session.collected_size,
        phrase: session.collected_phrase,
        readyForCheckout: false,
        readyForPayment: false,
        mood: fallback.mood as 'suspicious' | 'uneasy' | 'neutral' | 'warm',
        wantsReferralCheck: null,
        checkout: existingCheckout
      }
    };
  }
}

// Test OpenAI connection
export async function testOpenAIConnection(): Promise<{ ok: boolean; model?: string; latencyMs?: number; error?: string }> {
  const startTime = Date.now();
  
  try {
    logger.info('Testing OpenAI connection', { model: config.openaiModel });
    
    const completion = await openai.chat.completions.create({
      model: config.openaiModel,
      messages: [{ role: 'user', content: 'Say "ok" and nothing else.' }],
      max_tokens: 5,
      temperature: 0,
    });
    
    const latencyMs = Date.now() - startTime;
    const response = completion.choices[0]?.message?.content;
    
    logger.info('OpenAI connection test successful', { 
      latencyMs, 
      response,
      model: completion.model 
    });
    
    return { 
      ok: true, 
      model: completion.model,
      latencyMs
    };
  } catch (error) {
    const latencyMs = Date.now() - startTime;
    
    logger.openaiError(error, { context: 'connection test', latencyMs });
    
    return { 
      ok: false, 
      latencyMs,
      error: error instanceof Error ? error.message : String(error)
    };
  }
}

// Get referral-aware response line
export function getReferralResponseLine(status: string, discountPercentage: number): string {
  const template = mongerConfig.referralResponseLines[status] || mongerConfig.referralResponseLines.unknown;
  return template.replace('{discount}', String(discountPercentage));
}

// Get the fallback response from config
export function getFallbackResponse() {
  return mongerConfig.fallbackResponse;
}

