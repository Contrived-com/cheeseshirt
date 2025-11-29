# Monger Service Architecture

## Goal: Character/Flow Isolation

The Monger service should be as self-contained as possible, allowing character, 
plot, and flow changes without touching `/api` or `/web`.

## Current Implementation (Partially Isolated)

### uiHints - IMPLEMENTED ✅

The Monger now controls UI behavior via `uiHints`:

```json
{
  "reply": "got it.  size large, phrase 'hello'.  we good?",
  "state": { ... },
  "uiHints": {
    "skipTypewriter": true,   // Monger decides when to skip typewriter
    "showPaymentForm": false, // Monger decides when to show payment
    "blocked": false,         // Monger decides if user is blocked
    "inputDisabled": false    // Monger can disable input
  }
}
```

**What this isolates:**
- Typewriter behavior (confirmation messages show instantly)
- Payment form visibility  
- User blocking
- Input state

**To change these behaviors**, only modify `/monger` - Web just reads hints.

### State Fields - STILL COUPLED

These fields are still understood by API/Web:
- `size`, `phrase`, `hasAffirmation` - cheeseshirt-specific
- `readyForCheckout`, `readyForPayment` - flow states
- `checkout.shipping.*`, `checkout.email` - for Stripe

## Future: Full Isolation

To fully isolate (e.g., for two-character handoff):

### Phase-Based Flow
```json
{
  "reply": "...",
  "phase": "collecting" | "confirming" | "checkout" | "payment",
  "productData": { ... },  // Opaque to API, passed to Stripe
  "checkoutData": { ... }, // Shipping/email for Stripe
  "uiHints": { ... }
}
```

### Migration Steps
1. ✅ Add `uiHints` - DONE
2. Add `phase` field to replace `readyForCheckout`/`readyForPayment`
3. Replace specific fields with generic `productData`
4. Update Stripe integration to use `productData` as metadata

## Current Isolation Summary

| Aspect | Isolated to /monger? | Notes |
|--------|---------------------|-------|
| Character personality | ✅ Yes | `config/monger.json` |
| Dialogue/prompts | ✅ Yes | `character.py` |
| LLM calls | ✅ Yes | `llm/` folder |
| UI behavior | ✅ Yes | via `uiHints` |
| Flow phases | ⚠️ Partial | API still checks `readyForCheckout` |
| Product fields | ❌ No | `size`, `phrase` hardcoded in API |

## Two-Character Example

To add a "lackey" character for checkout:

**With current system** (partial isolation):
1. Update Monger prompts to change character mid-flow ✅
2. Update Monger to set `uiHints` appropriately ✅
3. No API/Web changes needed for UI behavior ✅
4. BUT: still uses same `size`/`phrase`/`checkout` fields

**With full isolation** (future):
1. Monger sets `phase: "lackey_checkout"`
2. Monger populates `productData` with whatever the lackey collected
3. API just passes `productData` to Stripe
4. Complete character/flow flexibility

