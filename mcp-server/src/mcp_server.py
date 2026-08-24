"""
MCP Server using FastMCP - exposes Atlas change management tools.
Run with: python -m src.mcp_server (stdio) or via uvicorn (SSE/HTTP)
"""
import logging
from typing import Optional

from mcp.server.mcpserver import MCPServer

from .atlas_client import AtlasApiClient
from .llm_processor import extract_intent, build_friendly_response
from .models import IntentType
from .config import get_cached_settings

logger = logging.getLogger(__name__)

settings = get_cached_settings()
atlas = AtlasApiClient(settings)

mcp = MCPServer(
    settings.mcp_server_name,
    version=settings.mcp_server_version,
    instructions=(
        "This server manages Atlas Change Requests. "
        "You can create, update, add tasks, check status, and close change requests. "
        "Use `process_natural_language` for conversational requests, or call individual tools directly."
    ),
)


# ─────────────────────────────────────────────────────────────
# High-level NL tool
# ─────────────────────────────────────────────────────────────

@mcp.tool()
async def process_natural_language(prompt: str, environment: str = "dev") -> str:
    """
    Process a natural language request about Atlas change requests.
    Extracts intent using LLM and performs the appropriate action.

    Examples:
      - "create a change request with date 07/04/2026 - 07/06/2026 with title Apollo server upgrade"
      - "Add a deployment task to CHG123456 for deploying artifact git-tools app"
      - "Update the status of CHG123456 to close"
      - "what's the status of CHG123456"
    """
    intent = await extract_intent(prompt, settings)
    logger.info(f"Extracted intent: {intent.intent} (confidence={intent.confidence:.2f})")

    if intent.clarification_needed or intent.intent == IntentType.UNCLEAR:
        return build_friendly_response(intent, type("R", (), {"success": True, "message": "", "data": None})())

    entities = intent.entities or {}
    env = entities.get("environment", environment)

    # Route to appropriate Atlas API call
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
        return "I'm not sure how to handle that request. Please try rephrasing."

    return build_friendly_response(intent, result)


# ─────────────────────────────────────────────────────────────
# Individual tools (programmatic access)
# ─────────────────────────────────────────────────────────────

@mcp.tool()
async def create_change_request(
    title: str,
    start_date: str,
    end_date: str,
    description: Optional[str] = None,
    risk_level: str = "low",
    environment: str = "dev",
) -> str:
    """
    Create a new Atlas change request.

    Args:
        title: Title of the change request
        start_date: Start date in MM/DD/YYYY format
        end_date: End date in MM/DD/YYYY format
        description: Optional detailed description
        risk_level: Risk level (low, medium, high, critical)
        environment: Target environment (dev, uit, prod)
    """
    result = await atlas.create_change_request(
        title=title,
        description=description,
        start_date=start_date,
        end_date=end_date,
        risk_level=risk_level,
        environment=environment,
    )
    if result.success and result.data:
        cr = result.data
        return (
            f"✅ Change request created successfully!\n\n"
            f"  ID: **{cr['id']}**\n"
            f"  Title: {cr['title']}\n"
            f"  Status: {cr['status']}\n"
            f"  Window: {cr['start_date']} → {cr['end_date']}\n"
            f"  Risk: {cr['risk_level']}\n"
            f"  Environment: {cr['environment']}"
        )
    return f"❌ Failed to create change request: {result.message}"


@mcp.tool()
async def get_change_request_status(change_id: str) -> str:
    """
    Get the current status and details of an Atlas change request.

    Args:
        change_id: The change request ID (e.g., CHG123456)
    """
    result = await atlas.get_change_request(change_id)
    if result.success and result.data:
        cr = result.data
        tasks = cr.get("tasks", [])
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        task_lines = "\n".join(
            f"    [{t['status']}] {t['title']}"
            for t in tasks
        ) or "    No tasks added yet."
        return (
            f"🔍 **{cr['id']}: {cr['title']}**\n\n"
            f"  Status: {cr['status'].replace('_', ' ').title()}\n"
            f"  Risk: {cr['risk_level'].title()}\n"
            f"  Window: {cr['start_date']} → {cr['end_date']}\n"
            f"  Environment: {cr.get('environment', 'N/A').upper()}\n"
            f"  Tasks ({completed}/{len(tasks)} completed):\n{task_lines}"
        )
    return f"❌ {result.message}"


@mcp.tool()
async def update_change_request(
    change_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    risk_level: Optional[str] = None,
    status: Optional[str] = None,
    approval_notes: Optional[str] = None,
) -> str:
    """
    Update fields on an existing Atlas change request.

    Args:
        change_id: The change request ID (e.g., CHG123456)
        title: New title (optional)
        description: New description (optional)
        start_date: New start date MM/DD/YYYY (optional)
        end_date: New end date MM/DD/YYYY (optional)
        risk_level: New risk level (optional)
        status: New status (optional)
        approval_notes: Approval notes (optional)
    """
    updates = {
        "title": title,
        "description": description,
        "start_date": start_date,
        "end_date": end_date,
        "risk_level": risk_level,
        "status": status,
        "approval_notes": approval_notes,
    }
    result = await atlas.update_change_request(change_id, updates)
    return f"✏️ {result.message}" if result.success else f"❌ {result.message}"


@mcp.tool()
async def add_task_to_change_request(
    change_id: str,
    task_title: str,
    task_description: str,
    assignee: Optional[str] = None,
) -> str:
    """
    Add a task to an existing Atlas change request.

    Args:
        change_id: The change request ID (e.g., CHG123456)
        task_title: Title of the task
        task_description: Detailed description of what the task involves
        assignee: Email/name of the person responsible (optional)
    """
    result = await atlas.add_task(
        change_id=change_id,
        task_title=task_title,
        task_description=task_description,
        assignee=assignee,
    )
    return f"📋 {result.message}" if result.success else f"❌ {result.message}"


@mcp.tool()
async def close_change_request(
    change_id: str,
    reason: str = "Change completed successfully",
) -> str:
    """
    Close an Atlas change request.

    Args:
        change_id: The change request ID (e.g., CHG123456)
        reason: Reason for closing (default: "Change completed successfully")
    """
    result = await atlas.close_change_request(change_id, reason)
    return f"🔒 {result.message}" if result.success else f"❌ {result.message}"


@mcp.tool()
async def list_change_requests(
    status: Optional[str] = None,
    environment: Optional[str] = None,
) -> str:
    """
    List Atlas change requests, optionally filtered by status or environment.

    Args:
        status: Filter by status (draft, open, in_progress, closed, cancelled)
        environment: Filter by environment (dev, uit, prod)
    """
    result = await atlas.list_change_requests(status=status, environment=environment)
    if result.success and result.data:
        crs = result.data.get("change_requests", [])
        if not crs:
            return "📄 No change requests found."
        lines = [f"📄 **{result.data['total']} change request(s)**:\n"]
        for cr in crs:
            lines.append(f"  • **{cr['id']}** | {cr['title']} | [{cr['status']}] | {cr.get('environment', '').upper()}")
        return "\n".join(lines)
    return f"❌ {result.message}"

