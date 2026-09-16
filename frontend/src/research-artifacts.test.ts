import assert from "node:assert/strict";
import test from "node:test";
import { artifactsFrom, fetchArtifact, type ResearchArtifact } from "./research-artifacts";
import { parseSse } from "./sse";

const run = "10000000-0000-4000-8000-000000000001";
const id = "20000000-0000-4000-8000-000000000002";
const artifact = (): ResearchArtifact => ({id, run_id: run, name: "count.json", mime: "application/json",
  size_bytes: 1, download_url: `/api/v1/assistant/runs/${run}/artifacts/${id}`,
  expires_at: new Date(Date.now()+900000).toISOString(), citation_index: 2,
  dataset_ids: [run], as_of: "2026-09-16", timezone: "Asia/Shanghai"});

test("artifact URLs and provenance are constrained even when restored from browser storage", () => {
  assert.equal(artifactsFrom([artifact()], run, [2]).length, 1);
  for (const mutation of [{download_url: "https://example.com"}, {download_url: "//example.com/x"},
    {name: "../secret.json"}, {mime: "text/html"}, {size_bytes: 1048577}, {citation_index: 3},
    {expires_at: "invalid"}, {run_id: id}, {dataset_ids: []}])
    assert.throws(() => artifactsFrom([{...artifact(), ...mutation}], run, [2]));
  assert.throws(() => artifactsFrom([artifact(), artifact()]));
});

async function events(frames: [string, unknown][]) {
  const bytes = new TextEncoder().encode(frames.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join(""));
  const result = [];
  for await (const item of parseSse(new ReadableStream({start(c) {c.enqueue(bytes); c.close();}}))) result.push(item);
  return result;
}
test("artifact frames require research protocol, source citation and matching admitted run", async () => {
  const meta: [string, unknown] = ["meta", {protocol_version: 2, run_id: run}];
  const sources: [string, unknown] = ["sources", {items: [{index: 2}]}];
  const files: [string, unknown] = ["artifacts", {run_id: run, items: [artifact()]}];
  const done: [string, unknown] = ["done", {status: "completed"}];
  assert.equal((await events([meta, sources, files, done])).length, 4);
  await assert.rejects(events([meta, files, sources, done]));
  await assert.rejects(events([sources, files, done]));
  await assert.rejects(events([meta, sources, files, files, done]));
  await assert.rejects(events([meta, ["sources", {items: [{index: 1}]}], files, done]));
});

test("file reads reject expiry, access errors, unexpected MIME and excessive bytes", async () => {
  const previous = globalThis.fetch;
  let calls = 0;
  try {
    globalThis.fetch = async () => {calls++; return new Response("3", {headers: {"content-type": "application/json"}});};
    assert.equal(await (await fetchArtifact(artifact(), new AbortController().signal)).text(), "3");
    await assert.rejects(fetchArtifact({...artifact(), expires_at: "2000-01-01"}, new AbortController().signal), /expired/);
    assert.equal(calls, 1);
    for (const response of [new Response("3", {status: 404}), new Response("3", {headers: {"content-type": "text/html"}}),
      new Response("333", {headers: {"content-type": "application/json"}})]) {
      globalThis.fetch = async () => response;
      await assert.rejects(fetchArtifact(artifact(), new AbortController().signal));
    }
  } finally {globalThis.fetch = previous;}
});
