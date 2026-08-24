// ─── Domain types ─────────────────────────────────────────────────────────────

export type ChangeRequestStatus =
  | 'draft'
  | 'open'
  | 'in_progress'
  | 'pending_approval'
  | 'approved'
  | 'closed'
  | 'cancelled'

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'
export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed'

export interface Task {
  id: string
  title: string
  description: string
  assignee?: string
  status: TaskStatus
  created_at?: string
}

export interface ChangeRequest {
  id: string
  title: string
  description?: string
  status: ChangeRequestStatus
  start_date: string
  end_date: string
  risk_level: RiskLevel
  tasks: Task[]
  created_at: string
  updated_at: string
  created_by: string
  environment?: string
  approval_notes?: string
  close_reason?: string
}

// ─── Pipeline types ────────────────────────────────────────────────────────────

export type PipelineStage =
  | 'client'
  | 'llm_processing'
  | 'mcp_server'
  | 'atlas_api'
  | 'complete'
  | 'error'

export type StageStatus = 'idle' | 'active' | 'complete' | 'error'

export interface PipelineUpdate {
  stage: PipelineStage
  status: StageStatus
  message: string
  timestamp: string
}

export interface PipelineState {
  client: StageStatus
  llm_processing: StageStatus
  mcp_server: StageStatus
  atlas_api: StageStatus
  complete: StageStatus
  messages: Record<PipelineStage, string>
}

// ─── Chat types ────────────────────────────────────────────────────────────────

export type MessageRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: Date
  intent?: string
  changeRequest?: ChangeRequest
  pipeline?: PipelineState
  isLoading?: boolean
  clarificationNeeded?: boolean
  suggestions?: string[]
}

export interface ChatRequest {
  prompt: string
  session_id?: string
  environment?: string
}

export interface StreamResultPayload {
  type: 'result'
  response: string
  intent: string
  clarification_needed: boolean
  suggestions: string[]
  change_request?: ChangeRequest
  session_id: string
}

// ─── Environment ──────────────────────────────────────────────────────────────

export type Environment = 'dev' | 'uit' | 'prod'

