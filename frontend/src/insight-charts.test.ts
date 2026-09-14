import assert from "node:assert/strict";
import test from "node:test";
import { categoryBuckets, categoryTotal } from "./insight-charts";

test("keeps zero categories and each daily joint count", () => {
  const buckets = categoryBuckets([{ date: "2026-09-01", category: "research", count: 2 }, { date: "2026-09-02", category: "product", count: 1 }], false);
  assert.equal(buckets.length, 2);
  assert.equal(buckets[0].counts.agent_tool, 0);
  assert.equal(categoryTotal(buckets), 3);
});
test("rolls long ranges into natural months without extending endpoints", () => {
  const buckets = categoryBuckets([{ date: "2026-01-30", category: "research", count: 1 }, { date: "2026-02-02", category: "research", count: 2 }], true);
  assert.deepEqual(buckets.map(({ from, to, total }) => ({ from, to, total })), [{ from: "2026-01-30", to: "2026-01-30", total: 1 }, { from: "2026-02-02", to: "2026-02-02", total: 2 }]);
  assert.equal(categoryTotal(buckets), 3);
});
