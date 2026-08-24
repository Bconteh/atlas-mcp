"""
Mock Atlas API client - simulates real Atlas change management API calls.
Replace mock implementations with actual HTTP calls when connecting to real Atlas.
"""
import asyncio
import json
import logging
import random
import string
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from .models import (
    AtlasApiResponse,
    ChangeRequest,
    ChangeRequestStatus,
    RiskLevel,
    Task,
    TaskStatus,
)
from .config import Settings

logger = logging.getLogger(__name__)

# In-memory store (replaces a real DB / Atlas API backend)
_CHANGE_REQUESTS: dict[str, dict] = {}
_initialized = False


def _load_mock_data() -> None:
    """Load mock change requests from JSON file into memory."""
    global _CHANGE_REQUESTS, _initialized
    if _initialized:
        return
    mock_file = Path(__file__).parent.parent / "mock_data" / "change_requests.json"
    with open(mock_file, "r") as f:
        data = json.load(f)
    for cr in data["change_requests"]:
        _CHANGE_REQUESTS[cr["id"]] = cr
    _initialized = True
    logger.info(f"Loaded {len(_CHANGE_REQUESTS)} mock change requests")


def _generate_change_id() -> str:
    """Generate a new CHG ID."""
    existing_ids = [int(k.replace("CHG", "")) for k in _CHANGE_REQUESTS if k.startswith("CHG")]
    next_id = max(existing_ids, default=123460) + 1
    return f"CHG{next_id}"


def _generate_task_id() -> str:
    suffix = "".join(random.choices(string.digits, k=3))
    return f"TASK-{suffix}"


async def _simulate_api_delay(min_ms: int = 100, max_ms: int = 400) -> None:
    """Simulate realistic API latency."""
    delay = random.uniform(min_ms / 1000, max_ms / 1000)
    await asyncio.sleep(delay)


class AtlasApiClient:
    """
    Client for the Atlas Change Management API.
    Currently uses in-memory mock data. Set `use_mock=False` and provide
    `base_url` + `api_key` to connect to the real Atlas API.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.use_mock = settings.atlas_use_mock
        self.base_url = settings.atlas_api_base_url
        self.api_key = settings.atlas_api_key
        _load_mock_data()

    async def create_change_request(
        self,
        title: str,
        description: Optional[str],
        start_date: str,
        end_date: str,
        risk_level: str = "low",
        environment: str = "dev",
    ) -> AtlasApiResponse:
        """Create a new change request in Atlas."""
        await _simulate_api_delay()

        if self.use_mock:
            change_id = _generate_change_id()
            now = datetime.now(UTC).isoformat() + "Z"
            new_cr: dict = {
                "id": change_id,
                "title": title,
                "description": description or "",
                "status": ChangeRequestStatus.OPEN.value,
                "start_date": start_date,
                "end_date": end_date,
                "risk_level": risk_level,
                "environment": environment,
                "created_by": "mcp-agent@example.com",
                "created_at": now,
                "updated_at": now,
                "approval_notes": None,
                "close_reason": None,
                "tasks": [],
            }
            _CHANGE_REQUESTS[change_id] = new_cr
            logger.info(f"[MOCK] Created change request {change_id}")
            return AtlasApiResponse(
                success=True,
                message=f"Change request {change_id} created successfully.",
                data=new_cr,
            )

        # Real API call (placeholder)
        raise NotImplementedError("Real Atlas API integration not yet configured.")

    async def get_change_request(self, change_id: str) -> AtlasApiResponse:
        """Retrieve a change request by ID."""
        await _simulate_api_delay(50, 200)

        if self.use_mock:
            cr = _CHANGE_REQUESTS.get(change_id.upper())
            if not cr:
                return AtlasApiResponse(
                    success=False,
                    message=f"Change request {change_id} not found.",
                    error="NOT_FOUND",
                )
            return AtlasApiResponse(
                success=True,
                message=f"Retrieved change request {change_id}.",
                data=cr,
            )

        raise NotImplementedError("Real Atlas API integration not yet configured.")

    async def update_change_request(
        self,
        change_id: str,
        updates: dict,
    ) -> AtlasApiResponse:
        """Update fields on an existing change request."""
        await _simulate_api_delay()

        if self.use_mock:
            cr = _CHANGE_REQUESTS.get(change_id.upper())
            if not cr:
                return AtlasApiResponse(
                    success=False,
                    message=f"Change request {change_id} not found.",
                    error="NOT_FOUND",
                )

            # Only update provided (non-None) fields
            allowed_fields = {
                "title", "description", "start_date", "end_date",
                "risk_level", "status", "approval_notes",
            }
            applied = []
            for field, value in updates.items():
                if field in allowed_fields and value is not None:
                    cr[field] = value
                    applied.append(field)

            cr["updated_at"] = datetime.now(UTC).isoformat() + "Z"
            logger.info(f"[MOCK] Updated {change_id}: {applied}")
            return AtlasApiResponse(
                success=True,
                message=f"Change request {change_id} updated. Fields changed: {', '.join(applied) or 'none'}.",
                data=cr,
            )

        raise NotImplementedError("Real Atlas API integration not yet configured.")

    async def add_task(
        self,
        change_id: str,
        task_title: str,
        task_description: str,
        assignee: Optional[str] = None,
    ) -> AtlasApiResponse:
        """Add a task to an existing change request."""
        await _simulate_api_delay()

        if self.use_mock:
            cr = _CHANGE_REQUESTS.get(change_id.upper())
            if not cr:
                return AtlasApiResponse(
                    success=False,
                    message=f"Change request {change_id} not found.",
                    error="NOT_FOUND",
                )

            task: dict = {
                "id": _generate_task_id(),
                "title": task_title,
                "description": task_description,
                "assignee": assignee,
                "status": TaskStatus.PENDING.value,
                "created_at": datetime.now(UTC).isoformat() + "Z",
            }
            cr["tasks"].append(task)
            cr["updated_at"] = datetime.now(UTC).isoformat() + "Z"
            logger.info(f"[MOCK] Added task {task['id']} to {change_id}")
            return AtlasApiResponse(
                success=True,
                message=f"Task '{task_title}' added to {change_id} (Task ID: {task['id']}).",
                data={"change_request": cr, "task": task},
            )

        raise NotImplementedError("Real Atlas API integration not yet configured.")

    async def close_change_request(
        self,
        change_id: str,
        reason: str = "Change completed successfully",
    ) -> AtlasApiResponse:
        """Close a change request."""
        await _simulate_api_delay()

        if self.use_mock:
            cr = _CHANGE_REQUESTS.get(change_id.upper())
            if not cr:
                return AtlasApiResponse(
                    success=False,
                    message=f"Change request {change_id} not found.",
                    error="NOT_FOUND",
                )

            if cr["status"] == ChangeRequestStatus.CLOSED.value:
                return AtlasApiResponse(
                    success=False,
                    message=f"Change request {change_id} is already closed.",
                    error="ALREADY_CLOSED",
                )

            cr["status"] = ChangeRequestStatus.CLOSED.value
            cr["close_reason"] = reason
            cr["updated_at"] = datetime.now(UTC).isoformat() + "Z"
            logger.info(f"[MOCK] Closed {change_id}: {reason}")
            return AtlasApiResponse(
                success=True,
                message=f"Change request {change_id} has been closed. Reason: {reason}",
                data=cr,
            )

        raise NotImplementedError("Real Atlas API integration not yet configured.")

    async def list_change_requests(
        self,
        status: Optional[str] = None,
        environment: Optional[str] = None,
        limit: int = 20,
    ) -> AtlasApiResponse:
        """List change requests, optionally filtered by status or environment."""
        await _simulate_api_delay(50, 150)

        if self.use_mock:
            results = list(_CHANGE_REQUESTS.values())
            if status:
                results = [r for r in results if r["status"] == status.lower()]
            if environment:
                results = [r for r in results if r.get("environment") == environment.lower()]
            results = results[:limit]
            return AtlasApiResponse(
                success=True,
                message=f"Found {len(results)} change request(s).",
                data={"change_requests": results, "total": len(results)},
            )

        raise NotImplementedError("Real Atlas API integration not yet configured.")

