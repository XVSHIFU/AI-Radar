import assert from "node:assert/strict";
import { once } from "node:events";
import test from "node:test";
import { createRuntimeServer } from "../src/server.ts";
import type { Broker } from "../src/runner.ts";

test("HTTP client disconnect aborts the active upstream model without retry", async () => {
  let paid = 0;
  let settleAbort: () => void = () => {};
  const aborted = new Promise<void>((resolve) => {
    settleAbort = resolve;
  });
  const broker: Broker = {
    async *model(_context, _seq, _max, signal) {
      paid++;
      try {
        yield { type: "text", text: "first-token" };
        await new Promise<void>((resolve) => {
          if (signal.aborted) resolve();
          else
            signal.addEventListener("abort", () => resolve(), { once: true });
        });
        signal.throwIfAborted();
      } finally {
        settleAbort();
      }
    },
    async tool() {
      throw new Error("Unexpected tool");
    },
  };
  const token = "runtime-disconnect-test-secret-123456789";
  const server = createRuntimeServer({
    token,
    system: "Research",
    broker: () => broker,
    deadlineMs: 2000,
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert(address && typeof address === "object");
  const controller = new AbortController();
  try {
    const response = await fetch(`http://127.0.0.1:${address.port}/v1/run`, {
      method: "POST",
      headers: { authorization: `Bearer ${token}` },
      body: JSON.stringify({
        prompt: "Hello",
        max_output: 1600,
        capability: "a".repeat(43),
      }),
      signal: controller.signal,
    });
    const reader = response.body!.getReader();
    let text = "";
    while (!text.includes("first-token")) {
      const chunk = await reader.read();
      assert(!chunk.done);
      text += new TextDecoder().decode(chunk.value);
    }
    controller.abort();
    await Promise.race([
      aborted,
      new Promise((_, reject) => {
        const timer = setTimeout(
          () => reject(new Error("upstream did not cancel")),
          500,
        );
        timer.unref();
      }),
    ]);
    assert.equal(paid, 1);
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  } finally {
    controller.abort();
    server.closeAllConnections();
    server.close();
    await once(server, "close");
  }
});
