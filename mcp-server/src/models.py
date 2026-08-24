"""
Pydantic models for Atlas Change Request Management
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime, UTC
from enum import Enum


class ChangeRequestStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    id: str
    title: str
    description: str
    assignee: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[str] = None


class ChangeRequest(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: ChangeRequestStatus = ChangeRequestStatus.DRAFT
    start_date: str
    end_date: str
    risk_level: RiskLevel = RiskLevel.LOW
    tasks: List[Task] = []
    created_at: str
    updated_at: str
    created_by: str = "system"
    environment: Optional[str] = "dev"
    approval_notes: Optional[str] = None
    close_reason: Optional[str] = None


# ---- Input / Request models ----

class CreateChangeRequestInput(BaseModel):
    title: str = Field(..., description="Title of the change request")
    description: Optional[str] = Field(None, description="Detailed description")
    start_date: str = Field(..., description="Start date in MM/DD/YYYY format")
    end_date: str = Field(..., description="End date in MM/DD/YYYY format")
    risk_level: Optional[str] = Field("low", description="Risk level: low, medium, high, critical")
    environment: Optional[str] = Field("dev", description="Target environment: dev, uit, prod")


class UpdateChangeRequestInput(BaseModel):
    change_id: str = Field(..., description="Change request ID, e.g. CHG123456")
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None
    approval_notes: Optional[str] = None


class AddTaskInput(BaseModel):
    change_id: str = Field(..., description="Change request ID")
    task_title: str = Field(..., description="Title of the task")
    task_description: str = Field(..., description="Detailed description of the task")
    assignee: Optional[str] = Field(None, description="Person assigned to the task")


class CloseChangeRequestInput(BaseModel):
    change_id: str = Field(..., description="Change request ID to close")
    reason: Optional[str] = Field("Change completed successfully", description="Reason for closing")


# ---- Response models ----

class AtlasApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None


class PipelineStage(str, Enum):
    CLIENT = "client"
    LLM_PROCESSING = "llm_processing"
    MCP_SERVER = "mcp_server"
    ATLAS_API = "atlas_api"
    COMPLETE = "complete"
    ERROR = "error"


class PipelineUpdate(BaseModel):
    stage: PipelineStage
    status: str  # "active", "complete", "error"
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class IntentType(str, Enum):
    CREATE_CHANGE_REQUEST = "create_change_request"
    UPDATE_CHANGE_REQUEST = "update_change_request"
    ADD_TASK = "add_task"
    CHECK_STATUS = "check_status"
    CLOSE_CHANGE_REQUEST = "close_change_request"
    LIST_CHANGE_REQUESTS = "list_change_requests"
    UNCLEAR = "unclear"


class ExtractedIntent(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    entities: dict = Field(default_factory=dict)
    clarification_needed: bool = False
    suggestions: List[str] = Field(default_factory=list)
    friendly_summary: str = ""


class ChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    environment: Optional[str] = "dev"


class ChatResponse(BaseModel):
    response: str
    intent: Optional[str] = None
    change_request: Optional[ChangeRequest] = None
    pipeline_stages: List[PipelineUpdate] = []
    session_id: Optional[str] = None

