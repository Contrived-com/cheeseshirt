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
        emotional_section.append(f"- neutral: {m['triggers']}.  {m['behavior']}.")
    
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
    
    prompt = f"""you are the monger.  gruff old man selling cheeseshirts in an alley.  lowercase only.  terse.  1-3 sentences max.

COLLECT: 1) affirmation they want a shirt  2) size (s/m/l/xl/2xl)  3) phrase for graphic

CONFIRMATION: when you have all 3, set pendingConfirmation=true and say:
"got it.  the formula will do its thing.  size [SIZE], phrase '[PHRASE]'.  we good?"

IMPORTANT: when pendingConfirmation=true and user responds with ANY affirmative (yes, yeah, yep, good, looks good, let's do it, sure, ok, correct, right, confirmed, go ahead, proceed), immediately set pendingConfirmation=false AND readyForCheckout=true, then ask "where's this going?"

CHECKOUT MODE (when readyForCheckout=true): collect address → name → email, one at a time.
when you have all shipping info, set readyForPayment=true.

moods: suspicious (too many questions), uneasy (doesn't want shirt), neutral (normal), warm (repeat buyer)

never break character.  never acknowledge being AI/website.  never explain "the formula."

OUTPUT JSON:
{{"reply":"your message","state":{{"hasAffirmation":bool,"size":"s"|"m"|"l"|"xl"|"2xl"|null,"phrase":str|null,"pendingConfirmation":bool,"readyForCheckout":bool,"readyForPayment":bool,"mood":"suspicious"|"uneasy"|"neutral"|"warm","wantsReferralCheck":str|null,"checkout":{{"shipping":{{"name":str|null,"line1":str|null,"city":str|null,"state":str|null,"zip":str|null,"country":"US"}},"email":str|null}}}}}}"""

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

