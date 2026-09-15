import { ref } from "vue";
import { demoEvents, demoToday, demoRevision } from "./demo-events";
export type Category =
  | "model_release"
  | "agent_tool"
  | "framework_sdk"
  | "research"
  | "product"
  | "industry";
export type Event = {
  id: string;
  title_zh: string;
  summary_zh: string;
  category: Category;
  importance: number;
  event_date: string | null;
  date_precision: string;
  source_count: number;
  evidence_count: number;
  entities: string[];
  content_version: number;
  articles?: Article[];
  evidence?: Evidence[];
};
export type Evidence = {
  id: string;
  event_id: string;
  article_version_id: string;
  paragraph_id: string;
  quote_text: string;
  source_url: string;
  title: string;
  verification_status: string;
  source_published_at?: string;
  event_date?: string;
};
export type Article = { title: string; source_url: string; language?: string };
export type ApiError = {
  data_mode?: string;
  details?: { query_plan_public?: { data_mode?: string } | unknown };
  code: string;
  message: string;
  retryable?: boolean;
  request_id?: string;
  status?: number;
};
export type EventQuery = {
  q?: string;
  category?: Category;
  date_from?: string;
  date_to?: string;
  min_importance?: number;
  limit: number;
  cursor?: string;
};
export type EventResult = {
  items: Event[];
  total: number;
  total_relation: "eq";
  next_cursor: string | null;
  as_of: string;
  data_revision: string;
  request_id: string;
};
const demo = () =>
  typeof location !== "undefined" &&
  new URLSearchParams(location.search).get("demo") === "1";
export const dataMode = ref(demo() ? "fixture" : "live");
export const isDemo = () => demo();
type ModeResponse = {
  data_mode?: unknown;
  details?: { query_plan_public?: { data_mode?: unknown } | unknown };
};
export function updateDataMode(response: ModeResponse) {
  const plan = response.details?.query_plan_public;
  const planMode =
    plan && typeof plan === "object" && "data_mode" in plan
      ? plan.data_mode
      : undefined;
  const mode = response.data_mode ?? planMode;
  if (mode === "fixture") dataMode.value = "fixture";
  else if (mode === "postgres") dataMode.value = "live";
}
function err(e: unknown): ApiError {
  return typeof e === "object" && e && "code" in e
    ? (e as ApiError)
    : {
        code: "NETWORK_ERROR",
        message: e instanceof Error ? e.message : "网络请求失败",
        retryable: true,
      };
}
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin", ...init });
  if (!response.ok) {
    let body: ApiError = {
      code: `HTTP_${response.status}`,
      message: "服务请求失败",
      status: response.status,
    };
    try {
      body = { ...body, ...(await response.json()) };
    } catch {}
    updateDataMode(body);
    throw body;
  }
  const result = (await response.json()) as T & { data_mode?: string };
  updateDataMode(result);
  return result;
}
function filter(q: EventQuery) {
  const rows = demoEvents.filter(
    (x) =>
      (!q.q ||
        `${x.title_zh} ${x.summary_zh} ${x.entities.join(" ")}`
          .toLowerCase()
          .includes(q.q.toLowerCase())) &&
      (!q.category || x.category === q.category) &&
      (!q.date_from || (x.event_date ?? "") >= q.date_from) &&
      (!q.date_to || (x.event_date ?? "") <= q.date_to) &&
      (!q.min_importance || x.importance >= q.min_importance),
  );
  const start = Number(q.cursor || 0);
  return {
    items: rows.slice(start, start + q.limit),
    total: rows.length,
    total_relation: "eq" as const,
    next_cursor: start + q.limit < rows.length ? String(start + q.limit) : null,
    as_of: demoToday + "T00:00:00+08:00",
    data_revision: demoRevision,
    request_id: "demo-events",
  };
}
export type Stats = {
  total_events: number;
  total_sources: number;
  categories: Record<string, number>;
  scope: string;
  as_of: string;
  data_revision: string;
};
export const stats = () =>
  demo()
    ? Promise.resolve({
        total_events: demoEvents.length,
        total_sources: 12,
        categories: demoEvents.reduce(
          (a, x) => ({ ...a, [x.category]: (a[x.category] || 0) + 1 }),
          {} as Record<string, number>,
        ),
        scope: "global",
        as_of: demoToday + "T00:00:00+08:00",
        data_revision: demoRevision,
      })
    : api<Stats>("/api/v1/stats");
export const events = {
  list: (q: EventQuery, signal?: AbortSignal) =>
    demo()
      ? Promise.resolve(filter(q))
      : api<EventResult>(
          "/api/v1/events?" +
            new URLSearchParams(
              Object.entries(q).filter(
                ([, v]) => v !== undefined && v !== "",
              ) as [string, string][],
            ),
          { signal },
        ),
  one: (id: string, signal?: AbortSignal) =>
    demo()
      ? Promise.resolve(demoEvents.find((x) => x.id === id) as Event)
      : api<Event>(`/api/v1/events/${id}`, { signal }),
  evidence: (id: string, signal?: AbortSignal) =>
    demo()
      ? Promise.resolve([
          {
            id: "demo-evidence-" + id,
            event_id: id,
            article_version_id: "demo-article-v1",
            paragraph_id: "demo-p-001",
            quote_text:
              "这是演示模式提供的合成段落摘录，不是已保存的原文证据。",
            source_url: "https://example.invalid/demo",
            title: "合成演示来源",
            verification_status: "demo",
          },
        ])
      : api<{ items: Evidence[] }>(`/api/v1/events/${id}/evidence`, {
          signal,
        }).then((x) => x.items),
};
export const ask = (payload: unknown, signal?: AbortSignal) =>
  api<AskResult>("/api/v1/ask", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
export type Citation = {
  index: number;
  source_url: string;
  title: string;
  quote_text?: string;
  paragraph_id?: string;
};
export type AskResult = {
  answer: string | null;
  citations: Citation[];
  execution_status: string;
  answer_status: string;
  scope_total: number;
  retrieved_count: number;
  summarized_count: number;
  citation_count: number;
  coverage: string;
  as_of: string;
  filters_applied: unknown;
  request_id: string;
};
export type AdminSession = { authenticated: boolean; csrf_token?: string; expires_at?: string };
export type Source = { id: string; name: string; feed_url: string; channel_type: string; editable: boolean; enabled: boolean; health: string; last_success_at: string | null; consecutive_failures: number; last_checked_at: string | null; cooldown_until: string | null };
export type ProbeResult = { ok: boolean; checked_at: string; http_status?: number; message: string; items_found?: number };
export type Run = { id: string; status: string; started_at: string; finished_at: string | null; found: number; candidates: number; versions: number; kept: number; parser_failures: number; failed_jobs: number; cost: string | number | null; cost_status: "actual" | "estimated" | "unknown"; error_summary: string | null };
export type ModelSettings = { provider: string; base_url: string; model: string; configured: boolean; enabled: boolean; max_tokens: number };
export type ModelTest = { ok: boolean; message: string; model: string; usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number } };
export type Usage = { items: Array<{ purpose: string; status: string; calls: number; usage_recorded: boolean; input_tokens: number; output_tokens: number; total_tokens: number }>; as_of: string };
const csrfHeaders = (csrf: string, extra: HeadersInit = {}) => ({ ...extra, "X-CSRF-Token": csrf });
export const admin = {
  session: (token?: string) => token === undefined ? api<AdminSession>("/api/v1/admin/session") : api<AdminSession>("/api/v1/admin/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) }),
  logout: (csrf: string) => fetch("/api/v1/admin/session", { method: "DELETE", credentials: "same-origin", headers: csrfHeaders(csrf) }).then((response) => { if (!response.ok) throw { code: `HTTP_${response.status}`, status: response.status, message: "退出管理后台失败" }; }),
  sources: () => api<{ items: Source[] }>("/api/v1/admin/sources"),
  createSource: (csrf: string, payload: Pick<Source, "name" | "feed_url" | "channel_type">) => api<Source>("/api/v1/admin/sources", { method: "POST", headers: csrfHeaders(csrf, { "Content-Type": "application/json" }), body: JSON.stringify(payload) }),
  updateSource: (csrf: string, id: string, payload: Partial<Pick<Source, "name" | "feed_url" | "enabled">>) => api<Source>(`/api/v1/admin/sources/${id}`, { method: "PATCH", headers: csrfHeaders(csrf, { "Content-Type": "application/json" }), body: JSON.stringify(payload) }),
  probe: (csrf: string, id: string) => api<ProbeResult>(`/api/v1/admin/sources/${id}/probe`, { method: "POST", headers: csrfHeaders(csrf) }),
  runs: () => api<{ items: Run[] }>("/api/v1/ingest/runs"),
  start: (csrf: string, source_ids: string[], idempotencyKey: string) => api<{ run_id: string; status: string }>("/api/v1/ingest/runs", { method: "POST", headers: csrfHeaders(csrf, { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey }), body: JSON.stringify({ source_ids }) }),
  model: () => api<ModelSettings>("/api/v1/admin/model"),
  saveModel: (csrf: string, payload: { api_key?: string; enabled: boolean; max_tokens: number }) => api<ModelSettings>("/api/v1/admin/model", { method: "PUT", headers: csrfHeaders(csrf, { "Content-Type": "application/json" }), body: JSON.stringify(payload) }),
  testModel: (csrf: string, kind: "connectivity" | "completion") => api<ModelTest>("/api/v1/admin/model/test", { method: "POST", headers: csrfHeaders(csrf, { "Content-Type": "application/json" }), body: JSON.stringify({ kind }) }),
  usage: () => api<Usage>("/api/v1/admin/model/usage"),
};
export { err };
