import assert from "node:assert/strict";
import test from "node:test";
import { adminRequestGeneration, recordedUsage, usageValue } from "./admin-state.js";

test("invalidating the admin session rejects stale asynchronous results", () => {
  const requests = adminRequestGeneration();
  const request = requests.capture();
  assert.equal(requests.current(request), true);
  requests.invalidate();
  assert.equal(requests.current(request), false);
});

test("usage formatting keeps unknown token and recording values explicit", () => {
  assert.equal(usageValue(null), "未知");
  assert.equal(recordedUsage(null), "记录次数未知");
  assert.equal(recordedUsage(457), "已记录 457 次");
});