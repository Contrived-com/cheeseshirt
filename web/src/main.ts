/**
 * cheeseshirt terminal interface
 * the monger awaits
 * 
 * conversational checkout: the Monger collects shipping info through chat,
 * only the payment card form appears as a UI element
 */

import { loadStripe, Stripe, StripeElements, StripePaymentElement } from '@stripe/stripe-js';

// Configuration
const API_BASE = '/api';
const CHAR_DELAY = 18; // ms between characters for typewriter effect
const THINKING_DELAY = 400; // minimum "thinking" time before response

// Stripe instance (loaded lazily)
let stripePromise: Promise<Stripe | null> | null = null;
let stripeConfig: { publishableKey: string; shirtPriceCents: number } | null = null;

// Checkout state from Monger
interface CheckoutShipping {
  name: string | null;
  line1: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  country: string;
}

interface CheckoutState {
  shipping: CheckoutShipping;
  email: string | null;
}

// State
interface SessionState {
  sessionId: string | null;
  customerId: string | null;
  isBlocked: boolean;
  isThinking: boolean;
  collectedSize: string | null;
  collectedPhrase: string | null;
  // Checkout state (from Monger's conversation)
  readyForCheckout: boolean;
  readyForPayment: boolean;
  checkout: CheckoutState;
  // Payment state
  paymentFormVisible: boolean;
  paymentIntentId: string | null;
  clientSecret: string | null;
  paymentProcessing: boolean;
  // Diagnostic mode (no typewriter, technical assistant)
  diagnosticMode: boolean;
}

const state: SessionState = {
  sessionId: null,
  customerId: null,
  isBlocked: false,
  isThinking: false,
  collectedSize: null,
  collectedPhrase: null,
  readyForCheckout: false,
  readyForPayment: false,
  checkout: {
    shipping: { name: null, line1: null, city: null, state: null, zip: null, country: 'US' },
    email: null
  },
  paymentFormVisible: false,
  paymentIntentId: null,
  clientSecret: null,
  paymentProcessing: false,
  diagnosticMode: false,
};

// Stripe elements
let elements: StripeElements | null = null;
let paymentElement: StripePaymentElement | null = null;

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
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.error || `API error: ${response.status}`);
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

// Load Stripe config and initialize
async function getStripe(): Promise<Stripe | null> {
  if (!stripePromise) {
    if (!stripeConfig) {
      stripeConfig = await apiGet<{ publishableKey: string; shirtPriceCents: number }>('/stripe/config');
    }
    stripePromise = loadStripe(stripeConfig.publishableKey);
  }
  return stripePromise;
}

// Format cents to dollars
function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
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
  if (!state.paymentFormVisible) {
    input.focus();
  }
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
    
    await addMessage(response.mongerOpeningLine, 'monger', true);
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
  
  // Don't allow chat while payment form is visible and processing
  if (state.paymentProcessing) {
    return;
  }
  
  const trimmedInput = userInput.trim();
  if (!trimmedInput) {
    return;
  }
  
  // Display user input
  await addMessage(trimmedInput, 'user', false);
  input.value = '';
  
  showThinking();
  const thinkingStart = Date.now();
  
  try {
    interface UIHints {
      skipTypewriter: boolean;
      showPaymentForm: boolean;
      blocked: boolean;
      inputDisabled: boolean;
    }
    
    interface ChatResponse {
      mongerReply: string;
      conversationState: string;
      needsSize: boolean;
      needsPhrase: boolean;
      needsAffirmation: boolean;
      pendingConfirmation: boolean;
      readyForCheckout: boolean;
      readyForPayment: boolean;
      wantsReferralCheck: string | null;
      mood: string;
      collectedSize: string | null;
      collectedPhrase: string | null;
      checkout: CheckoutState;
      diagnosticMode?: boolean;
      uiHints: UIHints;
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
    
    // Use uiHints from Monger to control behavior
    const hints = response.uiHints;
    
    // Check if blocked
    if (hints.blocked) {
      state.isBlocked = true;
      terminal.classList.add('blocked');
      await addMessage(response.mongerReply, 'monger', false);
      return;
    }
    
    // Update collected state
    if (response.collectedSize) state.collectedSize = response.collectedSize;
    if (response.collectedPhrase) state.collectedPhrase = response.collectedPhrase;
    state.readyForCheckout = response.readyForCheckout;
    state.readyForPayment = response.readyForPayment;
    state.checkout = response.checkout;
    
    // Track diagnostic mode
    if (response.diagnosticMode !== undefined) {
      state.diagnosticMode = response.diagnosticMode;
    }
    
    // Display Monger's reply (use skipTypewriter hint from Monger)
    const useTypewriter = !hints.skipTypewriter;
    await addMessage(response.mongerReply, 'monger', useTypewriter);
    
    // Handle referral lookup if needed
    if (response.wantsReferralCheck) {
      await handleReferralLookup(response.wantsReferralCheck);
    }
    
    // Show payment form if Monger says so
    if (hints.showPaymentForm && !state.paymentFormVisible) {
      await showPaymentForm();
    }
    
  } catch (error) {
    console.error('Chat error:', error);
    hideThinking();
    await addMessage('...signal dropped.  say that again.', 'monger', true);
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

// ============================================
// Payment Form (Card Only)
// ============================================

async function showPaymentForm(): Promise<void> {
  // Validate we have all checkout info
  const { shipping, email } = state.checkout;
  if (!shipping.name || !shipping.line1 || !shipping.city || !shipping.state || !shipping.zip || !email) {
    console.error('Missing checkout info', state.checkout);
    await addMessage("...something's wrong.  let me get your info again.  where's this going?", 'monger', true);
    state.readyForPayment = false;
    return;
  }
  
  // Load Stripe config
  if (!stripeConfig) {
    stripeConfig = await apiGet<{ publishableKey: string; shirtPriceCents: number }>('/stripe/config');
  }
  
  state.paymentFormVisible = true;
  
  // Create payment intent with collected info
  try {
    interface PaymentIntentResponse {
      clientSecret: string;
      paymentIntentId: string;
      amount: number;
      currency: string;
    }
    
    const response = await apiPost<PaymentIntentResponse>('/stripe/create-payment-intent', {
      sessionId: state.sessionId,
      size: state.collectedSize,
      phrase: state.collectedPhrase,
      email: email,
      customerName: shipping.name,
    });
    
    state.clientSecret = response.clientSecret;
    state.paymentIntentId = response.paymentIntentId;
    
    // Update payment intent with shipping address
    await apiPost('/stripe/update-shipping', {
      paymentIntentId: state.paymentIntentId,
      shipping: {
        name: shipping.name,
        address: {
          line1: shipping.line1,
          line2: '',
          city: shipping.city,
          state: shipping.state,
          postal_code: shipping.zip,
          country: shipping.country || 'US',
        },
      },
    });
    
    // Create and show the payment form
    const paymentForm = createPaymentForm();
    output.appendChild(paymentForm);
    terminalBody.scrollTop = terminalBody.scrollHeight;
    
    // Mount Stripe Elements
    await mountPaymentElement(response.clientSecret);
    
  } catch (error) {
    console.error('Failed to create payment:', error);
    await addMessage("...trouble with the register.  try again.", 'monger', true);
    state.paymentFormVisible = false;
  }
}

function createPaymentForm(): HTMLElement {
  const form = document.createElement('div');
  form.className = 'checkout-form';
  form.id = 'payment-form';
  
  form.innerHTML = `
    <div class="checkout-summary">
      <span class="checkout-summary-label">cheeseshirt - size ${state.collectedSize?.toUpperCase()}</span>
      <span class="checkout-summary-value">${formatPrice(stripeConfig!.shirtPriceCents)}</span>
    </div>
    
    <div class="checkout-section">
      <label class="checkout-label">the card</label>
      <div id="payment-element" class="stripe-element"></div>
    </div>
    
    <div class="checkout-error hidden" id="checkout-error"></div>
    
    <button class="checkout-submit" id="checkout-submit" type="button">
      do it
    </button>
    
    <span class="checkout-cancel" id="checkout-cancel">changed my mind</span>
  `;
  
  // Set up event listeners
  setTimeout(() => {
    document.getElementById('checkout-submit')?.addEventListener('click', handlePayment);
    document.getElementById('checkout-cancel')?.addEventListener('click', cancelPayment);
  }, 0);
  
  return form;
}

async function mountPaymentElement(clientSecret: string): Promise<void> {
  const stripe = await getStripe();
  if (!stripe) return;
  
  elements = stripe.elements({
    clientSecret,
    appearance: {
      theme: 'night',
      variables: {
        colorPrimary: '#2d5a3d',
        colorBackground: '#0a0a0a',
        colorText: '#c8c8c8',
        colorDanger: '#8b4444',
        fontFamily: '"IBM Plex Mono", monospace',
        borderRadius: '2px',
        fontSizeBase: '14px',
      },
      rules: {
        '.Input': {
          backgroundColor: '#0a0a0a',
          border: '1px solid #1a1a1a',
          color: '#e8e8e8',
          padding: '10px 12px',
        },
        '.Input:focus': {
          borderColor: '#2d5a3d',
          boxShadow: 'none',
        },
        '.Label': {
          color: '#666666',
          fontSize: '11px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        },
        '.Tab': {
          backgroundColor: '#0a0a0a',
          border: '1px solid #1a1a1a',
          color: '#666666',
        },
        '.Tab--selected': {
          backgroundColor: '#111111',
          borderColor: '#2d5a3d',
          color: '#c8c8c8',
        },
      },
    },
  });
  
  const paymentContainer = document.getElementById('payment-element');
  if (paymentContainer) {
    paymentElement = elements.create('payment', { layout: 'tabs' });
    paymentElement.mount(paymentContainer);
  }
}

async function handlePayment(): Promise<void> {
  const stripe = await getStripe();
  if (!stripe || !elements || !state.clientSecret) {
    showPaymentError('payment not ready.  try again.');
    return;
  }
  
  const submitBtn = document.getElementById('checkout-submit') as HTMLButtonElement;
  
  state.paymentProcessing = true;
  submitBtn.disabled = true;
  submitBtn.classList.add('processing');
  submitBtn.textContent = 'checking with my guy...';
  hidePaymentError();
  
  try {
    const { error, paymentIntent } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: window.location.href,
        receipt_email: state.checkout.email || undefined,
      },
      redirect: 'if_required',
    });
    
    if (error) {
      showPaymentError(error.message || "didn't go through.  try again.");
      submitBtn.disabled = false;
      submitBtn.classList.remove('processing');
      submitBtn.textContent = 'do it';
      state.paymentProcessing = false;
    } else if (paymentIntent && paymentIntent.status === 'succeeded') {
      await handlePaymentSuccess();
    } else {
      showPaymentError('processing...  wait a moment.');
      submitBtn.disabled = false;
      submitBtn.classList.remove('processing');
      submitBtn.textContent = 'do it';
      state.paymentProcessing = false;
    }
    
  } catch (error) {
    console.error('Payment error:', error);
    showPaymentError("something's wrong.  try again.");
    submitBtn.disabled = false;
    submitBtn.classList.remove('processing');
    submitBtn.textContent = 'do it';
    state.paymentProcessing = false;
  }
}

async function handlePaymentSuccess(): Promise<void> {
  // Remove payment form
  document.getElementById('payment-form')?.remove();
  
  // Reset state for potential second purchase
  state.paymentFormVisible = false;
  state.readyForCheckout = false;
  state.readyForPayment = false;
  state.clientSecret = null;
  state.paymentIntentId = null;
  state.paymentProcessing = false;
  state.collectedSize = null;
  state.collectedPhrase = null;
  state.checkout = {
    shipping: { name: null, line1: null, city: null, state: null, zip: null, country: 'US' },
    email: null
  };
  
  // Show success message
  await addMessage("good.  it's done.  the formula's already working on it.", 'monger', true);
  
  await new Promise(r => setTimeout(r, 1000));
  await addMessage("you want another layer while you're here?", 'monger', true);
  
  hideThinking();
}

async function cancelPayment(): Promise<void> {
  document.getElementById('payment-form')?.remove();
  
  state.paymentFormVisible = false;
  state.readyForPayment = false;
  state.clientSecret = null;
  state.paymentIntentId = null;
  state.paymentProcessing = false;
  
  await addMessage("...changed your mind?  fine.  i'll be here.", 'monger', true);
  hideThinking();
}

function showPaymentError(message: string): void {
  const errorEl = document.getElementById('checkout-error');
  if (errorEl) {
    errorEl.textContent = message;
    errorEl.classList.remove('hidden');
  }
}

function hidePaymentError(): void {
  const errorEl = document.getElementById('checkout-error');
  if (errorEl) {
    errorEl.classList.add('hidden');
  }
}

// ============================================
// Time Waster Handling
// ============================================

function markTimeWaster(): void {
  if (state.sessionId && !state.readyForPayment && !state.isBlocked && !state.paymentFormVisible) {
    const data = JSON.stringify({ sessionId: state.sessionId });
    navigator.sendBeacon(`${API_BASE}/mark-time-waster`, data);
  }
}

// ============================================
// Input Handling
// ============================================

function handleInput(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage(input.value);
  }
}

// ============================================
// Initialize
// ============================================

function init(): void {
  input.focus();
  showThinking();
  
  input.addEventListener('keydown', handleInput);
  
  terminal.addEventListener('click', (e) => {
    if ((e.target as HTMLElement).closest('.checkout-form')) return;
    if (!state.isBlocked && !state.isThinking && !state.paymentFormVisible) {
      input.focus();
    }
  });
  
  window.addEventListener('beforeunload', markTimeWaster);
  window.addEventListener('pagehide', markTimeWaster);
  
  initSession();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
