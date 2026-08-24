import { Activity, Server } from 'lucide-react'
import type { Environment } from '../types'
import clsx from 'clsx'

interface HeaderProps {
  serverStatus: 'online' | 'offline' | 'checking'
  environment: Environment
  onEnvironmentChange: (env: Environment) => void
}

const ENV_CONFIG: Record<Environment, { label: string; color: string; dot: string }> = {
  dev:  { label: 'DEV',  color: 'text-green-400  bg-green-400/10  border-green-400/30',  dot: 'bg-green-400' },
  uit:  { label: 'UIT',  color: 'text-amber-400  bg-amber-400/10  border-amber-400/30',  dot: 'bg-amber-400' },
  prod: { label: 'PROD', color: 'text-red-400    bg-red-400/10    border-red-400/30',    dot: 'bg-red-400'   },
}

export default function Header({ serverStatus, environment, onEnvironmentChange }: HeaderProps) {
  return (
    <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-md sticky top-0 z-10">
      <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white leading-none">Atlas MCP</h1>
            <p className="text-xs text-gray-500 leading-none mt-0.5">Change Request Management</p>
          </div>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-3">
          {/* Environment selector */}
          <div className="flex items-center gap-1 bg-gray-900 border border-gray-800 rounded-lg p-1">
            {(Object.keys(ENV_CONFIG) as Environment[]).map(env => (
              <button
                key={env}
                onClick={() => onEnvironmentChange(env)}
                className={clsx(
                  'px-3 py-1 text-xs font-semibold rounded-md transition-all duration-200',
                  environment === env
                    ? ENV_CONFIG[env].color + ' border'
                    : 'text-gray-500 hover:text-gray-300',
                )}
              >
                {ENV_CONFIG[env].label}
              </button>
            ))}
          </div>

          {/* Server status */}
          <div className="flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-lg px-3 py-1.5">
            <Server className="w-3.5 h-3.5 text-gray-500" />
            <div className={clsx(
              'w-2 h-2 rounded-full',
              serverStatus === 'online'   ? 'bg-green-400 shadow-sm shadow-green-400' :
              serverStatus === 'checking' ? 'bg-amber-400 animate-pulse' :
              'bg-red-400',
            )} />
            <span className="text-xs text-gray-400">
              {serverStatus === 'online' ? 'Connected' : serverStatus === 'checking' ? 'Connecting…' : 'Offline'}
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}

