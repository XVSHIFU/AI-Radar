import assert from "node:assert/strict";
import test from "node:test";
import { ask, askStream, assistantQuota, refreshAssistantQuota } from "./api";

test("anonymous initialization is shared and both paid endpoints wait for it", async () => {
  const original = globalThis.fetch;
  const paths: string[] = [];
  let release: (() => void) | undefined;
  const ready = new Promise<void>(resolve => { release = resolve; });
  globalThis.fetch = async (input) => {
    const path = String(input);
    paths.push(path);
    if (path.endsWith("/session")) {
      await ready;
      return Response.json({ quota: { remaining: 7, limit: 20, window_hours: 48, next_available_at: null } });
    }
    return Response.json({ answer: "" });
  };
  try {
    const stream = askStream({ question: "first" });
    const regular = ask({ question: "follow-up" });
    assert.deepEqual(paths, ["/api/v1/assistant/session"]);
    release!();
    await Promise.all([stream, regular]);
    await refreshAssistantQuota();
    assert.equal(paths.filter(p => p === "/api/v1/ask").length, 1);
    assert.equal(paths.filter(p => p === "/api/v1/ask/stream").length, 1);
    assert.equal(assistantQuota.value?.remaining, 7);
  } finally { globalThis.fetch = original; }
});

test("failed quota initialization never falls through to a model request", async () => {
  const original = globalThis.fetch;
  const paths: string[] = [];
  globalThis.fetch = async input => {
    paths.push(String(input));
    return Response.json({ code: "ASSISTANT_QUOTA_UNAVAILABLE", message: "Unavailable" }, { status: 503 });
  };
  try {
    await assert.rejects(askStream({ question: "question" }), { code: "ASSISTANT_QUOTA_UNAVAILABLE" });
    assert.deepEqual(paths, ["/api/v1/assistant/session"]);
  } finally { globalThis.fetch = original; }
});
