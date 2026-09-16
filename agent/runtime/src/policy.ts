import { createHash } from "node:crypto";
import { readFile, lstat } from "node:fs/promises";
import { TOOL_NAMES } from "./runner.ts";

const limits = {
  ip_questions: 5, ip_window_seconds: 172800, model_calls_per_run: 3,
  business_tool_calls_per_run: 4, skill_loads_per_run: 2, python_calls_per_run: 1,
  input_tokens_per_run: 24000, output_tokens_per_run: 4800,
  run_deadline_seconds: 90, automatic_paid_retries: 0, global_concurrent_runs: 2,
};
const pythonLimits = {"network": "none", "read_only_rootfs": true, "non_root": true, "drop_all_capabilities": true, "no_new_privileges": true, "host_mounts": false, "docker_socket": false, "cpu_cores": 1, "memory_mib": 256, "pids": 32, "execution_seconds": 10, "job_deadline_seconds": 30, "scratch_mib": 32, "input_bytes": 2097152, "dataset_rows": 10000, "code_bytes": 16384, "stdout_bytes": 65536, "artifact_bytes": 1048576, "artifact_types": ["application/json", "text/csv", "image/png"], "requires_isolation_verification": true, "guest_tasks": 2};
const forbidden = ["shell", "host_files", "arbitrary_network", "database_write", "admin_api",
  "container_control", "install_packages", "install_plugins", "self_modify", "spawn_agents", "background_jobs"];
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("INVALID_POLICY");
  return value as Record<string, unknown>;
}
export function validatePolicy(raw: unknown) {
  const policy = object(raw), configured = object(policy.limits), memory = object(policy.memory);
  const denied = policy.forbidden_capabilities, names = policy.tools;
  if (policy.runtime !== "pi-agent-core" || policy.default_allow !== false ||
      Object.keys(configured).length !== Object.keys(limits).length ||
      Object.entries(limits).some(([key, value]) => configured[key] !== value) ||
      !Array.isArray(denied) || forbidden.some(key => !denied.includes(key)) ||
      !Array.isArray(names) || names.length !== TOOL_NAMES.length + 1 ||
      [...TOOL_NAMES, "run_python"].some(key => !names.includes(key)) ||
      typeof object(policy.python).enabled !== "boolean" ||
      Object.keys(object(policy.python)).length !== Object.keys(pythonLimits).length + 1 ||
      Object.entries(pythonLimits).some(([key, value]) => JSON.stringify(object(policy.python)[key]) !== JSON.stringify(value)) || memory.summary_tokens !== 1200 ||
      ["shared_user_memory", "ip_is_identity", "server_persistent_transcripts", "policy_writable_by_agent"]
        .some(key => memory[key] !== false)) throw new Error("INVALID_POLICY");
}
export async function loadPolicy(root: URL) {
  const policyPath = new URL("policy.json", root), systemPath = new URL("SYSTEM.md", root);
  const stats = await Promise.all([lstat(policyPath), lstat(systemPath)]);
  if (stats.some(value => !value.isFile() || value.isSymbolicLink()) ||
      stats[0]!.size > 16384 || stats[1]!.size > 8192) throw new Error("INVALID_POLICY");
  const [raw, system] = await Promise.all([readFile(policyPath), readFile(systemPath)]);
  validatePolicy(JSON.parse(raw.toString("utf8")));
  const digest = createHash("sha256").update(raw).update("\0").update(system).digest("hex");
  return {system: system.toString("utf8"), digest, pythonEnabled: object(JSON.parse(raw.toString("utf8")).python).enabled === true};
}
