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
