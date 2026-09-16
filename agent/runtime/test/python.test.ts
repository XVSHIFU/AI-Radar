import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { runResearch, type Broker } from "../src/runner.ts";
import { validatePolicy } from "../src/policy.ts";

test("Python needs explicit policy activation and remains once per research run", async () => {
  for (const enabled of [false, true]) {
    const executed: string[] = [];
    const broker: Broker = {
      async *model(context, sequence) {
        if (sequence === 1) {
          assert.equal(context.tools?.some(t => t.name === "run_python"), enabled);
          for (const id of ["first", "second"]) yield {type: "tool", id, name: "run_python",
            arguments: {code: "print(3)", dataset_ids: ["10000000-0000-4000-8000-000000000001"]}};
          yield {type: "usage", input: 10, output: 10};
          yield {type: "finish", reason: "toolUse"};
        } else {
          yield {type: "text", text: "Result [1]."};
          yield {type: "usage", input: 10, output: 10};
          yield {type: "finish", reason: "stop"};
        }
      },
      async tool(name) { executed.push(name); return {stdout: "3", citation_index: 1}; },
    };
    await runResearch({system: "Use only authorized tools", prompt: "Analyze", maxOutput: 512,
                       pythonEnabled: enabled}, broker, async () => {}, new AbortController().signal);
    assert.deepEqual(executed, enabled ? ["run_python"] : []);
  }
});

test("enabled Python policy still enforces every isolation limit", async () => {
  const raw = JSON.parse(await readFile(new URL("../../../research/policy.json", import.meta.url), "utf8"));
  raw.python.enabled = true;
  validatePolicy(raw);
  raw.python.guest_tasks = 32;
  assert.throws(() => validatePolicy(raw), /INVALID_POLICY/);
});
