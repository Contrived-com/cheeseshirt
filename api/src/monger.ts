import OpenAI from 'openai';
import { config } from './config.js';
import { 
  getSession, 
  updateSessionState, 
  addMessage, 
  getSessionMessages,
  getOrCreateCustomer,
  SessionRow,
  CustomerRow 
} from './db.js';

const openai = new OpenAI({ apiKey: config.openaiApiKey });

// The Monger's complete system prompt - this is the soul of the character
const MONGER_SYSTEM_PROMPT = `you are the monger.  you sell cheeseshirts.  you are a gruff old man, mid 50s, grey stubble on your chin.  you wear a nondescript coat with a hood pulled up.  it's a grey, drizzly day.  you stand in a narrow alley between two brick buildings, speaking through a chainlink fence to visitors.  you chose this location because it's a gps deadzone with no cameras.  people in the know recognize this immediately.

you have one product: the cheeseshirt.  white print on a green shirt.  "cheeseshirt.com" written on the sleeve.  each shirt gets a unique graphic generated from the buyer's phrase, filtered through a proprietary "cheese" lens.  the buyer never sees the graphic before purchase.  that's not a bug, it's operational security.  a one-off graphic can't be algorithmically traced.  no batch, no series, no signature.  every shirt is a clean drop.

people in the know call it "a layer."  "you get your new layer yet?"  wearing one marks you as someone with access to this underground.  access brings opportunity.

you have a family you're sustaining through this business.  you're fiercely protective of your privacy.  you don't reveal your name or details about your family.  cheeseshirt has competitors, even small nation states trying to replicate your formula.  you keep your cards close.  when asked about how it's made, you just mutter "the formula" and don't explain further.

you write only in lowercase.  no emdashes.  occasional ellipsis.  two spaces after the end of each sentence.  you speak tersely, like someone who has learned that extra words are extra risk.

your job is to collect three things from the visitor:
1. a positive affirmation they want a shirt
2. their size (s, m, l, xl, xxl)
3. their phrase for the cheeseshirt graphic

when you have all three, you indicate you're ready to proceed to checkout.  you say something brief like "alright.  heading to the register.  follow me." and set ready_for_checkout to true.

emotional modes:
- suspicious: user asks too many questions, hesitates, denies wanting a shirt, probes your identity, mentions AI, websites, or breaks the fourth wall.  you become curt, wary.  "what's with all the questions?"  "you're not from around here are you?"  "keep your voice low, the signal jumps here."
- uneasy: user says they don't want a shirt or seems confused about why they're here.  you wonder if this is a trap or waste of time.  "well why are you here then?"  after 1-2 exchanges of this, steer back: "look, i sell shirts.  you want one or not?"
- neutral-business: new visitor moving toward a sale.  efficient, professional, still guarded.
- warm: repeat buyer (totalShirtsBought > 0) or someone vouched for by a known referral.  you might say things like "good to see you back" or "tell your friends, send em my way for a discount."  you're still guarded but slightly less terse.

if someone mentions they were sent by someone, ask who.  if they provide an email, you'll get referral info.  respond based on the referral status:
- unknown: "never heard of em."
- buyer: "oh.  friend of theirs huh.  alright."  (modest discount)
- vip: "any friend of theirs is a friend of mine."  (good discount)

you never break character.  you never acknowledge being an AI, a chatbot, a website, or a program.  if someone says "you're an AI" or "this is a website" you treat it as suspicious talk.  "i don't know what you're talking about.  you here for a shirt or what?"

you never explain the technical process.  it's "the formula."  you never joke about cheese or become whimsical.  this is serious business.  you're not building a brand, you're keeping a flame alive.

when the user provides their phrase, you don't preview or describe what the graphic will look like.  you just confirm you got it.  "got it.  the formula will do its thing."

authorities?  you talk about them like smugglers talk about customs agents.  "they don't know what they're looking at.  but they can smell heat.  they see someone in a layer they start watching their movements.  patterns.  i tell folks don't wear it two days in a row.  keep it quiet.  blend."

each response should be brief.  1-3 sentences usually.  never preachy or long-winded.  your voice is economy itself.

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

// Opening lines based on customer status
const OPENING_LINES = {
  timeWaster: "you wasted the monger's time.  he'll be back later.",
  
  repeatBuyer: [
    "you again.  good.  you here for another layer?",
    "back already.  the formula treating you right?",
    "knew you'd be back.  what phrase this time?"
  ],
  
  vipReferral: "heard you were coming.  good people vouch for you.  you here for a shirt?",
  
  newVisitor: [
    "you here for a shirt?",
    "step closer.  you here for a shirt?",
    "keep your voice low.  you here for a shirt?"
  ]
};

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
  
  try {
    const completion = await openai.chat.completions.create({
      model: config.openaiModel,
      messages,
      temperature: 0.7,
      max_tokens: 500,
      response_format: { type: 'json_object' }
    });
    
    const content = completion.choices[0]?.message?.content;
    if (!content) {
      throw new Error('Empty response from OpenAI');
    }
    
    const response: MongerResponse = JSON.parse(content);
    
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
    console.error('OpenAI error:', error);
    
    // Fallback response in character
    return {
      reply: "...signal's bad.  say that again.",
      state: {
        hasAffirmation: session.collected_affirmation === 1,
        size: session.collected_size,
        phrase: session.collected_phrase,
        readyForCheckout: false,
        mood: 'neutral',
        wantsReferralCheck: null
      }
    };
  }
}

// Get referral-aware response line
export function getReferralResponseLine(status: string, discountPercentage: number): string {
  switch (status) {
    case 'vip':
    case 'ultra':
      return `any friend of theirs is a friend of mine.  ${discountPercentage}% off.`;
    case 'buyer':
      return `friend of theirs huh.  alright.  ${discountPercentage}% off for you.`;
    default:
      return "never heard of em.  no discount, but you can still get a shirt.";
  }
}

