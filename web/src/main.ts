/**
 * cheeseshirt terminal interface
 * the monger awaits
 */

// Configuration
const API_BASE = '/api';
const CHAR_DELAY = 18; // ms between characters for typewriter effect
const THINKING_DELAY = 400; // minimum "thinking" time before response

// State
interface SessionState {
  sessionId: string | null;
  customerId: string | null;
  isBlocked: boolean;
  isThinking: boolean;
  readyForCheckout: boolean;
  collectedSize: string | null;
  collectedPhrase: string | null;
}

const state: SessionState = {
  sessionId: null,
  customerId: null,
  isBlocked: false,
  isThinking: false,
  readyForCheckout: false,
  collectedSize: null,
  collectedPhrase: null,
};

// DOM elements
const terminal = document.querySelector('.terminal') as HTMLElement;
const output = document.getElementById('output') as HTMLElement;
const input = document.getElementById('input') as HTMLInputElement;
const statusIndicator = document.getElementById('status') as HTMLElement;
const terminalBody = document.getElementById('terminal-body') as HTMLElement;

// API helpers
async function apiPost<T>(endpoint: string, data: object): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return response.json();
}

async function apiGet<T>(endpoint: string): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'GET',
    credentials: 'include',
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return response.json();
}

// Get cookie value
function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

// Typewriter effect
async function typeText(container: HTMLElement, text: string): Promise<void> {
  return new Promise((resolve) => {
    let index = 0;
    
    function typeNextChar() {
      if (index < text.length) {
        const char = text[index];
        const span = document.createElement('span');
        span.className = 'char';
        span.textContent = char;
        span.style.animationDelay = '0ms';
        container.appendChild(span);
        index++;
        
        // Scroll to bottom
        terminalBody.scrollTop = terminalBody.scrollHeight;
        
        setTimeout(typeNextChar, CHAR_DELAY);
      } else {
        resolve();
      }
    }
    
    typeNextChar();
  });
}

// Add a message to the output
async function addMessage(text: string, type: 'monger' | 'user' | 'system' | 'error', typewriter = true): Promise<void> {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${type}`;
  
  if (type === 'monger' && typewriter) {
    const typingSpan = document.createElement('span');
    typingSpan.className = 'typing';
    messageDiv.appendChild(typingSpan);
    output.appendChild(messageDiv);
    await typeText(typingSpan, text);
  } else {
    messageDiv.textContent = text;
    output.appendChild(messageDiv);
  }
  
  // Scroll to bottom
  terminalBody.scrollTop = terminalBody.scrollHeight;
}

// Show thinking indicator
function showThinking() {
  state.isThinking = true;
  statusIndicator.textContent = 'thinking';
  statusIndicator.className = 'terminal-status visible thinking';
  input.disabled = true;
  terminal.classList.add('disabled');
}

// Hide thinking indicator
function hideThinking() {
  state.isThinking = false;
  statusIndicator.className = 'terminal-status';
  input.disabled = false;
  terminal.classList.remove('disabled');
  input.focus();
}

// Initialize session
async function initSession(): Promise<void> {
  try {
    const cookieId = getCookie('cheeseshirt_id');
    
    interface InitResponse {
      sessionId: string;
      customerId: string;
      mongerOpeningLine: string;
      isRecentTimeWaster: boolean;
      isRepeatCustomer: boolean;
      recentOrdersCount: number;
    }
    
    const response = await apiPost<InitResponse>('/session/init', {
      cookieId: cookieId || undefined,
    });
    
    state.sessionId = response.sessionId;
    state.customerId = response.customerId;
    
    if (response.isRecentTimeWaster) {
      state.isBlocked = true;
      terminal.classList.add('blocked');
      await addMessage(response.mongerOpeningLine, 'monger', false);
      return;
    }
    
    // Display opening line with typewriter effect
    await addMessage(response.mongerOpeningLine, 'monger', true);
    
    // Enable input
    hideThinking();
    
  } catch (error) {
    console.error('Failed to init session:', error);
    await addMessage('connection lost.  try again later.', 'error', false);
  }
}

// Send message to the Monger
async function sendMessage(userInput: string): Promise<void> {
  if (!state.sessionId || state.isBlocked || state.isThinking) {
    return;
  }
  
  const trimmedInput = userInput.trim();
  if (!trimmedInput) {
    return;
  }
  
  // Display user input
  await addMessage(trimmedInput, 'user', false);
  
  // Clear input
  input.value = '';
  
  // Show thinking
  showThinking();
  
  // Minimum thinking delay for effect
  const thinkingStart = Date.now();
  
  try {
    interface ChatResponse {
      mongerReply: string;
      conversationState: string;
      needsSize: boolean;
      needsPhrase: boolean;
      needsAffirmation: boolean;
      readyForCheckout: boolean;
      wantsReferralCheck: string | null;
      mood: string;
      collectedSize: string | null;
      collectedPhrase: string | null;
    }
    
    const response = await apiPost<ChatResponse>('/chat', {
      sessionId: state.sessionId,
      userInput: trimmedInput,
    });
    
    // Wait for minimum thinking time
    const elapsed = Date.now() - thinkingStart;
    if (elapsed < THINKING_DELAY) {
      await new Promise(r => setTimeout(r, THINKING_DELAY - elapsed));
    }
    
    hideThinking();
    
    // Check if blocked
    if (response.conversationState === 'blocked') {
      state.isBlocked = true;
      terminal.classList.add('blocked');
      await addMessage(response.mongerReply, 'monger', false);
      return;
    }
    
    // Display Monger's reply
    await addMessage(response.mongerReply, 'monger', true);
    
    // Update collected state from response
    if (response.collectedSize) {
      state.collectedSize = response.collectedSize;
    }
    if (response.collectedPhrase) {
      state.collectedPhrase = response.collectedPhrase;
    }
    
    // Handle referral lookup if needed
    if (response.wantsReferralCheck) {
      await handleReferralLookup(response.wantsReferralCheck);
    }
    
    // Handle checkout
    if (response.readyForCheckout) {
      state.readyForCheckout = true;
      await handleCheckout();
    }
    
  } catch (error) {
    console.error('Chat error:', error);
    hideThinking();
    await addMessage('...signal dropped.  say that again.', 'monger', true);
  }
}

// Update collected state from session
async function updateCollectedState(): Promise<void> {
  if (!state.sessionId) return;
  
  try {
    interface SessionInfo {
      size: string | null;
      phrase: string | null;
    }
    
    const response = await apiGet<SessionInfo>(`/session/${state.sessionId}`);
    
    if (response.size) {
      state.collectedSize = response.size;
    }
    if (response.phrase) {
      state.collectedPhrase = response.phrase;
    }
  } catch {
    // Ignore - we'll get the info at checkout time
  }
}

// Handle referral lookup
async function handleReferralLookup(email: string): Promise<void> {
  try {
    interface ReferralResponse {
      referrerStatus: string;
      discountPercentage: number;
      mongerLine: string;
    }
    
    const response = await apiPost<ReferralResponse>('/referral-lookup', {
      sessionId: state.sessionId,
      referrerEmail: email,
    });
    
    await addMessage(response.mongerLine, 'monger', true);
    
  } catch (error) {
    console.error('Referral lookup error:', error);
  }
}

// Handle checkout redirect
async function handleCheckout(): Promise<void> {
  try {
    // Fetch session to ensure we have collected data
    if (!state.collectedSize || !state.collectedPhrase) {
      await updateCollectedState();
    }
    
    // Validate we have required data
    if (!state.collectedSize || !state.collectedPhrase) {
      console.error('Missing size or phrase for checkout');
      await addMessage('...hold on.  need your size and phrase first.', 'monger', true);
      state.readyForCheckout = false;
      return;
    }
    
    // Small delay before showing system message
    await new Promise(r => setTimeout(r, 500));
    
    await addMessage('[redirecting to checkout...]', 'system', false);
    
    // Create checkout
    interface CheckoutResponse {
      checkoutUrl: string;
    }
    
    const checkoutResponse = await apiPost<CheckoutResponse>('/create-checkout', {
      sessionId: state.sessionId,
      size: state.collectedSize,
      phrase: state.collectedPhrase,
    });
    
    // Redirect to Shopify checkout
    window.location.href = checkoutResponse.checkoutUrl;
    
  } catch (error) {
    console.error('Checkout error:', error);
    await addMessage('...trouble with the register.  try again.', 'monger', true);
    state.readyForCheckout = false;
  }
}

// Mark session as time-wasted if user leaves without buying
function markTimeWaster(): void {
  if (state.sessionId && !state.readyForCheckout && !state.isBlocked) {
    // Use sendBeacon for reliability on page unload
    const data = JSON.stringify({ sessionId: state.sessionId });
    navigator.sendBeacon(`${API_BASE}/mark-time-waster`, data);
  }
}

// Input handling
function handleInput(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage(input.value);
  }
}

// Initialize
function init(): void {
  // Focus input
  input.focus();
  
  // Show initial thinking state
  showThinking();
  
  // Bind events
  input.addEventListener('keydown', handleInput);
  
  // Click anywhere in terminal focuses input
  terminal.addEventListener('click', () => {
    if (!state.isBlocked && !state.isThinking) {
      input.focus();
    }
  });
  
  // Mark as time waster on page leave (if no purchase)
  window.addEventListener('beforeunload', markTimeWaster);
  window.addEventListener('pagehide', markTimeWaster);
  
  // Start session
  initSession();
}

// Run when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

