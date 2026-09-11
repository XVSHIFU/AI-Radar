import test from "node:test";
import assert from "node:assert/strict";
import { idempotentSubmission } from "./submission.js";
test("duplicate submit makes one request and retry retains key", () => {
  const x = idempotentSubmission();
  const a = x.begin();
  assert.equal(x.begin(), undefined);
  x.finish(false);
  assert.equal(x.begin(), a);
  x.finish(true);
  assert.notEqual(x.begin(), a);
});
