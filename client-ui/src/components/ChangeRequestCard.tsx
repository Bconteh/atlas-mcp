import clsx from 'clsx'
import { Calendar, CheckCircle2, AlertTriangle, Tag, User } from 'lucide-react'
import type { ChangeRequest, ChangeRequestStatus, RiskLevel } from '../types'

const STATUS_CONFIG: Record<ChangeRequestStatus, { label: string; color: string; bg: string }> = {
  draft:            { label: 'Draft',            color: 'text-gray-400',   bg: 'bg-gray-800' },
  open:             { label: 'Open',             color: 'text-green-400',  bg: 'bg-green-900/30' },
  in_progress:      { label: 'In Progress',      color: 'text-blue-400',   bg: 'bg-blue-900/30' },
  pending_approval: { label: 'Pending Approval', color: 'text-amber-400',  bg: 'bg-amber-900/30' },
  approved:         { label: 'Approved',         color: 'text-emerald-400',bg: 'bg-emerald-900/30' },
  closed:           { label: 'Closed',           color: 'text-gray-500',   bg: 'bg-gray-800/50' },
  cancelled:        { label: 'Cancelled',        color: 'text-red-400',    bg: 'bg-red-900/20' },
}

const RISK_CONFIG: Record<RiskLevel, { label: string; color: string }> = {
  low:      { label: 'Low',      color: 'text-green-400' },
  medium:   { label: 'Medium',   color: 'text-amber-400' },
  high:     { label: 'High',     color: 'text-orange-400' },
  critical: { label: 'Critical', color: 'text-red-400' },
}

interface ChangeRequestCardProps {
  cr: ChangeRequest
  compact?: boolean
}

export default function ChangeRequestCard({ cr, compact = false }: ChangeRequestCardProps) {
  const status = STATUS_CONFIG[cr.status] || STATUS_CONFIG.draft
  const risk = RISK_CONFIG[cr.risk_level] || RISK_CONFIG.low
  const completedTasks = cr.tasks.filter(t => t.status === 'completed').length

  return (
    <div className={clsx(
      'bg-gray-900 border border-gray-800 rounded-xl p-4 animate-fade-in',
      'hover:border-gray-700 transition-all duration-200',
    )}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono font-semibold text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded">
              {cr.id}
            </span>
            <span className={clsx(
              'text-xs font-medium px-2 py-0.5 rounded-full',
              status.color, status.bg,
            )}>
              {status.label}
            </span>
          </div>
          <h3 className="font-semibold text-white leading-tight">{cr.title}</h3>
        </div>
      </div>

      {!compact && cr.description && (
        <p className="text-sm text-gray-400 mb-3 leading-relaxed">{cr.description}</p>
      )}

      {/* Meta */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex items-center gap-1.5 text-gray-400">
          <Calendar className="w-3.5 h-3.5 flex-shrink-0" />
          <span>{cr.start_date} → {cr.end_date}</span>
        </div>
        <div className={clsx('flex items-center gap-1.5', risk.color)}>
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>{risk.label} Risk</span>
        </div>
        {cr.environment && (
          <div className="flex items-center gap-1.5 text-gray-400">
            <Tag className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="uppercase">{cr.environment}</span>
          </div>
        )}
        <div className="flex items-center gap-1.5 text-gray-400">
          <User className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="truncate">{cr.created_by}</span>
        </div>
      </div>

      {/* Tasks summary */}
      {cr.tasks.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Tasks
            </span>
            <span className="text-xs text-gray-400">
              {completedTasks}/{cr.tasks.length} done
            </span>
          </div>
          {/* Progress bar */}
          <div className="w-full bg-gray-800 rounded-full h-1.5">
            <div
              className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${cr.tasks.length > 0 ? (completedTasks / cr.tasks.length) * 100 : 0}%` }}
            />
          </div>

          {!compact && (
            <ul className="mt-2 space-y-1">
              {cr.tasks.slice(0, 3).map(task => (
                <li key={task.id} className="flex items-center gap-2 text-xs text-gray-400">
                  <span className={clsx(
                    'w-1.5 h-1.5 rounded-full flex-shrink-0',
                    task.status === 'completed' ? 'bg-green-400' :
                    task.status === 'in_progress' ? 'bg-blue-400 animate-pulse' :
                    task.status === 'failed' ? 'bg-red-400' :
                    'bg-gray-600',
                  )} />
                  <span className="truncate">{task.title}</span>
                  {task.assignee && (
                    <span className="text-gray-600 ml-auto flex-shrink-0">@{task.assignee.split('@')[0]}</span>
                  )}
                </li>
              ))}
              {cr.tasks.length > 3 && (
                <li className="text-xs text-gray-600 ml-3.5">
                  +{cr.tasks.length - 3} more
                </li>
              )}
            </ul>
          )}
        </div>
      )}

      {cr.close_reason && (
        <div className="mt-2 pt-2 border-t border-gray-800">
          <p className="text-xs text-gray-500">
            <span className="text-gray-400 font-medium">Close reason:</span> {cr.close_reason}
          </p>
        </div>
      )}
    </div>
  )
}

