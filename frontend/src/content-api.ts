import { api, type Category } from "./api";

export type ContentArticle = {
  article_version_id: string;
  title: string;
  source_url: string;
  published_at: string | null;
  content_hash: string;
  task_id: string | null;
  status: string | null;
};
export type ContentTask = {
  id: string;
  article_version_id: string;
  title: string;
  source_url: string;
  published_at: string | null;
  status: string;
  mode: string | null;
  draft_id: string | null;
  batch_id: string | null;
};
export type DraftEvidence = { paragraph_id: string; quote_text: string; claim_key: string | null; claim_text: string | null; support_type: string };
export type DraftEntity = { canonical_name: string; entity_type: string; role: string };
export type DraftContent = {
  relevant: boolean;
  title_zh: string;
  summary_zh: string;
  category: Category | null;
  importance: number | null;
  event_date: string | null;
  date_precision: string;
  date_basis: string;
  date_evidence_paragraph_id: string | null;
  entities: DraftEntity[];
  evidence: DraftEvidence[];
};
export type ContentDraft = {
  id: string;
  task_id: string;
  revision: number;
  status: string;
  content: Partial<DraftContent> | Record<string, unknown>;
  validation_errors: string[];
  article?: { title: string; source_url: string; paragraphs: Record<string, string> };
};
export type ImportItem = { task_id: string; status: string; draft_id: string | null; errors: string[] };
export type ContentSettings = {
  enabled: boolean;
  auto_publish: boolean;
  batch_limit: number;
  daily_article_limit: number;
  daily_input_tokens: number;
  daily_output_tokens: number;
  max_output_tokens: number;
  article_max_calls: number;
  concurrency: number;
  profile: { provider: string; base_url: string; model: string; has_api_key: boolean };
};
export type ContentSettingsPatch = Partial<Omit<ContentSettings, "profile">> & { profile?: { provider?: string; base_url?: string; model?: string; api_key?: string } };
export type ContentBatch = { id: string; status: string; items?: Array<{ id: string; status: string; draft_id?: string | null; error?: string }> };

const prefix = "/api/v1/admin/content";
const write = (csrf: string, method: "POST" | "PATCH", body?: unknown): RequestInit => ({
  method,
  headers: { "X-CSRF-Token": csrf, "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});
export const contentApi = {
  articles: () => api<{ items: ContentArticle[]; total: number }>(`${prefix}/articles?limit=50`),
  tasks: () => api<{ items: ContentTask[]; total: number }>(`${prefix}/tasks`),
  createTasks: (csrf: string, articleVersionIds: string[]) => api<{ items: ContentTask[] }>(`${prefix}/tasks`, write(csrf, "POST", { article_version_ids: articleVersionIds })),
  export: (csrf: string, taskIds: string[]) => api<{ prompt: string; task_ids: string[] }>(`${prefix}/export`, write(csrf, "POST", { task_ids: taskIds })),
  import: (csrf: string, value: string) => api<{ items: ImportItem[] }>(`${prefix}/import`, write(csrf, "POST", { text: value })),
  draft: (id: string) => api<ContentDraft>(`${prefix}/drafts/${encodeURIComponent(id)}`),
  saveDraft: (csrf: string, id: string, revision: number, content: DraftContent) => api<ContentDraft>(`${prefix}/drafts/${encodeURIComponent(id)}`, write(csrf, "PATCH", { revision, content })),
  publishDraft: (csrf: string, id: string, revision: number) => api<{ status: "published" | "invalid"; event_id?: string; draft_id: string; errors?: string[] }>(`${prefix}/drafts/${encodeURIComponent(id)}/publish`, write(csrf, "POST", { revision })),
  settings: () => api<ContentSettings>(`${prefix}/settings`),
  saveSettings: (csrf: string, settings: ContentSettingsPatch) => api<ContentSettings>(`${prefix}/settings`, write(csrf, "PATCH", settings)),
  startBatch: (csrf: string, taskIds: string[]) => api<ContentBatch>(`${prefix}/batches`, write(csrf, "POST", { task_ids: taskIds })),
  batch: (id: string) => api<ContentBatch>(`${prefix}/batches/${encodeURIComponent(id)}`),
  pauseBatch: (csrf: string, id: string) => api<ContentBatch>(`${prefix}/batches/${encodeURIComponent(id)}/pause`, write(csrf, "POST")),
  switchManual: (csrf: string, id: string) => api<ContentTask>(`${prefix}/tasks/${encodeURIComponent(id)}/manual`, write(csrf, "POST")),
  skipTask: (csrf: string, id: string) => api<ContentTask>(`${prefix}/tasks/${encodeURIComponent(id)}/skip`, write(csrf, "POST")),
};
