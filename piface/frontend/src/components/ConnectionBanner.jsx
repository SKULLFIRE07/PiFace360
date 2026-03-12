import { useState, useEffect, useRef } from 'react'
import { WifiOff, Loader2 } from 'lucide-react'
import { api } from '../api/client'

export default function ConnectionBanner() {
  const [status, setStatus] = useState('connected') // 'connected' | 'reconnecting' | 'disconnected'
  const failStartRef = useRef(null)
  const intervalRef = useRef(null)

  useEffect(() => {
    async function checkHealth() {
      try {
        await api.get('/system/health', { timeout: 5000 })
        setStatus('connected')
        failStartRef.current = null
      } catch {
        if (!failStartRef.current) {
          failStartRef.current = Date.now()
        }
        const elapsed = Date.now() - failStartRef.current
        setStatus(elapsed > 30000 ? 'disconnected' : 'reconnecting')
      }
    }

    checkHealth()
    intervalRef.current = setInterval(checkHealth, 10000)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  if (status === 'connected') return null

  const isDisconnected = status === 'disconnected'

  return (
    <div
      className={`flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium ${
        isDisconnected
          ? 'bg-red-500 text-white'
          : 'bg-yellow-400 text-yellow-900'
      }`}
    >
      {isDisconnected ? (
        <>
          <WifiOff className="w-4 h-4" />
          <span>Disconnected from server</span>
        </>
      ) : (
        <>
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Reconnecting...</span>
        </>
      )}
    </div>
  )
}
