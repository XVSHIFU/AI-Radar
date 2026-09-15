export type SseEvent = { event: string; data: string };

export async function* parseSse(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "message";
  let data: string[] = [];
  let ended = false;
  let sawSources = false;
  let sawError = false;
  let sawDone = false;
  let protocolVersion = 1;
  let turn = 0;
  let tokenSequence = 0;
  const abort = () => void reader.cancel("aborted");
  signal?.addEventListener("abort", abort, { once: true });
  const emit = (): SseEvent | null => {
    if (!data.length) return null;
    const value = { event, data: data.join("\n") };
    event = "message";
    data = [];
    return value;
  };
  const validate = (value: SseEvent) => {
    if (sawDone) throw new Error("done 后收到额外事件");
    if (
      !["meta", "status", "reset", "token", "sources", "error", "done"].includes(
        value.event,
      )
    )
      throw new Error(`未知 SSE 事件：${value.event}`);
    if (value.event === "meta") {
      const version = JSON.parse(value.data).protocol_version ?? 1;
      if (![1, 2].includes(version)) throw new Error("不支持的 SSE 协议版本");
      protocolVersion = version;
    }
    if (value.event === "reset") {
      const payload = JSON.parse(value.data);
      if (protocolVersion !== 2 || sawError || sawSources || !Number.isInteger(payload.turn) ||
          payload.turn < 1 || payload.turn > 3 || payload.turn < turn || payload.turn > turn + 1 ||
          typeof payload.text !== "string") throw new Error("无效的研究草稿切换");
      turn = payload.turn; tokenSequence = 0;
    }
    if (value.event === "token" && protocolVersion === 2) {
      const payload = JSON.parse(value.data);
      if (!turn || payload.turn !== turn || payload.seq !== tokenSequence + 1 || typeof payload.text !== "string")
        throw new Error("研究文字顺序无效");
      tokenSequence = payload.seq;
    }
    if (value.event === "token" && sawSources)
      throw new Error("sources 后不能再发送 token");
    if (value.event === "error") sawError = true;
    if (value.event === "sources") sawSources = true;
    if (value.event === "done") {
      if (sawDone) throw new Error("重复 done 事件");
      const status = JSON.parse(value.data).status;
      if (!["completed", "failed", "cancelled"].includes(status))
        throw new Error("未知 done 状态");
      if (!sawSources) throw new Error("done 前缺少 sources");
      if (sawError && status !== "failed")
        throw new Error("error 后 done 必须为 failed");
      sawDone = true;
    }
  };
  try {
    while (true) {
      if (signal?.aborted) throw new DOMException("已取消", "AbortError");
      const { value, done } = await reader.read();
      if (signal?.aborted) throw new DOMException("已取消", "AbortError");
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      let boundary: RegExpMatchArray | null;
      while ((boundary = buffer.match(/^(.*?)(\r\n|\n|\r(?!$))/))) {
        buffer = buffer.slice(boundary[0].length);
        const line = boundary[1];
        if (!line) {
          const out = emit();
          if (out) {
            validate(out);
            yield out;
          }
          continue;
        }
        if (line.startsWith(":")) continue;
        const split = line.indexOf(":");
        const field = split < 0 ? line : line.slice(0, split);
        const text = (split < 0 ? "" : line.slice(split + 1)).replace(/^ /, "");
        if (field === "event") event = text;
        if (field === "data") data.push(text);
      }
      if (done) break;
    }
    buffer += decoder.decode();
    if (buffer) {
      const out = emit();
      if (out) {
        validate(out);
        yield out;
      }
    }
    if (!sawDone) throw new Error("流在未收到 done 事件时结束");
  } finally {
    signal?.removeEventListener("abort", abort);
    if (!ended) await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
