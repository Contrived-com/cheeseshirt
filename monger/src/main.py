"""
Monger Service - FastAPI application.

This service handles all LLM interactions for the Monger character.
It talks to an LLM sidecar service (llm-openai, llm-ollama, etc.) via HTTP,
so the Monger doesn't need to know which LLM is actually being used.

Includes diagnostic mode for system introspection.
"""
import json
import logging
import sys
import httpx
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .stats import get_llm_stats
from .models import (
    ChatRequest,
    ChatResponse,
    MongerState,
    CheckoutState,
    ShippingAddress,
    UIHints,
    OpeningLineRequest,
    OpeningLineResponse,
    ReferralLineRequest,
    ReferralLineResponse,
    ReferralLookupRequest,
    ReferralLookupResponse,
    HealthResponse,
    VersionResponse,
    LogsResponse,
    DiagnosticChatRequest,
    DiagnosticChatResponse,
)
from .referrals import lookup_referral, get_network
from .character import (
    build_system_prompt,
    build_context_prompt,
    get_opening_line,
    get_referral_response_line,
    get_fallback_response,
    get_character_config,
)
from .llm import get_llm_client, LLMMessage


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


# Log file mappings for diagnostics
LOG_FILES = {
    "monger": "cheeseshirt-monger.log",
    "api": "cheeseshirt-api.log",
    "web": "cheeseshirt-web.log",
    "web-error": "cheeseshirt-web-error.log",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    logger.info("Monger service starting up")
    logger.info("LLM sidecar URL: %s", settings.llm_service_url)
    
    # Pre-load character config
    try:
        get_character_config()
        logger.info("Character config loaded successfully")
    except Exception as e:
        logger.error("Failed to load character config: %s", e)
        raise
    
    # Load referral network
    try:
        network = get_network()
        logger.info("Referral network loaded: %d referrers", len(network.referrers))
    except Exception as e:
        logger.warning("Failed to load referral network: %s", e)
    
    # Test LLM sidecar connection
    try:
        llm = get_llm_client()
        ok, error, latency_ms = await llm.health_check()
        if ok:
            logger.info("LLM sidecar connected: %s (%dms)", llm.model_name, latency_ms)
        else:
            logger.warning("LLM sidecar not ready: %s", error)
    except Exception as e:
        logger.warning("Could not connect to LLM sidecar: %s (will retry on requests)", e)
    
    yield
    
    # Shutdown
    logger.info("Monger service shutting down")


app = FastAPI(
    title="Monger Service",
    description="LLM-powered character service for the Monger",
    version=settings.version,
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


# =============================================================================
# Health & Version Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint. Tests the LLM connection and returns status."""
    llm = get_llm_client()
    ok, error, latency_ms = await llm.health_check()
    
    return HealthResponse(
        status="ok" if ok else "degraded",
        llm_provider="sidecar",
        llm_ok=ok,
        llm_model=llm.model_name if ok else None,
        llm_latency_ms=latency_ms,
        error=error,
    )


@app.get("/version", response_model=VersionResponse)
async def version():
    """Return version information for this service."""
    llm = get_llm_client()
    return VersionResponse(
        service="cheeseshirt-monger",
        version=settings.version,
        llm_provider="sidecar",
        llm_model=llm.model_name,
    )


@app.get("/stats")
async def llm_stats():
    """Return LLM call statistics."""
    stats = get_llm_stats()
    return stats.get_summary()


# =============================================================================
# Diagnostic Endpoints
# =============================================================================

@app.get("/diagnostic/logs/{service}")
async def get_service_logs(service: str, lines: int = 50) -> LogsResponse:
    """
    Get the last N lines from a service's log file.
    
    Services: monger, api, web, web-error
    """
    if service not in LOG_FILES:
        raise HTTPException(
            status_code=404, 
            detail=f"Unknown service '{service}'. Available: {list(LOG_FILES.keys())}"
        )
    
    log_file = LOG_FILES[service]
    log_path = Path(settings.logs_dir) / log_file
    
    if not log_path.exists():
        return LogsResponse(
            service=service,
            log_file=log_file,
            lines=0,
            content="",
            error=f"Log file not found: {log_path}",
        )
    
    try:
        # Read last N lines
        with open(log_path, "r") as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            content = "".join(last_lines)
        
        return LogsResponse(
            service=service,
            log_file=log_file,
            lines=len(last_lines),
            content=content,
        )
    except Exception as e:
        return LogsResponse(
            service=service,
            log_file=log_file,
            lines=0,
            content="",
            error=str(e),
        )


@app.get("/diagnostic/services")
async def get_all_services_status() -> dict:
    """Get health and version status of all services."""
    stats = get_llm_stats()
    llm_stats_summary = stats.get_summary()
    
    results = {
        "monger": {"health": None, "version": None, "llm_stats": llm_stats_summary},
        "api": {"health": None, "version": None},
        "web": {"health": None, "version": None},
    }
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Monger (self)
        try:
            llm = get_llm_client()
            ok, error, latency_ms = await llm.health_check()
            results["monger"]["health"] = {
                "status": "ok" if ok else "degraded",
                "llm_ok": ok,
                "llm_latency_ms": latency_ms,
                "error": error,
            }
            results["monger"]["version"] = {
                "version": settings.version,
                "llm_provider": "sidecar",
                "llm_model": llm.model_name,
            }
        except Exception as e:
            results["monger"]["health"] = {"status": "error", "error": str(e)}
        
        # API
        try:
            resp = await client.get(f"{settings.api_service_url}/api/health")
            results["api"]["health"] = resp.json()
        except Exception as e:
            results["api"]["health"] = {"status": "error", "error": str(e)}
        
        try:
            resp = await client.get(f"{settings.api_service_url}/api/version")
            results["api"]["version"] = resp.json()
        except Exception as e:
            results["api"]["version"] = {"error": str(e)}
        
        # Web
        try:
            resp = await client.get(f"{settings.web_service_url}/health")
            results["web"]["health"] = {
                "status": "ok" if resp.status_code == 200 else "error",
                "status_code": resp.status_code,
            }
        except Exception as e:
            results["web"]["health"] = {"status": "error", "error": str(e)}
        
        try:
            resp = await client.get(f"{settings.web_service_url}/version")
            results["web"]["version"] = resp.json()
        except Exception as e:
            results["web"]["version"] = {"error": str(e)}
    
    return results


@app.post("/diagnostic/chat", response_model=DiagnosticChatResponse)
async def diagnostic_chat(request: DiagnosticChatRequest):
    """
    Diagnostic mode chat - the Monger drops character and helps debug.
    
    The LLM has access to service status, versions, and can read logs.
    """
    logger.info("Diagnostic chat request: %s", request.user_input[:100])
    
    # Gather current system status
    services_status = await get_all_services_status()
    
    # Build diagnostic context
    diagnostic_context = f"""You are now in DIAGNOSTIC MODE. You are no longer the Monger character.
You are a helpful assistant for the cheeseshirt system administrator.

Current system status:
{json.dumps(services_status, indent=2)}

Available log files: {list(LOG_FILES.keys())}

You can help the admin by:
- Explaining the current status of services
- Suggesting troubleshooting steps
- Explaining what different components do
- Reading logs if asked (tell them to ask for specific logs like "show me the api logs")

If the user asks to see logs, respond with a JSON block like this to trigger log fetching:
{{"action": "fetch_logs", "service": "api", "lines": 50}}

Be helpful, technical, and concise. You're talking to a developer."""

    llm = get_llm_client()
    
    # Build messages
    messages = [
        LLMMessage(role="system", content=diagnostic_context),
    ]
    
    # Add conversation history
    for msg in request.conversation_history:
        messages.append(LLMMessage(role=msg.role, content=msg.content))
    
    # Add current user input
    messages.append(LLMMessage(role="user", content=request.user_input))
    
    try:
        response = await llm.chat(messages, json_mode=False)
        
        # Check if the response contains a log fetch request
        diagnostic_data = None
        reply = response.content
        
        # Look for JSON action blocks in the response
        if '{"action": "fetch_logs"' in reply:
            try:
                import re
                match = re.search(r'\{[^}]*"action":\s*"fetch_logs"[^}]*\}', reply)
                if match:
                    action = json.loads(match.group())
                    if action.get("action") == "fetch_logs":
                        service = action.get("service", "api")
                        lines = action.get("lines", 50)
                        logs = await get_service_logs(service, lines)
                        diagnostic_data = {"logs": logs.model_dump()}
                        # Remove the JSON from the reply and add log content
                        reply = re.sub(r'\{[^}]*"action":\s*"fetch_logs"[^}]*\}', '', reply)
                        reply = reply.strip() + f"\n\n--- {service} logs (last {logs.lines} lines) ---\n{logs.content}"
            except Exception as e:
                logger.warning("Failed to parse log fetch action: %s", e)
        
        return DiagnosticChatResponse(
            reply=reply,
            diagnostic_data=diagnostic_data or {"services": services_status},
        )
        
    except Exception as e:
        logger.error("Diagnostic chat error: %s", e, exc_info=True)
        return DiagnosticChatResponse(
            reply=f"Error processing diagnostic request: {str(e)}",
            diagnostic_data={"error": str(e)},
        )


# =============================================================================
# Character Chat Endpoints
# =============================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Get a response from the Monger.
    
    This endpoint handles the conversation with the Monger character,
    sending requests to the LLM sidecar service.
    """
    logger.debug(
        "Chat request: input_len=%d, history_len=%d, checkout_mode=%s",
        len(request.user_input),
        len(request.conversation_history),
        request.context.is_checkout_mode,
    )
    
    llm = get_llm_client()
    
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
        response = await llm.chat(messages, json_mode=True)
        
        # Parse the JSON response
        try:
            data = json.loads(response.content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            logger.error("Raw response (first 1000 chars): %s", response.content[:1000])
            logger.error("Raw response (last 500 chars): %s", response.content[-500:] if len(response.content) > 500 else response.content)
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
            pending_confirmation=state_data.get("pendingConfirmation", False),
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
        
        # Build UI hints based on state
        ui_hints = UIHints(
            skip_typewriter=monger_state.pending_confirmation,
            show_payment_form=monger_state.ready_for_payment,
            blocked=False,
            input_disabled=False,
        )
        
        return ChatResponse(reply=reply, state=monger_state, ui_hints=ui_hints)
        
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
                pending_confirmation=False,
                ready_for_checkout=False,
                ready_for_payment=False,
                mood=fallback.get("mood", "neutral"),
                wants_referral_check=None,
                checkout=checkout,
            ),
            ui_hints=UIHints(),  # Default hints for fallback
        )


@app.post("/opening-line", response_model=OpeningLineResponse)
async def opening_line(request: OpeningLineRequest):
    """Get an opening line for the Monger."""
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
    """Get the Monger's response to a referral lookup."""
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


@app.post("/referral-lookup", response_model=ReferralLookupResponse)
async def referral_lookup(request: ReferralLookupRequest):
    """
    Look up a referrer by name, email, or phone.
    
    The Monger knows his people. This searches the network:
    - Name: Fuzzy match (~80% similarity)
    - Email: Exact match
    - Phone: Normalized exact match
    
    Also finds 2nd-degree connections ("friend of a friend").
    """
    logger.debug("Referral lookup: query='%s'", request.query[:50] if request.query else "")
    
    match = lookup_referral(request.query)
    
    if not match:
        logger.debug("Referral lookup: not found")
        return ReferralLookupResponse(
            found=False,
            monger_line="never heard of em. no discount, but you can still get a shirt.",
        )
    
    # Build the Monger's response based on match type and tier
    if match.match_type == "friend_of":
        # 2nd-degree connection
        if match.relationship:
            monger_line = f"ah, {match.connected_through}'s {match.relationship}. friend of a friend. {match.discount}% off."
        else:
            monger_line = f"you know {match.connected_through}? alright, {match.discount}% off."
    else:
        # Direct connection
        if match.tier == "ultra":
            if match.nickname:
                monger_line = f"{match.nickname}. inner circle. {match.discount}% off, no questions."
            else:
                monger_line = f"{match.name.split()[0].lower()}. inner circle. {match.discount}% off, no questions."
        elif match.tier == "vip":
            monger_line = f"trusted buyer. {match.discount}% off."
        else:
            monger_line = f"known face. {match.discount}% off."
    
    logger.info(
        "Referral lookup: found %s (%s, %s, %d%%)",
        match.name,
        match.tier,
        match.match_type,
        match.discount,
    )
    
    return ReferralLookupResponse(
        found=True,
        referrer_id=match.referrer_id,
        name=match.name,
        nickname=match.nickname,
        tier=match.tier,
        discount=match.discount,
        purchases=match.purchases,
        match_type=match.match_type,
        match_method=match.match_method,
        connected_through=match.connected_through,
        relationship=match.relationship,
        monger_line=monger_line,
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
