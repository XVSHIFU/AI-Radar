import assert from "node:assert/strict";
import { once } from "node:events";
import test from "node:test";
import { createRuntimeServer } from "../src/server.ts";
import { CONTENT_SYSTEM, type ContentBroker } from "../src/content.ts";
import { httpContentBroker } from "../src/content-broker.ts";

test("content route uses one pi model turn, zero tools, and only a terminal result", async () => {
  let calls = 0;
  const seen: string[] = [];
  const broker: ContentBroker = {
    async *model(context, sequence, maxOutput) {
      calls++;
      assert.equal(sequence, 1);
      assert.equal(maxOutput, 160);
      assert.deepEqual(context.tools, []);
      assert.equal(context.systemPrompt, CONTENT_SYSTEM);
      seen.push(JSON.stringify(context));
      yield { type: "text", text: '{"task_id":"t1"}' };
      yield { type: "usage", input: 31, output: 12 };
      yield { type: "finish", reason: "stop" };
    },
  };
  const token = "content-runtime-secret-1234567890123456789";
  const server = createRuntimeServer({
    token,
    system: "Research-only instructions",
    broker: () => { throw new Error("research broker must not run"); },
    contentBroker: () => broker,
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert(address && typeof address === "object");
  const url = `http://127.0.0.1:${address.port}/v1/content`;
  const payload = { prompt: "Export task t1", max_output: 160, capability: "a".repeat(64) };
  try {
    const unauthorized = await fetch(url, { method: "POST", body: JSON.stringify(payload) });
    assert.equal(unauthorized.status, 401);
    const invalid = await fetch(url, {
      method: "POST",
      headers: { authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...payload, tools: ["run_python"] }),
    });
    assert.equal(invalid.status, 400);
    assert.equal(calls, 0);
    const response = await fetch(url, {
      method: "POST",
      headers: { authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    });
    assert.equal(response.status, 200);
    const lines = (await response.text()).trim().split("\n").map((line) => JSON.parse(line));
    assert.deepEqual(lines, [{
      type: "result", status: "completed", content: '{"task_id":"t1"}',
      usage: { input: 31, output: 12 },
    }]);
    assert.equal(calls, 1);
    assert(!seen[0]?.includes("Research-only instructions"));
  } finally {
    server.closeAllConnections();
    server.close();
    await once(server, "close");
  }
});

test("provider tool call fails content run without another model call", async () => {
  let calls = 0;
  const broker: ContentBroker = {
    async *model() {
      calls++;
      yield { type: "tool", id: "x", name: "run_python", arguments: {} };
      yield { type: "finish", reason: "toolUse" };
    },
  };
  const result = await (await import("../src/content.ts")).runContent(
    "Task", 100, broker, new AbortController().signal,
  );
  assert.equal(result.status, "failed");
  assert.equal(result.content, "");
  assert.deepEqual(result.usage, { input: null, output: null });
  assert.equal(calls, 1);
});

test("content broker posts once to bound callback with no redirect following", async () => {
  const original = globalThis.fetch;
  const calls: Array<{ url: string; init: RequestInit }> = [];
  globalThis.fetch = async (input, init) => {
    calls.push({ url: String(input), init: init ?? {} });
    return new Response(
      '{"type":"text","text":"done"}\n{"type":"usage","input":3,"output":2}\n{"type":"finish","reason":"stop"}\n',
      { status: 200 },
    );
  };
  try {
    const broker = httpContentBroker("http://127.0.0.1:8000", "a".repeat(64));
    const deltas = [];
    for await (const delta of broker.model({ systemPrompt: CONTENT_SYSTEM, messages: [], tools: [] }, 1, 100, new AbortController().signal))
      deltas.push(delta);
    assert.equal(deltas.length, 3);
    assert.equal(calls.length, 1);
    assert.equal(calls[0]?.url, "http://127.0.0.1:8000/internal/content/model");
    assert.equal(calls[0]?.init.redirect, "error");
    assert.deepEqual(JSON.parse(String(calls[0]?.init.body)), {
      context: { systemPrompt: CONTENT_SYSTEM, messages: [], tools: [] },
      sequence: 1, max_output: 100,
    });
    assert.equal((calls[0]?.init.headers as Record<string, string>).authorization, `Bearer ${"a".repeat(64)}`);
  } finally {
    globalThis.fetch = original;
  }
});
