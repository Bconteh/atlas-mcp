import { useState, useEffect } from 'react'
import Header from './components/Header'
import ChatInterface from './components/ChatInterface'
import { checkHealth } from './services/api'
import type { Environment } from './types'
import './index.css'

export default function App() {
  const [serverStatus, setServerStatus] = useState<'online' | 'offline' | 'checking'>('checking')
  const [environment, setEnvironment] = useState<Environment>('dev')

  useEffect(() => {
    const ping = async () => {
      try {
        await checkHealth()
        setServerStatus('online')
      } catch {
        setServerStatus('offline')
      }
    }
    ping()
    const interval = setInterval(ping, 15_000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex flex-col h-screen bg-gray-950">
      <Header
        serverStatus={serverStatus}
        environment={environment}
        onEnvironmentChange={setEnvironment}
      />

      <main className="flex-1 overflow-hidden flex flex-col">
        {serverStatus === 'offline' && (
          <div className="mx-4 mt-3 bg-red-900/20 border border-red-800/50 rounded-xl p-3 text-sm text-red-400 text-center">
            ⚠️ Cannot connect to the MCP server. Make sure it's running at{' '}
            <code className="font-mono text-red-300">http://localhost:8000</code>
          </div>
        )}
        <ChatInterface environment={environment} />
      </main>
    </div>
  )
}

