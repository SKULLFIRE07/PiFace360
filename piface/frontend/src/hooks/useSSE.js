import { useState, useEffect, useRef, useCallback } from 'react'

export function useSSE(url, options = {}) {
  const { onMessage, onError, withCredentials = true } = options
  const [data, setData] = useState(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(null)

  const eventSourceRef = useRef(null)
  const retryCountRef = useRef(0)
  const retryTimeoutRef = useRef(null)
  const lastEventIdRef = useRef(null)
  const urlRef = useRef(url)
  const mountedRef = useRef(true)

  urlRef.current = url

  const getBackoffDelay = useCallback((retryCount) => {
    const delay = Math.min(1000 * Math.pow(2, retryCount), 30000)
    return delay
  }, [])

  const disconnect = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (!mountedRef.current) return

    disconnect()

    let connectUrl = urlRef.current
    if (lastEventIdRef.current) {
      const separator = connectUrl.includes('?') ? '&' : '?'
      connectUrl += `${separator}lastEventId=${encodeURIComponent(lastEventIdRef.current)}`
    }

    const es = new EventSource(connectUrl, { withCredentials })
    eventSourceRef.current = es

    es.onopen = () => {
      if (!mountedRef.current) return
      setConnected(true)
      setError(null)
      retryCountRef.current = 0
    }

    es.onmessage = (event) => {
      if (!mountedRef.current) return
      if (event.lastEventId) {
        lastEventIdRef.current = event.lastEventId
      }
      try {
        const parsed = JSON.parse(event.data)
        setData(parsed)
        onMessage?.(parsed, event)
      } catch {
        setData(event.data)
        onMessage?.(event.data, event)
      }
    }

    es.onerror = (err) => {
      if (!mountedRef.current) return
      es.close()
      eventSourceRef.current = null
      setConnected(false)

      const backoff = getBackoffDelay(retryCountRef.current)
      setError(`Connection lost. Retrying in ${Math.round(backoff / 1000)}s...`)
      onError?.(err)

      retryTimeoutRef.current = setTimeout(() => {
        if (mountedRef.current) {
          retryCountRef.current += 1
          connect()
        }
      }, backoff)
    }
  }, [disconnect, getBackoffDelay, onMessage, onError, withCredentials])

  // Connect on mount
  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      disconnect()
    }
  }, [url]) // eslint-disable-line react-hooks/exhaustive-deps

  // Reconnect on page visibility change
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && !eventSourceRef.current && mountedRef.current) {
        retryCountRef.current = 0
        connect()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [connect])

  return { data, connected, error }
}
