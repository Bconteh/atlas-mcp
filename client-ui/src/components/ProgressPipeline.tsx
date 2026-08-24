import { CheckCircle, Circle, Loader2, XCircle } from 'lucide-react'
import clsx from 'clsx'
import type { PipelineState, StageStatus } from '../types'

interface StageConfig {
  key: keyof Omit<PipelineState, 'complete' | 'messages'>
  label: string
  icon: string
  idleColor: string
  activeColor: string
  completeColor: string
}

const STAGES: StageConfig[] = [
  {
    key: 'client',
    label: 'Client',
    icon: '💬',
    idleColor: 'border-gray-600 text-gray-500',
    activeColor: 'border-blue-400 text-blue-400 bg-blue-400/10 shadow-lg shadow-blue-400/20',
    completeColor: 'border-blue-500 text-blue-400 bg-blue-500/10',
  },
  {
    key: 'llm_processing',
    label: 'LLM Processing',
    icon: '🧠',
    idleColor: 'border-gray-600 text-gray-500',
    activeColor: 'border-amber-400 text-amber-400 bg-amber-400/10 shadow-lg shadow-amber-400/20',
    completeColor: 'border-amber-500 text-amber-400 bg-amber-500/10',
  },
  {
    key: 'mcp_server',
    label: 'MCP Server',
    icon: '⚙️',
    idleColor: 'border-gray-600 text-gray-500',
    activeColor: 'border-green-400 text-green-400 bg-green-400/10 shadow-lg shadow-green-400/20',
    completeColor: 'border-green-500 text-green-400 bg-green-500/10',
  },
  {
    key: 'atlas_api',
    label: 'Atlas API',
    icon: '🌐',
    idleColor: 'border-gray-600 text-gray-500',
    activeColor: 'border-purple-400 text-purple-400 bg-purple-400/10 shadow-lg shadow-purple-400/20',
    completeColor: 'border-purple-500 text-purple-400 bg-purple-500/10',
  },
]

interface ProgressPipelineProps {
  pipeline: PipelineState
  visible: boolean
}

function StageIcon({ status }: { status: StageStatus }) {
  if (status === 'active')   return <Loader2  className="w-3.5 h-3.5 animate-spin" />
  if (status === 'complete') return <CheckCircle className="w-3.5 h-3.5" />
  if (status === 'error')    return <XCircle  className="w-3.5 h-3.5 text-red-400" />
  return <Circle className="w-3.5 h-3.5 opacity-30" />
}

function getNodeClasses(status: StageStatus, config: StageConfig): string {
  if (status === 'active')   return config.activeColor
  if (status === 'complete') return config.completeColor
  if (status === 'error')    return 'border-red-500 text-red-400 bg-red-500/10'
  return config.idleColor
}

/**
 * Connector line between two adjacent stages.
 * - gray   : source idle
 * - animated blue pulse : source complete, target active (flow in progress)
 * - green  : source complete, target complete (or complete node reached)
 * - red    : source error
 */
function Connector({ fromStatus, toStatus }: { fromStatus: StageStatus; toStatus: StageStatus }) {
  const isFlowing  = fromStatus === 'complete' && toStatus === 'active'
  const isSuccess  = fromStatus === 'complete' && (toStatus === 'complete' || toStatus === 'idle')
  const isError    = fromStatus === 'error'

  return (
    <div className="relative flex-1 h-0.5 mx-1 mt-[-22px] overflow-hidden rounded-full">
      {/* Base track */}
      <div
        className={clsx(
          'absolute inset-0 rounded-full transition-colors duration-500',
          isError   ? 'bg-red-500'              :
          isSuccess ? 'bg-green-500'             :
          isFlowing ? 'bg-blue-900/60'           :
                      'bg-gray-700',
        )}
      />

      {/* Animated flow shimmer — only while in-progress */}
      {isFlowing && (
        <div
          className="absolute inset-0 rounded-full"
          style={{
            background: 'linear-gradient(90deg, transparent 0%, #60a5fa 50%, transparent 100%)',
            animation: 'pipelineFlow 1s linear infinite',
          }}
        />
      )}
    </div>
  )
}

export default function ProgressPipeline({ pipeline, visible }: ProgressPipelineProps) {
  if (!visible) return null

  // Build a flat list of all nodes (4 stages + Complete) so connectors are easy to derive
  type NodeKey = keyof Omit<PipelineState, 'messages'>
  const allKeys: NodeKey[] = ['client', 'llm_processing', 'mcp_server', 'atlas_api', 'complete']

  return (
    <>
      {/* Inline keyframe for the flow shimmer */}
      <style>{`
        @keyframes pipelineFlow {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>

      <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-4 mb-2 animate-fade-in backdrop-blur-sm">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-4">
          Processing Pipeline
        </p>

        <div className="flex items-start">
          {allKeys.map((key, i) => {
            const isCompleteNode = key === 'complete'
            const status = pipeline[key] as StageStatus
            const message = !isCompleteNode
              ? pipeline.messages[key as keyof typeof pipeline.messages]
              : pipeline.messages['complete']
            const isLast = i === allKeys.length - 1

            // For stage nodes (not Complete)
            const stageConfig = !isCompleteNode
              ? STAGES.find(s => s.key === key)!
              : null

            const nodeClasses = isCompleteNode
              ? clsx(
                  'w-12 h-12 rounded-xl border-2 flex flex-col items-center justify-center transition-all duration-500',
                  status === 'complete' ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400 shadow-lg shadow-emerald-400/20' :
                  status === 'error'    ? 'border-red-500 bg-red-500/10 text-red-400' :
                                         'border-gray-700 text-gray-600',
                )
              : clsx(
                  'w-12 h-12 rounded-xl border-2 flex flex-col items-center justify-center transition-all duration-500 cursor-default',
                  getNodeClasses(status, stageConfig!),
                )

            const nodeIcon = isCompleteNode
              ? (status === 'complete' ? '✅' : status === 'error' ? '❌' : '🏁')
              : stageConfig!.icon

            const nodeLabel = isCompleteNode
              ? 'Complete'
              : stageConfig!.label

            return (
              <div key={key} className="flex items-center flex-1 min-w-0">
                {/* Node */}
                <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
                  <div className={nodeClasses} title={message || nodeLabel}>
                    <span className="text-base leading-none">{nodeIcon}</span>
                    <StageIcon status={status} />
                  </div>
                  <div className="text-center">
                    <p className={clsx(
                      'text-[10px] font-medium leading-tight whitespace-nowrap',
                      status === 'idle' ? 'text-gray-600' : 'text-gray-300',
                    )}>
                      {nodeLabel}
                    </p>
                    {message && status !== 'idle' && (
                      <p className="text-[9px] text-gray-500 max-w-[72px] truncate leading-tight mt-0.5" title={message}>
                        {message}
                      </p>
                    )}
                  </div>
                </div>

                {/* Connector to next node */}
                {!isLast && (
                  <Connector
                    fromStatus={status}
                    toStatus={pipeline[allKeys[i + 1]] as StageStatus}
                  />
                )}
              </div>
            )
          })}
        </div>
      </div>
    </>
  )
}
