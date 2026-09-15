export type ProbeOutcome = { id: string; state: "success" | "failed" | "skipped"; message?: string };
export async function runProbeQueue(ids: string[], probe: (id: string) => Promise<{ ok: boolean; message: string }>, options: { concurrency?: number; stopped: () => boolean; unauthorized: () => void; onState: (id: string, state: "pending" | "running" | "success" | "failed" | "skipped", message?: string) => void }) {
  const queue = [...ids]; const outcomes: ProbeOutcome[] = []; const concurrency = options.concurrency ?? 2;
  ids.forEach((id) => options.onState(id, "pending"));
  const worker = async () => { while (queue.length && !options.stopped()) { const id = queue.shift()!; options.onState(id, "running"); try { const result = await probe(id); const state = result.ok ? "success" : "failed"; outcomes.push({ id, state, message: result.message }); options.onState(id, state, result.message); } catch (error) { const status = typeof error === "object" && error && "status" in error ? (error as { status?: number }).status : undefined; if (status === 401) { options.unauthorized(); return; } outcomes.push({ id, state: "failed" }); options.onState(id, "failed", "探测请求失败"); } } };
  await Promise.all(Array.from({ length: concurrency }, worker));
  while (queue.length) { const id = queue.shift()!; outcomes.push({ id, state: "skipped" }); options.onState(id, "skipped"); }
  return outcomes;
}