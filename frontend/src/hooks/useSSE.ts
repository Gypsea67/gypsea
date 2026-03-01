import { useEffect, useRef, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8765'

/**
 * SSE hook с exponential backoff reconnect.
 * onMessage хранится в ref чтобы не рвать SSE-соединение при каждом рендере.
 */
export function useSSE(
  path: string,
  onMessage: (data: any) => void,
  enabled: boolean = true
) {
  const sourceRef = useRef<EventSource | null>(null)
  const retryRef = useRef(0)
  const onMessageRef = useRef(onMessage)
  const maxRetries = 10
  const baseDelay = 1000

  // Всегда актуальный callback без пересоздания SSE
  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close()
    }

    const url = `${API_BASE}${path}`
    const source = new EventSource(url)
    sourceRef.current = source

    source.onmessage = (event) => {
      retryRef.current = 0 // Reset on success
      try {
        const data = JSON.parse(event.data)
        onMessageRef.current(data)
      } catch {
        onMessageRef.current(event.data)
      }
    }

    // Named events (e.g., "system")
    source.addEventListener('system', (event: any) => {
      try {
        const data = JSON.parse(event.data)
        onMessageRef.current({ type: 'system', ...data })
      } catch {}
    })

    source.onerror = () => {
      source.close()
      sourceRef.current = null
      if (retryRef.current < maxRetries) {
        const delay = baseDelay * Math.pow(2, retryRef.current)
        retryRef.current++
        setTimeout(connect, delay)
      }
    }
  }, [path])

  useEffect(() => {
    if (enabled && path) {
      retryRef.current = 0
      connect()
    }
    return () => {
      sourceRef.current?.close()
      sourceRef.current = null
    }
  }, [enabled, path, connect])

  return {
    close: () => {
      sourceRef.current?.close()
      sourceRef.current = null
    },
  }
}

/**
 * Fetch helper for API calls.
 */
export async function apiFetch<T = any>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  return res.json()
}
