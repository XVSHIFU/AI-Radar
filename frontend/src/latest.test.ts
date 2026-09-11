import test from "node:test";
import assert from "node:assert/strict";
import { latestRequest } from "./latest.js";
test("real delayed race only applies newest response and preserves newest loading", async () => {
  const latest = latestRequest();
  let loading = false,
    result = "";
  const first = latest.begin();
  loading = true;
  const second = latest.begin();
  loading = true;
  await Promise.resolve();
  if (first.current()) result = "old";
  if (first.current()) loading = false;
  if (second.current()) result = "new";
  if (second.current()) loading = false;
  assert.equal(result, "new");
  assert.equal(loading, false);
  assert.ok(first.signal.aborted);
});
