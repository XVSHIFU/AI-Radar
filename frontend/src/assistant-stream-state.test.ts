import assert from "node:assert/strict";
import test from "node:test";
import { initialStreamState, reduceStream } from "./assistant-stream-state.js";
const citations = [{ index: 1, title: "x", source_url: "https://example.com" }];
test("stream citations become formal only after successful done", () => { const pending = reduceStream(initialStreamState(), "sources", { items: citations }); assert.equal(pending.pendingCitations.length, 1); assert.equal(reduceStream(pending, "done", { status: "completed" }).terminal, "completed"); });
test("error and EOF discard pending citations without becoming completed", () => { const pending = reduceStream(initialStreamState(), "sources", { items: citations }); const failed = reduceStream(reduceStream(pending, "error"), "done", { status: "completed" }); assert.equal(failed.terminal, "error"); assert.equal(failed.pendingCitations.length, 0); assert.equal(reduceStream(pending, "eof").terminal, "interrupted"); });
test("a new research draft drops prior citations; terminal errors cannot be reset", () => {
  const draft = reduceStream(initialStreamState(), "sources", { items: citations });
  assert.equal(reduceStream(draft, "reset").pendingCitations.length, 0);
  const failed = reduceStream(draft, "error");
  assert.equal(reduceStream(failed, "reset").terminal, "error");
  assert.equal(reduceStream(failed, "sources", { items: citations }).pendingCitations.length, 0);
});
