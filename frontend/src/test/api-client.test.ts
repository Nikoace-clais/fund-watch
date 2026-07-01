import { describe, it, expect, vi } from 'vitest'
import { streamSSE } from '../lib/api-client'

function bodyFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  let i = 0
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i++]))
      } else {
        controller.close()
      }
    },
  })
}

describe('streamSSE', () => {
  it('parses multiple events split across chunk boundaries', async () => {
    // The second event's payload is split mid-chunk to exercise the buffer.
    const chunks = [
      'data: {"type":"step","step":"ocr","text":"a"}\n\n',
      'data: {"type":"resu',
      'lt","data":{"ok":true}}\n\n',
    ]
    global.fetch = vi.fn().mockResolvedValue({ ok: true, body: bodyFromChunks(chunks) })

    const events: unknown[] = []
    await streamSSE('http://x/test', {}, (evt) => events.push(evt), () => {})

    expect(events).toEqual([
      { type: 'step', step: 'ocr', text: 'a' },
      { type: 'result', data: { ok: true } },
    ])
  })

  it('reports onError with the response detail when the request fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => ({ detail: '上游服务不可用' }),
    })

    const onError = vi.fn()
    await streamSSE('http://x/test', {}, () => {}, onError)

    expect(onError).toHaveBeenCalledWith('上游服务不可用')
  })

  it('skips a malformed chunk without throwing', async () => {
    const chunks = ['data: {not json}\n\n', 'data: {"type":"step","text":"ok"}\n\n']
    global.fetch = vi.fn().mockResolvedValue({ ok: true, body: bodyFromChunks(chunks) })

    const events: unknown[] = []
    await streamSSE('http://x/test', {}, (evt) => events.push(evt), () => {})

    expect(events).toEqual([{ type: 'step', text: 'ok' }])
  })
})
