import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { parseSse } from "./sse.js";
const byteStream = (text: string) =>
  new ReadableStream<Uint8Array>({
    start(c) {
      for (const b of new TextEncoder().encode(text))
        c.enqueue(Uint8Array.of(b));
      c.close();
    },
  });
const fixture = (name: string) =>
  readFile(new URL(`../../contracts/sse/${name}`, import.meta.url), "utf8");
const collect = async (text: string, signal?: AbortSignal) => {
  const out = [];
  for await (const event of parseSse(byteStream(text), signal)) out.push(event);
  return out;
};
const done = (status: string = "completed") =>
  `event: sources\ndata: {"items":[]}\n\nevent: done\ndata: {"status":"${status}"}\n\n`;
test("four frozen samples survive one-byte CRLF variants", async () => {
  for (const name of ["v1-normal.sse", "v1-empty.sse", "v1-failed.sse"]) {
    const x = (await fixture(name)).replaceAll("\n", "\r\n");
    const out = await collect(x);
    assert.equal(out.at(-1)?.event, "done");
  }
  await assert.rejects(
    () =>
      fixture("v1-truncated.sse").then((x) =>
        collect(x.replaceAll("\n", "\r\n")),
      ),
    /done/,
  );
});
test("failed and cancelled done are terminal non-success states", async () => {
  assert.match(
    (await collect(await fixture("v1-failed.sse"))).at(-1)?.data || "",
    /failed/,
  );
  assert.match(
    (await collect(done("cancelled"))).at(-1)?.data || "",
    /cancelled/,
  );
});
test("rejects invalid protocol ordering and terminal states", async () => {
  await assert.rejects(
    () => collect('event: done\ndata: {"status":"completed"}\n\n'),
    /sources/,
  );
  await assert.rejects(
    () =>
      collect(
        "event: sources\ndata: {}\n\nevent: token\ndata: {}\n\n" + done(),
      ),
    /sources 后/,
  );
  await assert.rejects(
    () => collect(done() + "event: token\ndata: {}\n\n"),
    /done 后/,
  );
  await assert.rejects(
    () => collect(done() + 'event: done\ndata: {"status":"completed"}\n\n'),
    /done 后/,
  );
  await assert.rejects(
    () =>
      collect(
        'event: sources\ndata: {}\n\nevent: done\ndata: {"status":"mystery"}\n\n',
      ),
    /未知/,
  );
  await assert.doesNotReject(() =>
    collect("event: error\ndata: {}\n\n" + done("failed")),
  );
});
test("abort interrupts hanging read, cancels and releases lock", async () => {
  let cancels = 0;
  let release = false;
  let resume!: () => void;
  const stream = new ReadableStream<Uint8Array>({
    pull() {
      return new Promise<void>((r) => (resume = r));
    },
    cancel() {
      cancels++;
    },
  });
  const c = new AbortController();
  const p = (async () => {
    try {
      for await (const _ of parseSse(stream, c.signal)) {
      }
    } catch (e) {
      assert.equal((e as DOMException).name, "AbortError");
      release = true;
    }
  })();
  await new Promise((r) => setTimeout(r, 5));
  c.abort();
  resume();
  await p;
  assert.equal(cancels, 1);
  assert.ok(release);
  const reader = stream.getReader();
  reader.releaseLock();
});

test("error before token rejects completed done", async () => {
  await assert.rejects(
    () =>
      collect("event: error\ndata: {}\n\nevent: token\ndata: {}\n\n" + done()),
    /failed/,
  );
});
test("error after token rejects completed done", async () => {
  await assert.rejects(
    () =>
      collect("event: token\ndata: {}\n\nevent: error\ndata: {}\n\n" + done()),
    /failed/,
  );
});
test("error with failed done passes", async () => {
  await assert.doesNotReject(() =>
    collect("event: error\ndata: {}\n\n" + done("failed")),
  );
});

test("accepts the live ask stream envelope and preserves partial tokens before failure", async () => {
  const stream = [
    'event: meta\ndata: {"request_id":"r1","protocol_version":1}\n\n',
    'event: status\ndata: {"phase":"retrieval","message":"正在检索"}\n\n',
    'event: token\ndata: {"seq":1,"text":"部分正文"}\n\n',
    'event: error\ndata: {"code":"MODEL_UNAVAILABLE","message":"模型不可用","retryable":false,"request_id":"r1"}\n\n',
    'event: sources\ndata: {"items":[]}\n\n',
    'event: done\ndata: {"status":"failed","answer_status":null,"scope_total":0,"retrieved_count":0,"summarized_count":0,"citation_count":0,"coverage":"none"}\n\n',
  ].join("");
  const events = await collect(stream);
  assert.equal(JSON.parse(events.find((event) => event.event === "token")!.data).text, "部分正文");
  assert.equal(JSON.parse(events.at(-1)!.data).status, "failed");
});
test("research v2 replaces drafts while preserving ordered final text and citation gates", async () => {
  const events = [
    ["meta", { protocol_version: 2 }], ["reset", { turn: 1, text: "" }],
    ["token", { turn: 1, seq: 1, text: "draft" }],
    ["reset", { turn: 2, text: "" }], ["token", { turn: 2, seq: 1, text: "final[1]" }],
  ].map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");
  assert.equal((await collect(events + done())).at(-1)?.event, "done");
  await assert.rejects(() => collect(events + 'event: reset\ndata: {"turn":1,"text":""}\n\n' + done()), /草稿/);
  await assert.rejects(() => collect('event: reset\ndata: {"turn":1,"text":""}\n\n' + done()), /草稿/);
  await assert.rejects(() => collect(events + 'event: token\ndata: {"turn":1,"seq":2,"text":"stale"}\n\n' + done()), /顺序/);
});
