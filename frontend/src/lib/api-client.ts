/// <reference types="vite/client" />

export const API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8010'

const DEFAULT_TIMEOUT = 30_000
const TOKEN_KEY = 'fund_watch_token'

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setAccessToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // storage unavailable (private browsing, quota) — ignore
  }
}

/** Attach X-Fund-Token when a token is stored (backend FUND_WATCH_TOKEN auth). */
function withAuth(init?: RequestInit): RequestInit {
  const token = getAccessToken()
  if (!token) return init ?? {}
  const headers = new Headers(init?.headers)
  headers.set('X-Fund-Token', token)
  return { ...init, headers }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Caller-supplied signal still wins; the timeout aborts alongside it.
  const controller = new AbortController()
  const onCallerAbort = () => controller.abort()
  if (init?.signal) {
    if (init.signal.aborted) controller.abort()
    else init.signal.addEventListener('abort', onCallerAbort, { once: true })
  }
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT)
  try {
    const res = await fetch(`${API}${path}`, {
      ...withAuth(init),
      signal: controller.signal,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    return res.json()
  } catch (e) {
    // caller abort → propagate as-is (react-query cancellation); our own
    // timeout → surface a readable message instead of a raw AbortError
    if (controller.signal.aborted && !init?.signal?.aborted) {
      throw new Error('请求超时，请稍后重试')
    }
    throw e
  } finally {
    clearTimeout(timer)
    init?.signal?.removeEventListener('abort', onCallerAbort)
  }
}

type SseEvent = { type: string; step?: string; text?: string; data?: unknown }

/** Shared SSE reader for the streaming endpoints (OCR fund-code, AI select) —
 * one fetch+read loop instead of duplicating it per endpoint.
 * Guarantees onError fires exactly once on failure; a caller abort
 * (init.signal) settles silently. */
export async function streamSSE(
  url: string,
  init: RequestInit,
  onEvent: (evt: SseEvent) => void,
  onError: (msg: string) => void,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(url, withAuth(init))
  } catch (e) {
    if (init.signal?.aborted) return
    onError(e instanceof Error ? e.message : '网络请求失败')
    return
  }
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}))
    onError(err.detail || `HTTP ${res.status}`)
    return
  }
  // A terminal result/error event must arrive before the stream ends —
  // otherwise the stream was truncated and we must not settle silently.
  let terminated = false
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const parts = buf.split('\n\n')
      buf = parts.pop() ?? ''
      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data:')) continue
        try {
          const evt = JSON.parse(line.slice('data:'.length).trim()) as SseEvent
          if (evt.type === 'result' || evt.type === 'error') terminated = true
          onEvent(evt)
        } catch {
          // malformed chunk, skip
        }
      }
    }
  } catch (e) {
    if (init.signal?.aborted) return
    onError(e instanceof Error ? e.message : '连接中断')
    return
  }
  if (!terminated && !init.signal?.aborted) onError('连接中断，未收到结果')
}
