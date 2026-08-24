"""
FastAPI HTTP bridge for the React UI client.
Exposes REST endpoints + SSE for real-time pipeline progress updates.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .atlas_client import AtlasApiClient
from .llm_processor import extract_intent, build_friendly_response
from .models import (
    ChatRequest,
    ChatResponse,
    IntentType,
    PipelineStage,
    PipelineUpdate,
)
from .config import get_cached_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Atlas Change Requests"])
settings = get_cached_settings()
atlas = AtlasApiClient(settings)


def _now() -> str:
    return datetime.now(UTC).isoformat() + "Z"


def _extract_cr(result) -> Optional[dict]:
    """
    Extract a ChangeRequest-compatible dict from an AtlasApiResponse.
    Handles the different data shapes returned by each API method:
      - create/update/get/close  → result.data IS the CR dict
      - add_task                 → result.data = {"change_request": {...}, "task": {...}}
      - list                     → result.data = {"change_requests": [...], "total": N}  → None
    """
    if not result or not result.success or not result.data:
        return None
    d = result.data
    if not isinstance(d, dict):
        return None
    if "change_requests" in d:
        return None  # list response — no single CR to show
    if "change_request" in d:
        return d["change_request"]  # add_task response
    return d  # direct CR dict


def _pipeline_event(stage: PipelineStage, status: str, message: str) -> str:
    """Format a Server-Sent Event payload."""
    update = PipelineUpdate(stage=stage, status=status, message=message)
    return f"data: {update.model_dump_json()}\n\n"


async def _process_request_stream(
    prompt: str,
    environment: str,
    session_id: str,
) -> AsyncGenerator[str, None]:
    """
    Process a change request prompt and yield SSE events for each pipeline stage:
      Client → LLM Processing → MCP Server → Atlas API → Complete
    """
    # Stage 1: Client received
    yield _pipeline_event(PipelineStage.CLIENT, "complete", "Request received")
    await asyncio.sleep(0.1)

    # Stage 2: LLM Processing
    yield _pipeline_event(PipelineStage.LLM_PROCESSING, "active", "Extracting intent from your request...")
    await asyncio.sleep(0.2)

    try:
        intent = await extract_intent(prompt, settings)
    except Exception as e:
        yield _pipeline_event(PipelineStage.LLM_PROCESSING, "error", f"LLM error: {str(e)}")
        yield _pipeline_event(PipelineStage.ERROR, "error", "Failed to process request")
        return

    yield _pipeline_event(
        PipelineStage.LLM_PROCESSING, "complete",
        f"Intent: {intent.intent.value.replace('_', ' ').title()} (confidence: {intent.confidence:.0%})"
    )

    # Stage 3: MCP Server routing
    yield _pipeline_event(PipelineStage.MCP_SERVER, "active", "Routing to the appropriate handler...")
    await asyncio.sleep(0.15)

    if intent.clarification_needed or intent.intent == IntentType.UNCLEAR:
        yield _pipeline_event(PipelineStage.MCP_SERVER, "complete", "Generating clarification response")
        friendly = build_friendly_response(intent, type("R", (), {"success": True, "message": "", "data": None})())
        yield _pipeline_event(PipelineStage.COMPLETE, "complete", "Done")
        result_payload = {
            "type": "result",
            "response": friendly,
            "intent": intent.intent.value,
            "clarification_needed": True,
            "suggestions": intent.suggestions,
            "change_request": None,
            "session_id": session_id,
        }
        yield f"data: {json.dumps(result_payload)}\n\n"
        return

    yield _pipeline_event(PipelineStage.MCP_SERVER, "complete", "Handler selected")

    # Stage 4: Atlas API
    yield _pipeline_event(PipelineStage.ATLAS_API, "active", "Calling Atlas API...")
    entities = intent.entities or {}
    env = entities.get("environment", environment)

    try:
        if intent.intent == IntentType.CREATE_CHANGE_REQUEST:
            result = await atlas.create_change_request(
                title=entities.get("title", "Untitled Change Request"),
                description=entities.get("description"),
                start_date=entities.get("start_date", ""),
                end_date=entities.get("end_date", ""),
                risk_level=entities.get("risk_level", "low"),
                environment=env,
            )
        elif intent.intent == IntentType.UPDATE_CHANGE_REQUEST:
            result = await atlas.update_change_request(
                change_id=entities.get("change_id", ""),
                updates={k: v for k, v in entities.items() if k != "change_id"},
            )
        elif intent.intent == IntentType.ADD_TASK:
            result = await atlas.add_task(
                change_id=entities.get("change_id", ""),
                task_title=entities.get("task_title", "New Task"),
                task_description=entities.get("task_description", ""),
                assignee=entities.get("assignee"),
            )
        elif intent.intent == IntentType.CHECK_STATUS:
            result = await atlas.get_change_request(entities.get("change_id", ""))
        elif intent.intent == IntentType.CLOSE_CHANGE_REQUEST:
            result = await atlas.close_change_request(
                change_id=entities.get("change_id", ""),
                reason=entities.get("close_reason", "Change completed successfully"),
            )
        elif intent.intent == IntentType.LIST_CHANGE_REQUESTS:
            result = await atlas.list_change_requests(
                status=entities.get("status"),
                environment=entities.get("environment"),
            )
        else:
            result = type("R", (), {"success": False, "message": "Unknown intent", "data": None})()

    except Exception as e:
        yield _pipeline_event(PipelineStage.ATLAS_API, "error", f"Atlas API error: {str(e)}")
        yield _pipeline_event(PipelineStage.ERROR, "error", "Failed to complete request")
        return

    api_status = "complete" if result.success else "error"
    yield _pipeline_event(PipelineStage.ATLAS_API, api_status, result.message)

    # Complete
    friendly_response = build_friendly_response(intent, result)
    yield _pipeline_event(PipelineStage.COMPLETE, "complete", "Request processed successfully")

    # Final result payload — extract the ChangeRequest dict from various response shapes
    cr_data = _extract_cr(result)

    result_payload = {
        "type": "result",
        "response": friendly_response,
        "intent": intent.intent.value,
        "clarification_needed": False,
        "suggestions": [],
        "change_request": cr_data,
        "session_id": session_id,
    }
    yield f"data: {json.dumps(result_payload)}\n\n"


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Process a chat prompt with real-time SSE pipeline progress updates.
    Yields Server-Sent Events for each pipeline stage.
    """
    session_id = request.session_id or str(uuid.uuid4())
    return StreamingResponse(
        _process_request_stream(request.prompt, request.environment or "dev", session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat prompt (non-streaming).
    Returns the full response after processing.
    """
    session_id = request.session_id or str(uuid.uuid4())
    intent = await extract_intent(request.prompt, settings)
    entities = intent.entities or {}
    env = entities.get("environment", request.environment or "dev")

    if intent.clarification_needed or intent.intent == IntentType.UNCLEAR:
        return ChatResponse(
            response=build_friendly_response(intent, type("R", (), {"success": True, "message": "", "data": None})()),
            intent=intent.intent.value,
            session_id=session_id,
        )

    result = None
    if intent.intent == IntentType.CREATE_CHANGE_REQUEST:
        result = await atlas.create_change_request(
            title=entities.get("title", "Untitled"),
            description=entities.get("description"),
            start_date=entities.get("start_date", ""),
            end_date=entities.get("end_date", ""),
            risk_level=entities.get("risk_level", "low"),
            environment=env,
        )
    elif intent.intent == IntentType.UPDATE_CHANGE_REQUEST:
        result = await atlas.update_change_request(
            change_id=entities.get("change_id", ""),
            updates={k: v for k, v in entities.items() if k != "change_id"},
        )
    elif intent.intent == IntentType.ADD_TASK:
        result = await atlas.add_task(
            change_id=entities.get("change_id", ""),
            task_title=entities.get("task_title", "New Task"),
            task_description=entities.get("task_description", ""),
            assignee=entities.get("assignee"),
        )
    elif intent.intent == IntentType.CHECK_STATUS:
        result = await atlas.get_change_request(entities.get("change_id", ""))
    elif intent.intent == IntentType.CLOSE_CHANGE_REQUEST:
        result = await atlas.close_change_request(
            change_id=entities.get("change_id", ""),
            reason=entities.get("close_reason", "Change completed successfully"),
        )
    elif intent.intent == IntentType.LIST_CHANGE_REQUESTS:
        result = await atlas.list_change_requests(
            status=entities.get("status"),
            environment=entities.get("environment"),
        )

    if not result:
        raise HTTPException(status_code=400, detail="Could not process request")

    return ChatResponse(
        response=build_friendly_response(intent, result),
        intent=intent.intent.value,
        change_request=_extract_cr(result),
        session_id=session_id,
    )


@router.get("/change-requests")
async def get_change_requests(status: Optional[str] = None, environment: Optional[str] = None):
    """List all change requests with optional filters."""
    result = await atlas.list_change_requests(status=status, environment=environment)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result.data


@router.get("/change-requests/{change_id}")
async def get_change_request(change_id: str):
    """Get a specific change request by ID."""
    result = await atlas.get_change_request(change_id)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    return result.data


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "atlas_mock": settings.atlas_use_mock,
    }

