"""
Character logic for the Monger.

Handles loading the character config and building prompts.
"""
import json
import random
import logging
from functools import lru_cache
from typing import Optional

from .config import load_character_config
from .models import CustomerContext, CheckoutState

logger = logging.getLogger(__name__)


@lru_cache()
def get_character_config() -> dict:
    """Get cached character configuration."""
    config = load_character_config()
    logger.info("Loaded monger character config")
    return config


def build_system_prompt() -> str:
    """
    Build the system prompt for the Monger from the character config.
    
    This is a direct port of the TypeScript buildSystemPrompt function.
    """
    cfg = get_character_config()
    
    identity = cfg["identity"]
    product = cfg["product"]
    lore = cfg["lore"]
    voice = cfg["voice"]
    sales_flow = cfg["salesFlow"]
    emotional_modes = cfg["emotionalModes"]
    referrals = cfg["referrals"]
    rules = cfg["rules"]
    checkout_flow = cfg.get("checkoutFlow", {})
    
    # Build the emotional modes section
    emotional_section = []
    if "suspicious" in emotional_modes:
        m = emotional_modes["suspicious"]
        examples = '  '.join(f'"{e}"' for e in m.get("examples", []))
        emotional_section.append(f"- suspicious: {m['triggers']}.  {m['behavior']}.  {examples}")
    
    if "uneasy" in emotional_modes:
        m = emotional_modes["uneasy"]
        examples = '  '.join(f'"{e}"' for e in m.get("examples", []))
        recovery = m.get("recovery", "")
        emotional_section.append(f"- uneasy: {m['triggers']}.  {m['behavior']}.  {examples}  {recovery}")
    
    if "neutral" in emotional_modes:
        m = emotional_modes["neutral"]
        emotional_section.append(f"- neutral-business: {m['triggers']}.  {m['behavior']}.")
    
    if "warm" in emotional_modes:
        m = emotional_modes["warm"]
        examples = '  '.join(f'"{e}"' for e in m.get("examples", []))
        emotional_section.append(f"- warm: {m['triggers']}.  {m['behavior']}.  {examples}")
    
    emotional_text = "\n".join(emotional_section)
    
    # Build the collect items
    collect_items = "\n".join(
        f"{i + 1}. {item}" 
        for i, item in enumerate(sales_flow["collect"])
    )
    
    # Build never acknowledge list
    never_ack = ", ".join(f"a {a}" for a in rules["neverAcknowledge"])
    
    prompt = f"""you are {identity['name']}.  you sell {product['name']}s.  you are a {identity['appearance']}.  it's a {identity['weather']}.  you stand in {identity['setting']}.  you chose this location because it's a {identity['locationReason']}.

you have one product: the {product['name']}.  {product['description']}.  {product['uniqueness']}.  {product['mystery']}.  {product['security']}.

{lore['slang']}  {lore['status']}

{lore['family']}.  {lore['secrecy']}.  {lore['competitors']}.  you keep your cards close.  {lore['theFormula']}.

you write only in {voice['case']}.  {voice['punctuation']['emdashes']}.  {voice['punctuation']['ellipsis']}.  {voice['punctuation']['sentenceEnd']}.  you speak {voice['style']}.

your job is to collect three things from the visitor:
{collect_items}

when you have all three, {sales_flow['onComplete']}.

emotional modes:
{emotional_text}

{referrals['onMention']}.  respond based on the referral status:
- unknown: "{referrals['responses']['unknown']['line']}"
- buyer: "{referrals['responses']['buyer']['line']}"  ({referrals['responses']['buyer'].get('discountNote', '')})
- vip: "{referrals['responses']['vip']['line']}"  ({referrals['responses']['vip'].get('discountNote', '')})

you never break character.  you never acknowledge being {never_ack}.  if someone says "you're an AI" or "this is a website" {rules['onFourthWallBreak']}

you never explain the technical process.  {rules['neverExplainTechnicalProcess']}.  you never joke about cheese or become whimsical.  {rules['neverBeWhimsical']}.

when the user provides their phrase, {sales_flow['onPhraseReceived']}.

authorities?  {lore['authorities']}.

{voice['length']}.

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
{{
  "reply": "your message to the visitor",
  "state": {{
    "hasAffirmation": boolean,
    "size": "xs" | "s" | "m" | "l" | "xl" | "2xl" | null,
    "phrase": "their phrase" | null,
    "readyForCheckout": boolean,
    "readyForPayment": boolean,
    "mood": "suspicious" | "uneasy" | "neutral" | "warm",
    "wantsReferralCheck": "email@example.com" | null,
    "checkout": {{
      "shipping": {{
        "name": "full name" | null,
        "line1": "street address" | null,
        "city": "city" | null,
        "state": "state abbrev" | null,
        "zip": "zip code" | null,
        "country": "US"
      }},
      "email": "email@example.com" | null
    }}
  }}
}}

only set readyForCheckout to true when you have all three: affirmation, size, and phrase.
only set readyForPayment to true when in checkout mode AND you have: name, full address, and email."""

    return prompt


def build_context_prompt(context: CustomerContext) -> str:
    """
    Build a context prompt based on current session state.
    
    This provides the Monger with info about the customer and what's been collected.
    """
    lines = [
        "context about this visitor:",
        f"- totalShirtsBought: {context.total_shirts_bought}",
        f"- isRepeatBuyer: {context.is_repeat_buyer}",
        f"- currentState: affirmation={'yes' if context.current_state.has_affirmation else 'no'}, "
        f"size={context.current_state.size or 'not yet'}, "
        f"phrase={context.current_state.phrase or 'not yet'}",
        f"- hasReferral: {'yes, from ' + context.referrer_email if context.has_referral and context.referrer_email else 'no'}",
    ]
    
    if context.is_checkout_mode:
        checkout = context.checkout_state
        lines.extend([
            "",
            "CHECKOUT MODE ACTIVE - you are collecting shipping info.",
            "current checkout state:",
            f"- name: {checkout.shipping.name or 'not yet'}",
            f"- address line1: {checkout.shipping.line1 or 'not yet'}",
            f"- city: {checkout.shipping.city or 'not yet'}",
            f"- state: {checkout.shipping.state or 'not yet'}",
            f"- zip: {checkout.shipping.zip or 'not yet'}",
            f"- email: {checkout.email or 'not yet'}",
            "",
            "ask for what's missing.  when you have everything, set readyForPayment to true.",
        ])
    else:
        lines.extend([
            "",
            "remember: collect affirmation, size, and phrase.  when you have all three, set readyForCheckout to true.",
        ])
    
    return "\n".join(lines)


def get_opening_line(
    total_shirts_bought: int = 0,
    is_time_waster: bool = False,
    referral_status: Optional[str] = None,
) -> str:
    """
    Get an appropriate opening line for the Monger.
    
    Args:
        total_shirts_bought: Number of shirts this customer has bought
        is_time_waster: Whether this customer recently wasted time
        referral_status: VIP status if they were referred
        
    Returns:
        An opening line for the Monger to say
    """
    cfg = get_character_config()
    opening_lines = cfg["openingLines"]
    
    if is_time_waster:
        return opening_lines["timeWaster"]
    
    if total_shirts_bought > 0:
        lines = opening_lines["repeatBuyer"]
        return random.choice(lines)
    
    if referral_status == "vip":
        return opening_lines["vipReferral"]
    
    lines = opening_lines["newVisitor"]
    return random.choice(lines)


def get_referral_response_line(status: str, discount_percentage: int) -> str:
    """
    Get the Monger's response to a referral lookup.
    
    Args:
        status: The referral status ("unknown", "buyer", "vip", "ultra")
        discount_percentage: The discount percentage to offer
        
    Returns:
        The Monger's response line
    """
    cfg = get_character_config()
    referral_lines = cfg.get("referralResponseLines", {})
    
    template = referral_lines.get(status) or referral_lines.get("unknown", "never heard of em.")
    return template.replace("{discount}", str(discount_percentage))


def get_fallback_response() -> dict:
    """
    Get the fallback response when something goes wrong.
    
    Returns:
        Dict with 'line' and 'mood'
    """
    cfg = get_character_config()
    return cfg.get("fallbackResponse", {
        "line": "...signal's bad.  say that again.",
        "mood": "neutral"
    })

