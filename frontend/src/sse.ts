export type SseEvent = { event: string; data: string }

export async function* parseSse(stream: ReadableStream<Uint8Array>, signal?: AbortSignal) {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let event = 'message'
  let data: string[] = []
  let ended = false
  let sawSources = false
  let sawDone = false
  const abort = () => void reader.cancel('aborted')
  signal?.addEventListener('abort', abort, { once: true })
  const emit = (): SseEvent | null => {
    if (!data.length) return null
    const value = { event, data: data.join('\n') }
    event = 'message'; data = []
    return value
  }
  const validate = (value: SseEvent) => {
    if (sawDone) throw new Error('done 后收到额外事件')
    if (!['meta','status','token','sources','error','done'].includes(value.event)) throw new Error(`未知 SSE 事件：${value.event}`)
    if (value.event === 'token' && sawSources) throw new Error('sources 后不能再发送 token')
    if (value.event === 'sources') sawSources = true
    if (value.event === 'done') {
      if (sawDone) throw new Error('重复 done 事件')
      const status = JSON.parse(value.data).status
      if (!['completed','failed'].includes(status)) throw new Error('未知 done 状态')
      sawDone = true
    }
  }
  try {
    while (true) {
      if (signal?.aborted) throw new DOMException('已取消', 'AbortError')
      const { value, done } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
      let boundary: RegExpMatchArray | null
      while ((boundary = buffer.match(/^(.*?)(\r\n|\n|\r(?!$))/))) {
        buffer = buffer.slice(boundary[0].length)
        const line = boundary[1]
        if (!line) { const out = emit(); if (out) { validate(out); yield out }; continue }
        if (line.startsWith(':')) continue
        const split = line.indexOf(':')
        const field = split < 0 ? line : line.slice(0, split)
        const text = (split < 0 ? '' : line.slice(split + 1)).replace(/^ /, '')
        if (field === 'event') event = text
        if (field === 'data') data.push(text)
      }
      if (done) break
    }
    buffer += decoder.decode()
    if (buffer) { const out = emit(); if (out) { validate(out); yield out } }
    if (!sawDone) throw new Error('流在未收到 done 事件时结束')
  } finally {
    signal?.removeEventListener('abort', abort)
    if (!ended) await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
