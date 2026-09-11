import test from "node:test";
import assert from "node:assert/strict";
import { askView } from "./ask-result.js";
const result = (
  citations: any[],
  execution_status = "completed",
  coverage = "complete",
  answer_status = "answered",
) => ({
  answer: "x",
  citations,
  execution_status,
  answer_status,
  scope_total: 1,
  retrieved_count: 1,
  summarized_count: 1,
  citation_count: citations.length,
  coverage,
  as_of: "",
  filters_applied: {},
  request_id: "",
});
test("keeps service citation index 2", () =>
  assert.equal(
    askView(result([{ index: 2, source_url: "https://a", title: "a" }]))
      .citations[0].index,
    2,
  ));
test("rejects missing or duplicate citation indexes", () => {
  assert.throws(
    () => askView(result([{ source_url: "https://a", title: "a" }])),
    /协议/,
  );
  assert.throws(
    () =>
      askView(
        result([
          { index: 2, source_url: "https://a", title: "a" },
          { index: 2, source_url: "https://b", title: "b" },
        ]),
      ),
    /协议/,
  );
});
test("presents no answer partial failed and cancelled states", () => {
  assert.match(
    askView(result([], "completed", "complete", "no_answer")).status,
    /没有/,
  );
  assert.equal(askView(result([], "failed", "partial")).partial, true);
  assert.match(askView(result([], "cancelled")).status, /取消/);
});
