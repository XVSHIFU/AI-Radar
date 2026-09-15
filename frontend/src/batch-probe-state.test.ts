import assert from "node:assert/strict";
import test from "node:test";
import { runProbeQueue } from "./batch-probe-state.js";
test("batch probe limits concurrency and treats ok false as failure", async () => {
  let live = 0, peak = 0; const states: string[] = [];
  const outcomes = await runProbeQueue(["a", "b", "c"], async (id) => { live++; peak = Math.max(peak, live); await new Promise((resolve) => setTimeout(resolve, 2)); live--; return { ok: id !== "b", message: id }; }, { stopped: () => false, unauthorized: () => {}, onState: (_id, state) => states.push(state) });
  assert.equal(peak, 2); assert.equal(outcomes.find((x) => x.id === "b")?.state, "failed"); assert.ok(states.includes("success"));
});
test("batch probe stops scheduling after unauthorized", async () => {
  const seen: string[] = []; let stopped = false;
  await runProbeQueue(["a", "b", "c"], async (id) => { seen.push(id); if (id === "a") throw { status: 401 }; return { ok: true, message: "ok" }; }, { stopped: () => stopped, unauthorized: () => { stopped = true; }, onState: () => {} });
  assert.equal(seen.includes("c"), false);
});