"""
Monger Service - FastAPI application.

This service handles all LLM interactions for the Monger character.
It abstracts the underlying LLM provider, making it easy to swap between
OpenAI, local models, or other providers.
"""
import json
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models import (
    ChatRequest,
    ChatResponse,
    MongerState,
    CheckoutState,
    ShippingAddress,
    OpeningLineRequest,
    OpeningLineResponse,
    ReferralLineRequest,
    ReferralLineResponse,
    HealthResponse,
)
from .character import (
    build_system_prompt,
    build_context_prompt,
    get_opening_line,
    get_referral_response_line,
    get_fallback_response,
    get_character_config,
)
from .llm import get_llm_provider, LLMMessage


def setup_logging():
    """Configure logging with file and console handlers."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper())
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler (always)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if configured)
    if settings.log_path:
        try:
            log_path = Path(settings.log_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            root_logger.info(f"Logging to file: {log_path}")
        except Exception as e:
            root_logger.error(f"Failed to set up file logging: {e}")
    
    return logging.getLogger(__name__)


# Configure logging
settings = get_settings()
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    logger.info("Monger service starting up")
    logger.info("LLM provider: %s", settings.llm_provider)
    
    # Pre-load character config and LLM provider
    try:
        get_character_config()
        logger.info("Character config loaded successfully")
    except Exception as e:
        logger.error("Failed to load character config: %s", e)
        raise
    
    try:
        provider = get_llm_provider()
        logger.info("LLM provider initialized: %s (%s)", provider.provider_name, provider.model_name)
    except Exception as e:
        logger.error("Failed to initialize LLM provider: %s", e)
        raise
    
    yield
    
    # Shutdown
    logger.info("Monger service shutting down")


app = FastAPI(
    title="Monger Service",
    description="LLM-powered character service for the Monger",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Tests the LLM connection and returns status.
    """
    provider = get_llm_provider()
    ok, error, latency_ms = await provider.test_connection()
    
    return HealthResponse(
        status="ok" if ok else "degraded",
        llm_provider=provider.provider_name,
        llm_ok=ok,
        llm_model=provider.model_name if ok else None,
        llm_latency_ms=latency_ms,
        error=error,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Get a response from the Monger.
    
    This endpoint handles the conversation with the Monger character,
    using the configured LLM provider.
    """
    logger.debug(
        "Chat request: input_len=%d, history_len=%d, checkout_mode=%s",
        len(request.user_input),
        len(request.conversation_history),
        request.context.is_checkout_mode,
    )
    
    provider = get_llm_provider()
    
    # Build messages for the LLM
    messages = [
        LLMMessage(role="system", content=build_system_prompt()),
        LLMMessage(role="system", content=build_context_prompt(request.context)),
    ]
    
    # Add conversation history
    for msg in request.conversation_history:
        messages.append(LLMMessage(role=msg.role, content=msg.content))
    
    # Add current user input
    messages.append(LLMMessage(role="user", content=request.user_input))
    
    try:
        response = await provider.chat_completion(messages, json_mode=True)
        
        # Parse the JSON response
        try:
            data = json.loads(response.content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            logger.debug("Raw response: %s", response.content[:500])
            raise HTTPException(status_code=500, detail="Invalid response from LLM")
        
        # Extract and normalize the response
        reply = data.get("reply", "")
        state_data = data.get("state", {})
        
        # Build checkout state
        checkout_data = state_data.get("checkout", {})
        shipping_data = checkout_data.get("shipping", {})
        
        checkout_state = CheckoutState(
            shipping=ShippingAddress(
                name=shipping_data.get("name"),
                line1=shipping_data.get("line1"),
                city=shipping_data.get("city"),
                state=shipping_data.get("state"),
                zip=shipping_data.get("zip"),
                country=shipping_data.get("country", "US"),
            ),
            email=checkout_data.get("email"),
        )
        
        monger_state = MongerState(
            has_affirmation=state_data.get("hasAffirmation", False),
            size=state_data.get("size"),
            phrase=state_data.get("phrase"),
            ready_for_checkout=state_data.get("readyForCheckout", False),
            ready_for_payment=state_data.get("readyForPayment", False),
            mood=state_data.get("mood", "neutral"),
            wants_referral_check=state_data.get("wantsReferralCheck"),
            checkout=checkout_state,
        )
        
        logger.debug(
            "Chat response: mood=%s, ready_checkout=%s, ready_payment=%s",
            monger_state.mood,
            monger_state.ready_for_checkout,
            monger_state.ready_for_payment,
        )
        
        return ChatResponse(reply=reply, state=monger_state)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        
        # Return fallback response in character
        fallback = get_fallback_response()
        
        # Preserve existing state from context
        current = request.context.current_state
        checkout = request.context.checkout_state
        
        return ChatResponse(
            reply=fallback["line"],
            state=MongerState(
                has_affirmation=current.has_affirmation,
                size=current.size,
                phrase=current.phrase,
                ready_for_checkout=False,
                ready_for_payment=False,
                mood=fallback.get("mood", "neutral"),
                wants_referral_check=None,
                checkout=checkout,
            ),
        )


@app.post("/opening-line", response_model=OpeningLineResponse)
async def opening_line(request: OpeningLineRequest):
    """
    Get an opening line for the Monger.
    
    Returns an appropriate greeting based on customer history.
    """
    line = get_opening_line(
        total_shirts_bought=request.total_shirts_bought,
        is_time_waster=request.is_time_waster,
        referral_status=request.referral_status,
    )
    
    logger.debug(
        "Opening line: shirts=%d, time_waster=%s, referral=%s -> '%s...'",
        request.total_shirts_bought,
        request.is_time_waster,
        request.referral_status,
        line[:30],
    )
    
    return OpeningLineResponse(line=line)


@app.post("/referral-line", response_model=ReferralLineResponse)
async def referral_line(request: ReferralLineRequest):
    """
    Get the Monger's response to a referral lookup.
    
    Returns an appropriate line based on the referrer's status.
    """
    line = get_referral_response_line(
        status=request.status,
        discount_percentage=request.discount_percentage,
    )
    
    logger.debug(
        "Referral line: status=%s, discount=%d -> '%s...'",
        request.status,
        request.discount_percentage,
        line[:30],
    )
    
    return ReferralLineResponse(line=line)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )

