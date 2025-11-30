"""
Pydantic models for the monger service API.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ShippingAddress(BaseModel):
    """Shipping address collected during checkout."""
    name: Optional[str] = None
    line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: str = "US"


class CheckoutState(BaseModel):
    """Checkout state collected through conversation."""
    shipping: ShippingAddress = Field(default_factory=ShippingAddress)
    email: Optional[str] = None


class ConversationMessage(BaseModel):
    """A single message in the conversation history."""
    role: Literal["user", "assistant"]
    content: str


class CurrentState(BaseModel):
    """Current state of what's been collected from the visitor."""
    has_affirmation: bool = False
    size: Optional[str] = None
    phrase: Optional[str] = None


class CustomerContext(BaseModel):
    """Context about the customer for the Monger to use."""
    total_shirts_bought: int = 0
    is_repeat_buyer: bool = False
    last_purchase_at: Optional[str] = None  # ISO timestamp of last purchase
    is_blocked: bool = False  # Time-waster blocked status (from cookie)
    blocked_until: Optional[str] = None  # When the block expires
    current_state: CurrentState = Field(default_factory=CurrentState)
    has_referral: bool = False
    referrer_email: Optional[str] = None
    is_checkout_mode: bool = False
    checkout_state: CheckoutState = Field(default_factory=CheckoutState)


class ChatRequest(BaseModel):
    """Request to the /chat endpoint."""
    user_input: str
    context: CustomerContext
    conversation_history: list[ConversationMessage] = Field(default_factory=list)


class MongerState(BaseModel):
    """State returned by the Monger after processing input."""
    has_affirmation: bool = False
    size: Optional[str] = None
    phrase: Optional[str] = None
    pending_confirmation: bool = False
    ready_for_checkout: bool = False
    ready_for_payment: bool = False
    mood: Literal["suspicious", "uneasy", "neutral", "warm"] = "neutral"
    wants_referral_check: Optional[str] = None
    checkout: CheckoutState = Field(default_factory=CheckoutState)


class UIHints(BaseModel):
    """
    UI behavior hints from the Monger.
    
    This allows the Monger to control presentation without the frontend
    needing to understand the underlying state. Keeps UI logic in Monger.
    """
    skip_typewriter: bool = False  # Display reply instantly (e.g., confirmations)
    show_payment_form: bool = False  # Time to collect payment
    blocked: bool = False  # User is blocked/banned
    input_disabled: bool = False  # Disable user input temporarily


class ChatResponse(BaseModel):
    """Response from the /chat endpoint."""
    reply: str
    state: MongerState
    ui_hints: UIHints = Field(default_factory=UIHints)


class OpeningLineRequest(BaseModel):
    """Request for an opening line."""
    total_shirts_bought: int = 0
    is_time_waster: bool = False
    referral_status: Optional[str] = None


class OpeningLineResponse(BaseModel):
    """Response with an opening line."""
    line: str


class ReferralLineRequest(BaseModel):
    """Request for a referral response line."""
    status: str
    discount_percentage: int


class ReferralLineResponse(BaseModel):
    """Response with a referral line."""
    line: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    llm_provider: str
    llm_ok: bool
    llm_model: Optional[str] = None
    llm_latency_ms: Optional[int] = None
    error: Optional[str] = None


class VersionResponse(BaseModel):
    """Version information response."""
    service: str
    version: str
    llm_provider: str
    llm_model: str


class ServiceHealth(BaseModel):
    """Health status of a single service."""
    service: str
    status: str
    url: str
    error: Optional[str] = None


class ServiceVersion(BaseModel):
    """Version info of a single service."""
    service: str
    version: Optional[str] = None
    error: Optional[str] = None


class LogsResponse(BaseModel):
    """Response containing log file contents."""
    service: str
    log_file: str
    lines: int
    content: str
    error: Optional[str] = None


class DiagnosticsResponse(BaseModel):
    """Full diagnostics report."""
    services: dict
    versions: dict
    logs: dict


class DiagnosticChatRequest(BaseModel):
    """Request for diagnostic mode chat."""
    user_input: str
    conversation_history: list[ConversationMessage] = Field(default_factory=list)


class DiagnosticChatResponse(BaseModel):
    """Response from diagnostic mode chat."""
    reply: str
    diagnostic_data: Optional[dict] = None


# =============================================================================
# Referral Lookup Models
# =============================================================================

class ReferralLookupRequest(BaseModel):
    """Request to look up a referrer by name, email, or phone."""
    query: str  # Name (fuzzy), email (exact), or phone (exact)


class ReferralLookupResponse(BaseModel):
    """Response from referral lookup."""
    found: bool
    referrer_id: Optional[str] = None
    name: Optional[str] = None
    nickname: Optional[str] = None
    tier: Optional[str] = None  # ultra, vip, buyer, friend_of
    discount: int = 0
    purchases: int = 0
    match_type: Optional[str] = None  # direct or friend_of
    match_method: Optional[str] = None  # name, email, phone
    connected_through: Optional[str] = None  # For friend_of matches
    relationship: Optional[str] = None  # e.g., "sister", "coworker"
    monger_line: str = ""  # The Monger's reaction

