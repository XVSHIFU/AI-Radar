import assert from "node:assert/strict";
import test from "node:test";
import { contentApi } from "./content-api.js";

test("content workbench uses admin cookies and CSRF for manual and Agent writes", async () => {
  const originalFetch = globalThis.fetch;
  const calls: Array<{ path: string; init: RequestInit }> = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    calls.push({ path: String(input), init });
    if (String(input).endsWith("/export")) return Response.json({ prompt: "task", task_ids: ["task-1"] });
    if (String(input).endsWith("/import")) return Response.json({ items: [{ task_id: "task-1", status: "needs_review", draft_id: "draft-1", errors: [] }] });
    if (String(input).endsWith("/batches")) return Response.json({ id: "batch-1", status: "queued", items: [] });
    return Response.json({ items: [{ id: "task-1", article_version_id: "article-1" }] });
  }) as typeof fetch;
  try {
    await contentApi.createTasks("csrf-value", ["article-1"]);
    await contentApi.export("csrf-value", ["task-1"]);
    await contentApi.import("csrf-value", "```json\n{}\n```");
    await contentApi.startBatch("csrf-value", ["task-1"]);
    await contentApi.skipTask("csrf-value", "task-1");
    assert.deepEqual(calls.map(call => call.path), [
      "/api/v1/admin/content/tasks", "/api/v1/admin/content/export",
      "/api/v1/admin/content/import", "/api/v1/admin/content/batches", "/api/v1/admin/content/tasks/task-1/skip",
    ]);
    assert.ok(calls.every(call => call.init.credentials === "same-origin")); // Credentials stay in the existing admin session cookie.
    assert.ok(calls.every(call => call.init.method === "POST"));
    assert.ok(calls.every(call => (call.init.headers as Record<string, string>)["X-CSRF-Token"] === "csrf-value"));
    assert.deepEqual(JSON.parse(String(calls[0].init.body)), { article_version_ids: ["article-1"] });
    assert.deepEqual(JSON.parse(String(calls[1].init.body)), { task_ids: ["task-1"] });
    assert.deepEqual(JSON.parse(String(calls[2].init.body)), { text: "```json\n{}\n```" });
    assert.deepEqual(JSON.parse(String(calls[3].init.body)), { task_ids: ["task-1"] });
    assert.equal(calls[4].init.body, undefined);
  } finally { globalThis.fetch = originalFetch; }
});
