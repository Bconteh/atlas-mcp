import type {
  ChangeRequest,
  ChatRequest,
  PipelineUpdate,
  StreamResultPayload,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

// ─── Streaming chat (SSE) ─────────────────────────────────────────────────────

export interface StreamCallbacks {
  onPipelineUpdate: (update: PipelineUpdate) => void
  onResult: (result: StreamResultPayload) => void
  onError: (error: string) => void
}

export async function streamChat(
  request: ChatRequest,
  callbacks: StreamCallbacks,
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const err = await response.text()
    callbacks.onError(`Server error: ${err}`)
    return
  }

  const reader = response.body?.getReader()
  if (!reader) {
    callbacks.onError('No response body')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6).trim()
      if (!raw) continue

      try {
        const parsed = JSON.parse(raw)

        if (parsed.type === 'result') {
          callbacks.onResult(parsed as StreamResultPayload)
        } else if (parsed.stage) {
          callbacks.onPipelineUpdate(parsed as PipelineUpdate)
        }
      } catch {
        // ignore parse errors on partial chunks
      }
    }
  }
}

// ─── REST helpers ─────────────────────────────────────────────────────────────

export async function getChangeRequests(
  status?: string,
  environment?: string,
): Promise<{ change_requests: ChangeRequest[]; total: number }> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (environment) params.set('environment', environment)

  const res = await fetch(`${API_BASE}/change-requests?${params}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getChangeRequest(id: string): Promise<ChangeRequest> {
  const res = await fetch(`${API_BASE}/change-requests/${id}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function checkHealth(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error('Server not reachable')
  return res.json()
}

