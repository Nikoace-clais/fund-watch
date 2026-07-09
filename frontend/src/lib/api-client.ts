/// <reference types="vite/client" />

export const API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8010'

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

type SseEvent = { type: string; step?: string; text?: string; data?: unknown }

/** Shared SSE reader for the streaming endpoints (OCR fund-code, AI select) —
 * one fetch+read loop instead of duplicating it per endpoint. */
export async function streamSSE(
  url: string,
  init: RequestInit,
  onEvent: (evt: SseEvent) => void,
  onError: (msg: string) => void,
): Promise<void> {
  const res = await fetch(url, init)
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}))
    onError(err.detail || `HTTP ${res.status}`)
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
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
        onEvent(JSON.parse(line.slice('data:'.length).trim()))
      } catch {
        // malformed chunk, skip
      }
    }
  }
}
