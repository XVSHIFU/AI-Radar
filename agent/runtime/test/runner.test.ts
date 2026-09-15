import assert from "node:assert/strict";
import test from "node:test";
import {
  runResearch,
  TOOL_NAMES,
  type Broker,
  type BrokerDelta,
  type PublicEvent,
} from "../src/runner.ts";

const input = {
  system: "Use only registered tools. Cite saved evidence.",
  prompt: "Compare the periods.",
  maxOutput: 1600,
};
const tool = (
  id: string,
  name: string,
  args: Record<string, unknown>,
): BrokerDelta => ({ type: "tool", id, name, arguments: args });
const finish: BrokerDelta = { type: "finish", reason: "toolUse" };
const usage: BrokerDelta = { type: "usage", input: 30, output: 10 };

test("real pi core runs two dependent tools then streams a final answer; no default tools", async () => {
  const executed: string[] = [],
    events: PublicEvent[] = [];
  let firstTextBeforeFinish = false;
  const broker: Broker = {
    async *model(context, sequence) {
      assert.deepEqual(
        context.tools?.map((t) => t.name),
        sequence === 3 ? [] : [...TOOL_NAMES],
      );
      if (sequence === 1) {
        yield tool("aggregate", "aggregate_events", { dimension: "category" });
        yield usage;
        yield finish;
      } else if (sequence === 2) {
        assert(
          context.messages.some(
            (m) => m.role === "toolResult" && m.toolName === "aggregate_events",
          ),
        );
        yield tool("chart", "build_chart", {
          dataset_id: "10000000-0000-4000-8000-000000000001",
          kind: "bar",
        });
        yield usage;
        yield finish;
      } else {
        yield { type: "text", text: "The count is " };
        firstTextBeforeFinish = events.some(
          (e) => e.type === "text" && e.text === "The count is ",
        );
        yield { type: "text", text: "3 [1]." };
        yield usage;
        yield { type: "finish", reason: "stop" };
      }
    },
    async tool(name) {
      executed.push(name);
      return { dataset_id: "10000000-0000-4000-8000-000000000001", count: 3 };
    },
  };
  const result = await runResearch(
    input,
    broker,
    async (event) => {
      events.push(event);
    },
    new AbortController().signal,
  );
  assert.equal(result.status, "completed");
  assert.equal(result.answer, "The count is 3 [1].");
  assert.deepEqual(executed, ["aggregate_events", "build_chart"]);
  assert.equal(result.modelCalls, 3);
  assert(firstTextBeforeFinish, "a whole-answer replay is not streaming");
});

test("tools execute sequentially and the fifth business call never reaches the broker", async () => {
  let active = 0,
    maximum = 0,
    executed = 0;
  const broker: Broker = {
    async *model(_context, sequence) {
      if (sequence === 1) {
        for (let i = 0; i < 5; i++)
          yield tool(String(i), "aggregate_events", { dimension: "category" });
        yield finish;
      } else {
        yield { type: "text", text: "Partial result." };
        yield { type: "finish", reason: "stop" };
      }
      yield usage;
    },
    async tool() {
      active++;
      maximum = Math.max(maximum, active);
      await new Promise((r) => setTimeout(r, 2));
      executed++;
      active--;
      return { count: 1 };
    },
  };
  await runResearch(
    input,
    broker,
    async () => {},
    new AbortController().signal,
  );
  assert.equal(maximum, 1);
  assert.equal(executed, 4);
});

test("extra scope fields, shell calls and duplicate IDs cannot execute", async () => {
  const executed: string[] = [];
  const broker: Broker = {
    async *model(_context, sequence) {
      if (sequence === 1) {
        yield tool("escape", "shell", { command: "read deployment secrets" });
        yield tool("scope", "aggregate_events", {
          dimension: "category",
          scope_id: "other-user",
        });
        yield tool("once", "aggregate_events", { dimension: "category" });
        yield tool("once", "aggregate_events", { dimension: "category" });
        yield finish;
      } else {
        yield { type: "text", text: "Cannot access that scope." };
        yield { type: "finish", reason: "stop" };
      }
      yield usage;
    },
    async tool(name) {
      executed.push(name);
      return { count: 0 };
    },
  };
  await runResearch(
    input,
    broker,
    async () => {},
    new AbortController().signal,
  );
  assert.deepEqual(executed, ["aggregate_events"]);
});

test("a fourth paid model call cannot start even if the third asks for more tools", async () => {
  let paid = 0,
    tools = 0;
  const broker: Broker = {
    async *model(_context, sequence) {
      paid++;
      yield tool(String(sequence), "aggregate_events", {
        dimension: "category",
      });
      yield usage;
      yield finish;
    },
    async tool() {
      tools++;
      return { count: 0 };
    },
  };
  const result = await runResearch(
    input,
    broker,
    async () => {},
    new AbortController().signal,
  );
  assert.equal(paid, 3);
  assert.equal(tools, 2);
  assert.equal(result.status, "failed");
});

test("oversized input is rejected before any paid request", async () => {
  let paid = 0;
  const broker: Broker = {
    async *model() {
      paid++;
      yield { type: "finish", reason: "stop" };
    },
    async tool() {
      return {};
    },
  };
  const result = await runResearch(
    { ...input, prompt: "中".repeat(24000) },
    broker,
    async () => {},
    new AbortController().signal,
  );
  assert.equal(paid, 0);
  assert.equal(result.code, "BUDGET_EXCEEDED");
});

test("abort propagates to active model stream, preserves draft and never retries", async () => {
  const controller = new AbortController();
  let paid = 0,
    closed = false;
  const broker: Broker = {
    async *model(_context, _sequence, _max, signal) {
      paid++;
      try {
        yield { type: "text", text: "draft" };
        signal.throwIfAborted();
        yield { type: "finish", reason: "stop" };
      } finally {
        closed = true;
      }
    },
    async tool() {
      throw new Error("must not execute");
    },
  };
  const result = await runResearch(
    input,
    broker,
    async (event) => {
      if (event.type === "text") controller.abort();
    },
    controller.signal,
  );
  assert.equal(result.status, "cancelled");
  assert.equal(paid, 1);
  assert(closed);
});

test("broken provider streams fail with a generic error instead of publishing success", async () => {
  const broker: Broker = {
    async *model() {
      yield { type: "text", text: "unverified draft" };
      throw new Error("secret upstream URL");
    },
    async tool() {
      return {};
    },
  };
  const result = await runResearch(
    input,
    broker,
    async () => {},
    new AbortController().signal,
  );
  assert.equal(result.status, "failed");
  assert.equal(result.code, "RUNTIME_UNAVAILABLE");
  assert(!JSON.stringify(result).includes("secret"));
});

test("separate runs never reuse transcript or environment API keys", async () => {
  const old = process.env.OPENAI_API_KEY;
  process.env.OPENAI_API_KEY = "secret-test-key";
  const prompts: string[] = [];
  const broker: Broker = {
    async *model(context) {
      const body = JSON.stringify(context);
      assert(!body.includes("secret-test-key"));
      prompts.push(body);
      yield { type: "text", text: "Hello" };
      yield usage;
      yield { type: "finish", reason: "stop" };
    },
    async tool() {
      return {};
    },
  };
  try {
    await runResearch(
      { ...input, prompt: "private-first-user" },
      broker,
      async () => {},
      new AbortController().signal,
    );
    await runResearch(
      { ...input, prompt: "second-user" },
      broker,
      async () => {},
      new AbortController().signal,
    );
    assert(!prompts[1]?.includes("private-first-user"));
  } finally {
    if (old === undefined) delete process.env.OPENAI_API_KEY;
    else process.env.OPENAI_API_KEY = old;
  }
});
