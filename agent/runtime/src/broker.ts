import type { Context } from "@earendil-works/pi-ai";
import type { Broker, BrokerDelta, ToolName } from "./runner.ts";

function record(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: string[]) {
  if (Object.keys(value).some((key) => !keys.includes(key)))
    throw new Error("INVALID_MODEL_STREAM");
}
export function decodeDelta(value: unknown): BrokerDelta {
  if (!record(value)) throw new Error("INVALID_MODEL_STREAM");
  if (value.type === "text" && typeof value.text === "string") {
    exact(value, ["type", "text"]);
    return { type: "text", text: value.text };
  }
  if (
    value.type === "tool" &&
    typeof value.id === "string" &&
    /^[A-Za-z0-9_.:-]{1,128}$/.test(value.id) &&
    typeof value.name === "string" &&
    value.name.length <= 64 &&
    record(value.arguments)
  ) {
    exact(value, ["type", "id", "name", "arguments"]);
    return {
      type: "tool",
      id: value.id,
      name: value.name,
      arguments: value.arguments,
    };
  }
  if (value.type === "usage") {
    exact(value, ["type", "input", "output"]);
    const number = (v: unknown): v is number | null =>
      v === null ||
      (typeof v === "number" && Number.isSafeInteger(v) && v >= 0);
    if (number(value.input) && number(value.output))
      return { type: "usage", input: value.input, output: value.output };
  }
  if (
    value.type === "finish" &&
    ["stop", "toolUse", "length"].includes(String(value.reason))
  ) {
    exact(value, ["type", "reason"]);
    return {
      type: "finish",
      reason: value.reason as "stop" | "toolUse" | "length",
    };
  }
  throw new Error("INVALID_MODEL_STREAM");
}

/** Only the server-configured gateway can be contacted. The model never supplies a URL. */
export function httpBroker(origin: string, capability: string): Broker {
  const base = new URL(origin);
  if (
    !["http:", "https:"].includes(base.protocol) ||
    base.username ||
    base.password ||
    base.search ||
    base.hash ||
    base.pathname !== "/"
  )
    throw new Error("INVALID_BROKER_CONFIGURATION");
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(capability))
    throw new Error("INVALID_CAPABILITY");
  const post = async (path: string, body: unknown, signal: AbortSignal) => {
    const response = await fetch(new URL(path, base), {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${capability}`,
      },
      body: JSON.stringify(body),
      signal,
      redirect: "error",
    });
    if (!response.ok || !response.body)
      throw new Error(
        response.status === 429 ? "BUDGET_EXCEEDED" : "TOOL_UNAVAILABLE",
      );
    return response;
  };
  return {
    async *model(
      context: Context,
      sequence: number,
      maxOutput: number,
      signal: AbortSignal,
    ) {
      const response = await post(
        "/internal/research/model",
        { context, sequence, max_output: maxOutput },
        signal,
      );
      const reader = response.body!.getReader(),
        decoder = new TextDecoder("utf-8", { fatal: true });
      let pending = "",
        total = 0;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            pending += decoder.decode();
            break;
          }
          total += value.byteLength;
          if (total > 262144) throw new Error("RESOURCE_LIMIT");
          pending += decoder.decode(value, { stream: true });
          if (Buffer.byteLength(pending) > 65536)
            throw new Error("RESOURCE_LIMIT");
          let end: number;
          while ((end = pending.indexOf("\n")) >= 0) {
            const line = pending.slice(0, end);
            pending = pending.slice(end + 1);
            if (line.trim()) yield decodeDelta(JSON.parse(line));
          }
        }
        if (pending.trim()) yield decodeDelta(JSON.parse(pending));
      } finally {
        await reader.cancel().catch(() => {});
        reader.releaseLock();
      }
    },
    async tool(
      name: ToolName,
      args: unknown,
      callId: string,
      signal: AbortSignal,
    ) {
      const response = await post(
        "/internal/research/tool",
        { name, args, call_id: callId },
        signal,
      );
      const reader = response.body!.getReader();
      let total = 0;
      const chunks: Uint8Array[] = [];
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          total += value.byteLength;
          if (total > 32768) throw new Error("RESOURCE_LIMIT");
          chunks.push(value);
        }
      } finally {
        await reader.cancel().catch(() => {});
        reader.releaseLock();
      }
      const data = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      if (
        !record(data) ||
        !("result" in data) ||
        Object.keys(data).length !== 1
      )
        throw new Error("TOOL_UNAVAILABLE");
      return data.result;
    },
  };
}
