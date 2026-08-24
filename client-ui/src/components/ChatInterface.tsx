import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, Lightbulb, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import clsx from 'clsx'
import { streamChat } from '../services/api'
import ProgressPipeline from './ProgressPipeline'
import ChangeRequestCard from './ChangeRequestCard'
import type {
  ChatMessage,
  PipelineState,
  PipelineUpdate,
  PipelineStage,
  StreamResultPayload,
  Environment,
} from '../types'

const INITIAL_PIPELINE: PipelineState = {
  client: 'idle',
  llm_processing: 'idle',
  mcp_server: 'idle',
  atlas_api: 'idle',
  complete: 'idle',
  messages: {
    client: '',
    llm_processing: '',
    mcp_server: '',
    atlas_api: '',
    complete: '',
    error: '',
  },
}

const SAMPLE_PROMPTS = [
  "Create a change request with date 07/04/2026 - 07/06/2026 with title Apollo server upgrade",
  "Add a deployment task to CHG123456 for deploying artifact git-tools app",
  "Update the status of CHG123456 to close",
  "What's the status of CHG123456?",
  "List all open change requests",
  "Show me all change requests in production",
]

function uuid() {
  return Math.random().toString(36).substring(2, 11)
}

interface ChatInterfaceProps {
  environment: Environment
}

export default function ChatInterface({ environment }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: uuid(),
      role: 'assistant',
      content: '👋 Welcome to **Atlas Change Request Management**!\n\nI can help you create, update, check status, and close change requests. Try one of the sample prompts below or type your own request.',
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [sessionId] = useState(() => uuid())
  const [activePipeline, setActivePipeline] = useState<PipelineState | null>(null)
  const [showSamples, setShowSamples] = useState(true)
  // Track which message pipelines are expanded (collapsed by default after first render)
  const [expandedPipelines, setExpandedPipelines] = useState<Record<string, boolean>>({})

  const togglePipeline = (msgId: string) =>
    setExpandedPipelines(prev => ({ ...prev, [msgId]: !prev[msgId] }))

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activePipeline])

  const applyPipelineUpdate = useCallback((update: PipelineUpdate, prev: PipelineState): PipelineState => {
    const stage = update.stage as PipelineStage
    return {
      ...prev,
      [stage]: update.status,
      messages: { ...prev.messages, [stage]: update.message },
    }
  }, [])

  const handleSend = useCallback(async (promptText?: string) => {
    const text = (promptText ?? input).trim()
    if (!text || isProcessing) return

    setInput('')
    setShowSamples(false)
    setIsProcessing(true)

    const userMsg: ChatMessage = {
      id: uuid(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])

    // Start pipeline
    const initialPipeline: PipelineState = {
      ...INITIAL_PIPELINE,
      client: 'active',
      messages: { ...INITIAL_PIPELINE.messages, client: 'Sending request...' },
    }
    setActivePipeline(initialPipeline)

    let finalPipeline: PipelineState = initialPipeline

    await streamChat(
      { prompt: text, session_id: sessionId, environment },
      {
        onPipelineUpdate: (update) => {
          // Compute the next pipeline state synchronously so finalPipeline
          // is always up-to-date when onResult fires in the same JS tick.
          finalPipeline = applyPipelineUpdate(update, finalPipeline)
          setActivePipeline(finalPipeline)
        },
        onResult: (result: StreamResultPayload) => {
          const assistantMsg: ChatMessage = {
            id: uuid(),
            role: 'assistant',
            content: result.response,
            timestamp: new Date(),
            intent: result.intent,
            changeRequest: result.change_request ?? undefined,
            clarificationNeeded: result.clarification_needed,
            suggestions: result.suggestions,
            pipeline: finalPipeline,
          }
          setMessages(prev => [...prev, assistantMsg])
          setExpandedPipelines(prev => ({ ...prev, [assistantMsg.id]: true }))
          setActivePipeline(null)
          setIsProcessing(false)
        },
        onError: (error) => {
          const errMsg: ChatMessage = {
            id: uuid(),
            role: 'assistant',
            content: `❌ **Error:** ${error}\n\nPlease make sure the MCP server is running and try again.`,
            timestamp: new Date(),
          }
          setMessages(prev => [...prev, errMsg])
          setActivePipeline(null)
          setIsProcessing(false)
        },
      },
    )
  }, [input, isProcessing, sessionId, environment, applyPipelineUpdate])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleReset = () => {
    setMessages([{
      id: uuid(),
      role: 'assistant',
      content: '👋 Session reset. How can I help you with change requests?',
      timestamp: new Date(),
    }])
    setShowSamples(true)
    setActivePipeline(null)
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto w-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map(msg => (
          <div
            key={msg.id}
            className={clsx(
              'flex gap-3 animate-slide-in',
              msg.role === 'user' ? 'justify-end' : 'justify-start',
            )}
          >
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0 mt-1">
                <span className="text-sm">🤖</span>
              </div>
            )}

            <div className={clsx(
              'max-w-[80%] space-y-2',
              msg.role === 'user' ? 'items-end' : 'items-start',
            )}>
              {/* Completed pipeline — shown above the response bubble for assistant messages */}
              {msg.role === 'assistant' && msg.pipeline && (
                <div className="w-full">
                  {/* Toggle bar */}
                  <button
                    onClick={() => togglePipeline(msg.id)}
                    className="flex items-center gap-1.5 text-[10px] text-gray-500 hover:text-gray-300 mb-1 transition-colors"
                  >
                    {expandedPipelines[msg.id]
                      ? <ChevronUp className="w-3 h-3" />
                      : <ChevronDown className="w-3 h-3" />
                    }
                    <span className="uppercase tracking-wider font-medium">
                      {expandedPipelines[msg.id] ? 'Hide pipeline' : 'Show pipeline'}
                    </span>
                  </button>
                  {expandedPipelines[msg.id] && (
                    <ProgressPipeline pipeline={msg.pipeline} visible={true} />
                  )}
                </div>
              )}

              {/* Message bubble */}
              <div className={clsx(
                'rounded-2xl px-4 py-3 text-sm leading-relaxed',
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-sm'
                  : 'bg-gray-900 border border-gray-800 text-gray-200 rounded-tl-sm',
              )}>
                <div className="message-content">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              </div>

              {/* Suggestions */}
              {msg.clarificationNeeded && msg.suggestions && msg.suggestions.length > 0 && (
                <div className="space-y-1.5">
                  {msg.suggestions.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => handleSend(s.replace(/^(Would you like to |Please )/, ''))}
                      className="w-full text-left text-xs bg-gray-900 hover:bg-gray-800 border border-gray-700 hover:border-blue-500/50 rounded-lg px-3 py-2 text-gray-300 transition-all duration-200 flex items-center gap-2"
                    >
                      <Lightbulb className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                      {s}
                    </button>
                  ))}
                </div>
              )}

              {/* Change Request Card */}
              {msg.changeRequest && (
                <div className="w-full max-w-sm">
                  <ChangeRequestCard cr={msg.changeRequest} />
                </div>
              )}

              {/* Intent badge */}
              {msg.intent && msg.intent !== 'unclear' && (
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-gray-600 bg-gray-900 border border-gray-800 px-2 py-0.5 rounded-full">
                    {msg.intent.replace(/_/g, ' ')}
                  </span>
                </div>
              )}
            </div>

            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-lg bg-gray-700 flex items-center justify-center flex-shrink-0 mt-1">
                <span className="text-sm">👤</span>
              </div>
            )}
          </div>
        ))}

        {/* Active (in-progress) pipeline — shown below message list while processing */}
        {activePipeline && (
          <div className="px-11">
            <ProgressPipeline pipeline={activePipeline} visible={true} />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Sample prompts */}
      {showSamples && (
        <div className="px-4 pb-2">
          <button
            onClick={() => setShowSamples(false)}
            className="w-full flex items-center justify-between text-xs text-gray-500 hover:text-gray-400 mb-2"
          >
            <span className="font-medium">💡 Sample prompts</span>
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {SAMPLE_PROMPTS.map((p, i) => (
              <button
                key={i}
                onClick={() => handleSend(p)}
                disabled={isProcessing}
                className="text-left text-xs bg-gray-900/80 hover:bg-gray-800 border border-gray-800 hover:border-blue-500/40 rounded-lg px-3 py-2.5 text-gray-400 hover:text-gray-200 transition-all duration-200 truncate"
                title={p}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input bar */}
      <div className="border-t border-gray-800 px-4 py-3 bg-gray-950/80 backdrop-blur-md">
        <div className="flex items-end gap-2">
          <button
            onClick={handleReset}
            title="Reset conversation"
            className="p-2.5 text-gray-600 hover:text-gray-400 hover:bg-gray-800 rounded-xl transition-all flex-shrink-0 mb-0.5"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about change requests… (e.g. 'Create a CR for Apollo upgrade next week')"
              rows={1}
              disabled={isProcessing}
              className={clsx(
                'w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 text-sm text-gray-200',
                'placeholder-gray-600 resize-none focus:outline-none focus:border-blue-500/60',
                'transition-all duration-200 leading-relaxed',
                'min-h-[44px] max-h-[120px]',
                isProcessing && 'opacity-60 cursor-not-allowed',
              )}
              style={{ height: 'auto' }}
              onInput={e => {
                const t = e.target as HTMLTextAreaElement
                t.style.height = 'auto'
                t.style.height = Math.min(t.scrollHeight, 120) + 'px'
              }}
            />
          </div>

          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isProcessing}
            className={clsx(
              'p-2.5 rounded-xl transition-all duration-200 flex-shrink-0 mb-0.5',
              input.trim() && !isProcessing
                ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/30'
                : 'bg-gray-800 text-gray-600 cursor-not-allowed',
            )}
          >
            {isProcessing
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Send className="w-4 h-4" />
            }
          </button>
        </div>
        <p className="text-[10px] text-gray-700 mt-2 text-center">
          Shift+Enter for new line • Enter to send
        </p>
      </div>
    </div>
  )
}

