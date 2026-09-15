import { readFile } from "node:fs/promises";
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPolicy, validatePolicy } from "../src/policy.ts";

const root = new URL("../../../research/", import.meta.url);
test("packaged policy loads only the implemented limits and disabled Python", async () => {
  const policy = await loadPolicy(root);
  assert.match(policy.digest, /^[a-f0-9]{64}$/);
  assert.ok(policy.system.length > 100);
});
test("runtime refuses relaxed or incorrectly typed permission contracts", async () => {
  const raw = await readFile(new URL("policy.json", root), "utf8");
  for (const mutate of [
    (p: any) => p.limits.automatic_paid_retries = false,
    (p: any) => p.limits.model_calls_per_run = 4,
    (p: any) => p.memory.shared_user_memory = true,
    (p: any) => p.memory.ip_is_identity = true,
    (p: any) => p.python.enabled = true,
    (p: any) => p.tools.push("shell"),
    (p: any) => p.forbidden_capabilities = [],
  ]) {
    const policy = JSON.parse(raw); mutate(policy);
    assert.throws(() => validatePolicy(policy), /INVALID_POLICY/);
  }
});
