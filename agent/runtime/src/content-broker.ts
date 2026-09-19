import type { Context } from "@earendil-works/pi-ai";
import { decodeDelta } from "./broker.ts";
import type { ContentBroker } from "./content.ts";

/** Callback is bound to a one-use capability; redirects and tools are forbidden. */
export function httpContentBroker(origin: string, capability: string): ContentBroker {
  const base = new URL(origin);
  if (
    !["http:", "https:"].includes(base.protocol) ||
    base.username || base.password || base.search || base.hash || base.pathname !== "/"
  ) throw new Error("INVALID_BROKER_CONFIGURATION");
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(capability))
    throw new Error("INVALID_CAPABILITY");
  return {
    async *model(context: Context, sequence: number, maxOutput: number, signal: AbortSignal) {
      if (sequence !== 1 || !Number.isInteger(maxOutput) || maxOutput < 1 || maxOutput > 2000 ||
          (context.tools?.length ?? 0) !== 0)
        throw new Error("INVALID_ARGUMENT");
      const response = await fetch(new URL("/internal/content/model", base), {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${capability}`,
        },
        body: JSON.stringify({ context, sequence: 1, max_output: maxOutput }),
        signal,
        redirect: "error",
      });
      if (!response.ok || !response.body)
        throw new Error("CONTENT_MODEL_UNAVAILABLE");
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8", { fatal: true });
      let pending = "";
      let total = 0;
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
          if (Buffer.byteLength(pending) > 65536) throw new Error("RESOURCE_LIMIT");
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
  };
}
