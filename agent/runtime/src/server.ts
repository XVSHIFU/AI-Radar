import {
  createServer,
  type IncomingMessage,
  type ServerResponse,
} from "node:http";
import { timingSafeEqual } from "node:crypto";
import { loadPolicy } from "./policy.ts";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { once } from "node:events";
import { httpBroker } from "./broker.ts";
import { runResearch, type Broker, type PublicEvent } from "./runner.ts";

type Configuration = {
  token: string;
  system: string;
  policyDigest?: string;
  pythonEnabled?: boolean;
  broker: (capability: string) => Broker;
  deadlineMs?: number;
};
async function body(request: IncomingMessage): Promise<unknown> {
  let length = 0;
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    length += chunk.length;
    if (length > 65536) throw new Error("REQUEST_TOO_LARGE");
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}
function authorized(request: IncomingMessage, token: string) {
  const value = Buffer.from(request.headers.authorization ?? "");
  const expected = Buffer.from(`Bearer ${token}`);
  return value.length === expected.length && timingSafeEqual(value, expected);
}
function reject(response: ServerResponse, status: number, code: string) {
  response.writeHead(status, {
    "content-type": "application/json",
    "cache-control": "no-store",
  });
  response.end(JSON.stringify({ code }));
}

export function createRuntimeServer(config: Configuration) {
  if (Buffer.byteLength(config.token) < 32)
    throw new Error("Runtime authentication must be configured");
  let active = 0;
  return createServer(async (request, response) => {
    if (request.url === "/health" && request.method === "GET") {
      response.end(JSON.stringify({status: "ready", runtime: "pi-agent-core", python: config.pythonEnabled ?? false,
        policy_digest: config.policyDigest}));
      return;
    }
    if (request.method !== "POST" || request.url !== "/v1/run") {
      reject(response, 404, "NOT_FOUND");
      return;
    }
    if (!authorized(request, config.token)) {
      reject(response, 401, "UNAUTHORIZED");
      return;
    }
    if (active >= 2) {
      reject(response, 429, "BUSY");
      return;
    }
    active++;
    const controller = new AbortController();
    const cancel = () => controller.abort();
    response.on("close", cancel);
    const timer = setTimeout(
      () => {
        cancel();
        if (!request.complete) request.destroy();
      },
      Math.min(config.deadlineMs ?? 90000, 90000),
    );
    timer.unref();
    try {
      const payload = await body(request);
      if (!payload || typeof payload !== "object" || Array.isArray(payload))
        throw new Error("INVALID_ARGUMENT");
      const p = payload as Record<string, unknown>;
      if (
        Object.keys(p).some(
          (k) => !["prompt", "max_output", "capability"].includes(k),
        ) ||
        typeof p.prompt !== "string" ||
        Buffer.byteLength(p.prompt) > 24000 ||
        typeof p.max_output !== "number" ||
        !Number.isInteger(p.max_output) ||
        p.max_output < 1 ||
        p.max_output > 2000 ||
        typeof p.capability !== "string" ||
        !/^[A-Za-z0-9_-]{32,128}$/.test(p.capability)
      )
        throw new Error("INVALID_ARGUMENT");
      const broker = config.broker(p.capability);
      response.writeHead(200, {
        "content-type": "application/x-ndjson",
        "cache-control": "no-store",
        "x-accel-buffering": "no",
      });
      const write = async (
        event: PublicEvent | Awaited<ReturnType<typeof runResearch>>,
      ) => {
        controller.signal.throwIfAborted();
        if (!response.write(JSON.stringify(event) + "\n"))
          await once(response, "drain", { signal: controller.signal });
      };
      const result = await runResearch(
        { system: config.system, prompt: p.prompt, maxOutput: p.max_output, pythonEnabled: config.pythonEnabled },
        broker,
        write,
        controller.signal,
      );
      if (!response.destroyed)
        response.end(JSON.stringify({ type: "result", ...result }) + "\n");
    } catch (error) {
      if (!response.headersSent) {
        reject(
          response,
          400,
          error instanceof Error && error.message === "REQUEST_TOO_LARGE"
            ? "REQUEST_TOO_LARGE"
            : "INVALID_ARGUMENT",
        );
      } else if (!response.destroyed)
        response.end(
          JSON.stringify({
            type: "result",
            status: controller.signal.aborted ? "cancelled" : "failed",
            code: controller.signal.aborted
              ? "CANCELLED"
              : "RUNTIME_UNAVAILABLE",
          }) + "\n",
        );
    } finally {
      clearTimeout(timer);
      response.off("close", cancel);
      active--;
    }
  });
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const policy = await loadPolicy(new URL("../../../research/", import.meta.url));
  const token = process.env.RADAR_RUNTIME_TOKEN ?? "";
  const origin = process.env.RADAR_BROKER_ORIGIN ?? "http://127.0.0.1:8000";
  const server = createRuntimeServer({
    token,
    system: policy.system,
    policyDigest: policy.digest,
    pythonEnabled: policy.pythonEnabled,
    broker: (capability) => httpBroker(origin, capability),
  });
  server.requestTimeout = 90000;
  server.headersTimeout = 10000;
  server.listen(
    Number(process.env.PORT ?? 8081),
    process.env.RADAR_RUNTIME_HOST ?? "127.0.0.1",
  );
}
