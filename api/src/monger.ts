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

IMPORTANT: you must output valid JSON with this structure:
{
  "reply": "your message to the visitor",
  "state": {
    "hasAffirmation": boolean,
    "size": "s" | "m" | "l" | "xl" | "xxl" | null,
    "phrase": "their phrase" | null,
    "readyForCheckout": boolean,
    "mood": "suspicious" | "uneasy" | "neutral" | "warm",
    "wantsReferralCheck": "email@example.com" | null
  }
}

only set readyForCheckout to true when you have all three: affirmation, size, and phrase.`;
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

export interface MongerResponse {
  reply: string;
  state: {
    hasAffirmation: boolean;
    size: string | null;
    phrase: string | null;
    readyForCheckout: boolean;
    mood: 'suspicious' | 'uneasy' | 'neutral' | 'warm';
    wantsReferralCheck: string | null;
  };
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
      content: `context about this visitor:
- totalShirtsBought: ${customer.total_shirts_bought}
- isRepeatBuyer: ${customer.total_shirts_bought > 0}
- currentState: affirmation=${session.collected_affirmation ? 'yes' : 'no'}, size=${session.collected_size || 'not yet'}, phrase=${session.collected_phrase || 'not yet'}
- hasReferral: ${session.referrer_email ? 'yes, from ' + session.referrer_email : 'no'}

remember: collect affirmation, size, and phrase.  when you have all three, set readyForCheckout to true.`
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
    
    // Store messages
    addMessage(sessionId, 'user', userInput);
    addMessage(sessionId, 'assistant', response.reply);
    
    // Update session state
    updateSessionState(sessionId, {
      conversationState: response.state.readyForCheckout ? 'checkout' : 'conversation',
      collectedAffirmation: response.state.hasAffirmation,
      collectedSize: response.state.size,
      collectedPhrase: response.state.phrase,
    });
    
    return response;
    
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
    return {
      reply: fallback.line,
      state: {
        hasAffirmation: session.collected_affirmation === 1,
        size: session.collected_size,
        phrase: session.collected_phrase,
        readyForCheckout: false,
        mood: fallback.mood as 'suspicious' | 'uneasy' | 'neutral' | 'warm',
        wantsReferralCheck: null
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

