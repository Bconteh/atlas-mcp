"""
LLM-based intent extraction and natural language processing.
Uses OpenAI-compatible API (works with OpenAI, Azure OpenAI, GitHub Copilot, etc.)
"""
import json
import logging
import re
from typing import Optional

from .models import ExtractedIntent, IntentType
from .config import Settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an intelligent assistant for Atlas Change Request Management.
Your job is to extract the user's intent from their message about change requests.

You MUST respond with a valid JSON object following this schema:
{
  "intent": one of ["create_change_request", "update_change_request", "add_task", "check_status", "close_change_request", "list_change_requests", "unclear"],
  "confidence": float between 0.0 and 1.0,
  "entities": {
    "change_id": "CHG123456" (if mentioned),
    "title": "...",
    "description": "...",
    "start_date": "MM/DD/YYYY",
    "end_date": "MM/DD/YYYY",
    "risk_level": "low|medium|high|critical",
    "environment": "dev|uit|prod",
    "task_title": "...",
    "task_description": "...",
    "assignee": "...",
    "status": "...",
    "close_reason": "..."
  },
  "clarification_needed": true/false,
  "suggestions": ["suggestion 1", "suggestion 2"],
  "friendly_summary": "A clear, friendly description of what you understood"
}

Rules:
- If user says "create" or mentions a new change → create_change_request
- If user mentions a CHG ID and says "update", "change", "modify" → update_change_request
- If user says "add task", "add deployment task", "add step" → add_task
- If user asks "status", "what's the status", "check" → check_status
- If user says "close", "complete", "finish", "mark as closed" → close_change_request
- If user says "list", "show all", "show me" → list_change_requests
- If intent is unclear (e.g. no CHG ID for update, no dates for create), set clarification_needed=true
- Always include a friendly_summary explaining what you understood
- For dates, parse various formats (e.g. "July 4th 2026" → "07/04/2026")
- If no environment specified, default to "dev"
- Suggestions should be helpful next steps or clarifying questions
"""


def _build_llm_client(settings: Settings):
    """Build an OpenAI client (or Azure OpenAI if configured)."""
    try:
        from openai import AsyncOpenAI, AsyncAzureOpenAI

        if settings.azure_openai_endpoint:
            return AsyncAzureOpenAI(
                api_key=settings.llm_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
            )
        return AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_base_url if settings.llm_api_base_url != "https://api.openai.com/v1" else None,
        )
    except ImportError:
        logger.warning("openai package not installed; falling back to rule-based intent extraction")
        return None


async def extract_intent(user_prompt: str, settings: Settings) -> ExtractedIntent:
    """
    Extract intent from a user's natural language prompt.
    Uses LLM if available, falls back to rule-based parsing.
    """
    client = _build_llm_client(settings)

    if client and settings.llm_api_key not in ("your-llm-api-key-here", "", None):
        try:
            return await _llm_extract_intent(user_prompt, client, settings)
        except Exception as e:
            logger.warning(f"LLM extraction failed ({e}), falling back to rule-based")

    return _rule_based_extract_intent(user_prompt)


async def _llm_extract_intent(user_prompt: str, client, settings: Settings) -> ExtractedIntent:
    """Use LLM (OpenAI API) to extract intent."""
    response = await client.chat.completions.create(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    return ExtractedIntent(
        intent=IntentType(data.get("intent", "unclear")),
        confidence=float(data.get("confidence", 0.5)),
        entities=data.get("entities", {}),
        clarification_needed=data.get("clarification_needed", False),
        suggestions=data.get("suggestions", []),
        friendly_summary=data.get("friendly_summary", ""),
    )


def _rule_based_extract_intent(prompt: str) -> ExtractedIntent:
    """
    Fallback rule-based intent extraction when LLM is not available.
    Handles the sample prompts from the requirements.
    """
    p = prompt.lower()

    # Extract CHG ID
    chg_match = re.search(r"chg\s*(\d+)", p)
    change_id = f"CHG{chg_match.group(1)}" if chg_match else None

    # Extract dates (MM/DD/YYYY)
    dates = re.findall(r"\d{1,2}/\d{1,2}/\d{4}", prompt)

    # Extract title (text after "title" keyword or in quotes)
    title_match = re.search(r'title\s+(["\']?)(.+?)\1(?:\s*$|,)', prompt, re.IGNORECASE)
    title = title_match.group(2).strip() if title_match else None

    # Detect "add task" intent
    if any(kw in p for kw in ["add task", "add a task", "add deployment", "deployment task", "add step"]):
        task_parts = re.search(r"(?:for\s+)?(?:deploying|deployment of|deploy)\s+(.+?)(?:\s+app|\s+artifact|$)", p)
        task_desc = task_parts.group(0).strip() if task_parts else "Deployment task"
        return ExtractedIntent(
            intent=IntentType.ADD_TASK,
            confidence=0.9,
            entities={
                "change_id": change_id,
                "task_title": "Deployment Task",
                "task_description": task_desc,
            },
            clarification_needed=not change_id,
            suggestions=["Please specify the Change Request ID (e.g., CHG123456)"] if not change_id else [],
            friendly_summary=f"You want to add a deployment task to {change_id or 'a change request'}.",
        )

    # Detect close / status update to closed
    if any(kw in p for kw in ["close", "closed", "complete", "finish"]):
        if "status" in p or change_id:
            return ExtractedIntent(
                intent=IntentType.CLOSE_CHANGE_REQUEST,
                confidence=0.9,
                entities={"change_id": change_id},
                clarification_needed=not change_id,
                suggestions=["Please provide the Change Request ID to close"] if not change_id else [],
                friendly_summary=f"You want to close {change_id or 'a change request'}.",
            )

    # Detect status check
    if any(kw in p for kw in ["status", "what's the status", "check status", "how is", "progress"]):
        return ExtractedIntent(
            intent=IntentType.CHECK_STATUS,
            confidence=0.85,
            entities={"change_id": change_id},
            clarification_needed=not change_id,
            suggestions=["Please specify the Change Request ID (e.g., CHG123456)"] if not change_id else [],
            friendly_summary=f"You want to check the status of {change_id or 'a change request'}.",
        )

    # Detect create
    if any(kw in p for kw in ["create", "new change", "open a change", "submit a change", "raise a change"]):
        missing = []
        if not dates or len(dates) < 2:
            missing.append("start and end dates (e.g., 07/04/2026 - 07/06/2026)")
        if not title:
            missing.append("a title for the change request")

        return ExtractedIntent(
            intent=IntentType.CREATE_CHANGE_REQUEST,
            confidence=0.85,
            entities={
                "title": title,
                "start_date": dates[0] if len(dates) > 0 else None,
                "end_date": dates[1] if len(dates) > 1 else None,
            },
            clarification_needed=bool(missing),
            suggestions=[f"Please provide {m}" for m in missing],
            friendly_summary=f"You want to create a new change request"
                             + (f" titled '{title}'" if title else "")
                             + ".",
        )

    # Detect update
    if any(kw in p for kw in ["update", "modify", "change", "edit"]) and change_id:
        return ExtractedIntent(
            intent=IntentType.UPDATE_CHANGE_REQUEST,
            confidence=0.8,
            entities={"change_id": change_id},
            clarification_needed=False,
            friendly_summary=f"You want to update change request {change_id}.",
        )

    # Detect list
    if any(kw in p for kw in ["list", "show all", "show me", "get all"]):
        return ExtractedIntent(
            intent=IntentType.LIST_CHANGE_REQUESTS,
            confidence=0.8,
            entities={},
            clarification_needed=False,
            friendly_summary="You want to see a list of change requests.",
        )

    # Unclear
    return ExtractedIntent(
        intent=IntentType.UNCLEAR,
        confidence=0.3,
        entities={},
        clarification_needed=True,
        suggestions=[
            "Would you like to CREATE a new change request?",
            "Would you like to CHECK the STATUS of an existing change request?",
            "Would you like to UPDATE an existing change request?",
            "Would you like to ADD A TASK to a change request?",
            "Would you like to CLOSE a change request?",
        ],
        friendly_summary="I'm not sure what you'd like to do. Could you clarify?",
    )


def build_friendly_response(intent: ExtractedIntent, api_result) -> str:
    """Build a user-friendly response message from intent + API result."""

    if intent.clarification_needed:
        suggestions_text = "\n".join(f"  • {s}" for s in intent.suggestions)
        return (
            f"🤔 {intent.friendly_summary}\n\n"
            f"I need a bit more information to help you:\n{suggestions_text}"
        )

    if not api_result.success:
        return (
            f"❌ I encountered an issue: {api_result.message}\n\n"
            f"Please double-check the change request ID and try again."
        )

    action_emoji = {
        IntentType.CREATE_CHANGE_REQUEST: "✅",
        IntentType.UPDATE_CHANGE_REQUEST: "✏️",
        IntentType.ADD_TASK: "📋",
        IntentType.CHECK_STATUS: "🔍",
        IntentType.CLOSE_CHANGE_REQUEST: "🔒",
        IntentType.LIST_CHANGE_REQUESTS: "📄",
    }
    emoji = action_emoji.get(intent.intent, "ℹ️")

    if intent.intent == IntentType.CHECK_STATUS and api_result.data:
        cr = api_result.data
        status_emoji = {
            "open": "🟢", "in_progress": "🔄", "closed": "🔒",
            "draft": "📝", "pending_approval": "⏳", "cancelled": "❌",
        }
        s_emoji = status_emoji.get(cr.get("status", ""), "ℹ️")
        tasks = cr.get("tasks", [])
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        return (
            f"{emoji} **{cr['id']}: {cr['title']}**\n\n"
            f"  {s_emoji} Status: **{cr['status'].replace('_', ' ').title()}**\n"
            f"  📅 Window: {cr['start_date']} → {cr['end_date']}\n"
            f"  ⚠️ Risk: {cr['risk_level'].title()}\n"
            f"  🌍 Environment: {cr.get('environment', 'N/A').upper()}\n"
            f"  📋 Tasks: {completed}/{len(tasks)} completed\n"
            + (f"\n  📝 Approval notes: {cr['approval_notes']}" if cr.get("approval_notes") else "")
        )

    if intent.intent == IntentType.LIST_CHANGE_REQUESTS and api_result.data:
        crs = api_result.data.get("change_requests", [])
        if not crs:
            return "📄 No change requests found matching your criteria."
        lines = [f"📄 Found **{len(crs)}** change request(s):\n"]
        for cr in crs:
            lines.append(f"  • **{cr['id']}** - {cr['title']} [{cr['status']}]")
        return "\n".join(lines)

    return f"{emoji} {api_result.message}"

