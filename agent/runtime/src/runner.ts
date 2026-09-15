import {
  Agent,
  type AgentTool,
  type StreamFn,
} from "@earendil-works/pi-agent-core";
import type {
  AssistantMessage,
  Context,
  Model,
  ToolCall,
} from "@earendil-works/pi-ai";
import { createAssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";
import Type from "typebox";

export const TOOL_NAMES = [
  "resolve_entities",
  "search_events",
  "get_event_evidence",
  "aggregate_events",
  "compare_periods",
  "build_chart",
  "load_research_skill",
] as const;
export type ToolName = (typeof TOOL_NAMES)[number];
export type BrokerDelta =
  | { type: "text"; text: string }
  | {
      type: "tool";
      id: string;
      name: string;
      arguments: Record<string, unknown>;
    }
  | { type: "usage"; input: number | null; output: number | null }
  | { type: "finish"; reason: "stop" | "toolUse" | "length" };
export interface Broker {
  model(
    context: Context,
    sequence: number,
    maxOutput: number,
    signal: AbortSignal,
  ): AsyncIterable<BrokerDelta>;
  tool(
    name: ToolName,
    args: unknown,
    callId: string,
    signal: AbortSignal,
  ): Promise<unknown>;
}
export type PublicEvent =
  | { type: "turn"; turn: number }
  | { type: "text"; turn: number; text: string }
  | {
      type: "tool";
      name: string;
      phase: "started" | "finished";
      failed?: boolean;
    };
export type RunInput = { system: string; prompt: string; maxOutput: number };
const object = (fields: Parameters<typeof Type.Object>[0]) =>
  Type.Object(fields, { additionalProperties: false });
const date = Type.String({ pattern: "^\\d{4}-\\d{2}-\\d{2}$" });
const id = Type.String({ pattern: "^[0-9a-fA-F-]{36}$" });
const period = object({ from: date, to: date });
const definitions = [
  {
    name: "resolve_entities",
    description:
      "Resolve names within the authorized scope; ambiguous names require clarification.",
    parameters: object({ name: Type.String({ minLength: 1, maxLength: 100 }) }),
  },
  {
    name: "search_events",
    description:
      "Search the frozen authorized event scope. A page is not the entire result set.",
    parameters: object({
      query: Type.Optional(Type.String({ maxLength: 200 })),
      cursor: Type.Optional(Type.String({ maxLength: 200 })),
      sort: Type.Optional(
        Type.Union([Type.Literal("date"), Type.Literal("importance")]),
      ),
    }),
  },
  {
    name: "get_event_evidence",
    description:
      "Get frozen source paragraphs and citation IDs for authorized events.",
    parameters: object({
      event_ids: Type.Array(id, {
        minItems: 1,
        maxItems: 3,
        uniqueItems: true,
      }),
    }),
  },
  {
    name: "aggregate_events",
    description:
      "Exact database counts; never infer total counts from search pages.",
    parameters: object({
      dimension: Type.Union([
        Type.Literal("category"),
        Type.Literal("date"),
        Type.Literal("date_category"),
      ]),
      granularity: Type.Optional(
        Type.Union([Type.Literal("day"), Type.Literal("month")]),
      ),
    }),
  },
  {
    name: "compare_periods",
    description:
      "Compare two intervals contained in the authorized scope; return counts and an owned dataset.",
    parameters: object({ first: period, second: period }),
  },
  {
    name: "build_chart",
    description:
      "Build a chart only from a dataset returned in this run; numbers are server supplied.",
    parameters: object({
      dataset_id: id,
      kind: Type.Union([
        Type.Literal("bar"),
        Type.Literal("line"),
        Type.Literal("heatmap"),
      ]),
    }),
  },
  {
    name: "load_research_skill",
    description:
      "Read a registered research skill. No file paths, installs or execution.",
    parameters: object({
      name: Type.Union([
        Type.Literal("explain-event"),
        Type.Literal("compare-periods"),
        Type.Literal("verify-evidence"),
      ]),
    }),
  },
] as const;

const MODEL: Model<"openai-completions"> = {
  id: "server-configured",
  name: "Server configured model",
  provider: "radar",
  api: "openai-completions",
  baseUrl: "",
  reasoning: false,
  input: ["text"],
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
  contextWindow: 24_000,
  maxTokens: 2000,
};
function emptyMessage(): AssistantMessage {
  return {
    role: "assistant",
    content: [],
    api: MODEL.api,
    provider: MODEL.provider,
    model: MODEL.id,
    usage: {
      input: 0,
      output: 0,
      cacheRead: 0,
      cacheWrite: 0,
      totalTokens: 0,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
    },
    stopReason: "stop",
    timestamp: Date.now(),
  };
}
const safeError = (error: unknown) =>
  error instanceof Error &&
  [
    "BUDGET_EXCEEDED",
    "INVALID_MODEL_STREAM",
    "RESOURCE_LIMIT",
    "TOOL_UNAVAILABLE",
  ].includes(error.message)
    ? error.message
    : "RUNTIME_UNAVAILABLE";

/** One fresh pi instance per run; no shared transcript, resource discovery or default tools. */
export async function runResearch(
  input: RunInput,
  broker: Broker,
  emit: (event: PublicEvent) => Promise<void>,
  signal: AbortSignal,
) {
  if (
    !Number.isInteger(input.maxOutput) ||
    input.maxOutput < 1 ||
    input.maxOutput > 2000
  )
    throw new Error("INVALID_ARGUMENT");
  let calls = 0,
    business = 0,
    skills = 0,
    inputCharge = 0,
    outputCharge = 0,
    terminal = "";
  const callIds = new Set<string>();
  const streamFn: StreamFn = (_model, rawContext, options) => {
    const stream = createAssistantMessageEventStream();
    const message = emptyMessage();
    void (async () => {
      let observedInput: number | null = null,
        observedOutput: number | null = null;
      let reservedInput = 0,
        reservedOutput = 0,
        started = false;
      try {
        const abort = options?.signal ?? signal;
        abort.throwIfAborted();
        // This is a secondary guard. The Python broker independently owns durable billing.
        if (calls >= 3) throw new Error("BUDGET_EXCEEDED");
        calls++;
        const context = {
          ...rawContext,
          tools: calls === 3 ? [] : rawContext.tools,
        };
        reservedInput = Buffer.byteLength(JSON.stringify(context)) + 1024;
        reservedOutput = Math.min(input.maxOutput, 4800 - outputCharge);
        if (inputCharge + reservedInput > 24000 || reservedOutput < 1)
          throw new Error("BUDGET_EXCEEDED");
        await emit({ type: "turn", turn: calls });
        stream.push({ type: "start", partial: message });
        let finish: "stop" | "toolUse" | "length" | undefined;
        started = true;
        for await (const delta of broker.model(
          context,
          calls,
          reservedOutput,
          abort,
        )) {
          abort.throwIfAborted();
          if (finish && delta.type !== "usage")
            throw new Error("INVALID_MODEL_STREAM");
          if (delta.type === "text") {
            if (Buffer.byteLength(delta.text) > 65536)
              throw new Error("RESOURCE_LIMIT");
            let index = message.content.findIndex((c) => c.type === "text");
            if (index < 0) {
              index = message.content.length;
              message.content.push({ type: "text", text: "" });
              stream.push({
                type: "text_start",
                contentIndex: index,
                partial: message,
              });
            }
            const content = message.content[index];
            if (content?.type !== "text")
              throw new Error("INVALID_MODEL_STREAM");
            content.text += delta.text;
            if (content.text.length > 12000) throw new Error("RESOURCE_LIMIT");
            stream.push({
              type: "text_delta",
              contentIndex: index,
              delta: delta.text,
              partial: message,
            });
            await emit({ type: "text", turn: calls, text: delta.text });
          } else if (delta.type === "tool") {
            if (
              message.content.filter((c) => c.type === "toolCall").length >=
                6 ||
              Buffer.byteLength(JSON.stringify(delta.arguments)) > 16384
            )
              throw new Error("RESOURCE_LIMIT");
            const toolCall: ToolCall = {
              type: "toolCall",
              id: delta.id,
              name: delta.name,
              arguments: delta.arguments,
            };
            const index = message.content.length;
            message.content.push(toolCall);
            stream.push({
              type: "toolcall_start",
              contentIndex: index,
              partial: message,
            });
            stream.push({
              type: "toolcall_end",
              contentIndex: index,
              toolCall,
              partial: message,
            });
          } else if (delta.type === "usage") {
            for (const value of [delta.input, delta.output])
              if (value !== null && (!Number.isSafeInteger(value) || value < 0))
                throw new Error("INVALID_MODEL_STREAM");
            observedInput = delta.input;
            observedOutput = delta.output;
          } else if (delta.type === "finish") finish = delta.reason;
        }
        const hasTools = message.content.some((c) => c.type === "toolCall");
        if (!finish || (finish === "toolUse") !== hasTools)
          throw new Error("INVALID_MODEL_STREAM");
        if (
          inputCharge + (observedInput ?? reservedInput) > 24000 ||
          outputCharge + (observedOutput ?? reservedOutput) > 4800
        )
          throw new Error("BUDGET_EXCEEDED");
        message.stopReason = finish;
        // pi requires numbers, but unknown usage never becomes zero in billing or public output.
        message.usage.input = observedInput ?? reservedInput;
        message.usage.output = observedOutput ?? reservedOutput;
        message.usage.totalTokens = message.usage.input + message.usage.output;
        for (const [i, c] of message.content.entries())
          if (c.type === "text")
            stream.push({
              type: "text_end",
              contentIndex: i,
              content: c.text,
              partial: message,
            });
        stream.push({ type: "done", reason: finish, message });
      } catch (error) {
        terminal = signal.aborted ? "CANCELLED" : safeError(error);
        message.stopReason = signal.aborted ? "aborted" : "error";
        message.errorMessage = terminal;
        stream.push({
          type: "error",
          reason: message.stopReason,
          error: message,
        });
      } finally {
        if (started) {
          inputCharge += observedInput ?? reservedInput;
          outputCharge += observedOutput ?? reservedOutput;
        }
        stream.end(message);
      }
    })();
    return stream;
  };
  const tools: AgentTool[] = definitions.map((definition) => ({
    ...definition,
    label: definition.name,
    execute: async (callId, args, toolSignal) => {
      const abort = toolSignal ?? signal;
      abort.throwIfAborted();
      if (callIds.has(callId)) throw new Error("DUPLICATE_TOOL_CALL");
      callIds.add(callId);
      const isSkill = definition.name === "load_research_skill";
      if (calls >= 3 || (isSkill ? skills >= 2 : business >= 4))
        throw new Error("BUDGET_EXCEEDED");
      if (isSkill) skills++;
      else business++;
      try {
        const result = await broker.tool(definition.name, args, callId, abort);
        abort.throwIfAborted();
        const text = JSON.stringify(result);
        if (Buffer.byteLength(text) > 32768) throw new Error("RESOURCE_LIMIT");
        return { content: [{ type: "text", text }], details: {} };
      } catch (error) {
        throw new Error(safeError(error));
      }
    },
  }));
  const agent = new Agent({
    initialState: {
      systemPrompt: input.system,
      model: MODEL,
      tools,
      thinkingLevel: "off",
    },
    streamFn,
    toolExecution: "sequential",
    getApiKey: () => undefined,
    shouldStopAfterTurn: () =>
      Boolean(terminal) || signal.aborted || calls >= 3,
  });
  agent.subscribe(async (event) => {
    // Arguments, results, thinking fields and raw exceptions never go to the public stream.
    if (event.type === "tool_execution_start")
      await emit({
        type: "tool",
        name: TOOL_NAMES.includes(event.toolName as ToolName)
          ? event.toolName
          : "unsupported",
        phase: "started",
      });
    if (event.type === "tool_execution_end")
      await emit({
        type: "tool",
        name: TOOL_NAMES.includes(event.toolName as ToolName)
          ? event.toolName
          : "unsupported",
        phase: "finished",
        failed: event.isError,
      });
  });
  const abort = () => agent.abort();
  signal.addEventListener("abort", abort, { once: true });
  try {
    signal.throwIfAborted();
    await agent.prompt(input.prompt);
    const last = agent.state.messages.findLast((m) => m.role === "assistant");
    const answer =
      last?.role === "assistant"
        ? last.content
            .filter((c) => c.type === "text")
            .map((c) => c.text)
            .join("")
        : "";
    const completed =
      !terminal &&
      !signal.aborted &&
      last?.role === "assistant" &&
      last.stopReason === "stop";
    return {
      status: completed ? "completed" : signal.aborted ? "cancelled" : "failed",
      answer,
      code: completed ? null : terminal || "BUDGET_EXCEEDED",
      modelCalls: calls,
      businessTools: business,
      skillLoads: skills,
    };
  } finally {
    signal.removeEventListener("abort", abort);
    agent.reset();
  }
}
