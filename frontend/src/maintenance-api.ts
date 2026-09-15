import { api } from "./api";

export type DateReview = {
  event_id: string;
  current_date: string | null;
  title_zh?: string;
  status: string;
  candidates: Array<{ date: string; evidence_id: string; paragraph_id: string }>;
};

const write = (csrf: string, body?: unknown): RequestInit => ({
  method: "POST",
  headers: { "X-CSRF-Token": csrf, "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export type AuditEntry = { id: string; action: string; target: string; status_code: number; outcome: string; request_id: string; occurred_at: string };
export const maintenance = {
  audit: (signal?: AbortSignal) => api<{ items: AuditEntry[] }>("/api/v1/admin/audit?limit=50", { signal }),
  dates: (signal?: AbortSignal) => api<{ dry_run: boolean; items: DateReview[] }>("/api/v1/admin/event-date-review?limit=1000", { signal }),
  correctDate: (csrf: string, id: string, candidate: DateReview["candidates"][number]) =>
    api<{ audit_id: string }>(`/api/v1/admin/event-date-review/${encodeURIComponent(id)}`, write(csrf, { evidence_id: candidate.evidence_id, event_date: candidate.date })),
  merge: (csrf: string, source: string, target: string, reason: string, evidence: Record<string, unknown>) =>
    api<{ merge_id: string }>("/api/v1/admin/event-merges", write(csrf, { source_event_id: source, target_event_id: target, reason, evidence })),
  revert: (csrf: string, id: string) => api<{ status: string }>(`/api/v1/admin/event-merges/${encodeURIComponent(id)}/revert`, write(csrf)),
};
