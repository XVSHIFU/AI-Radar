import type { Citation } from "./api";
export type StreamState = { pendingCitations: Citation[]; terminal: "running" | "completed" | "error" | "interrupted" };
export const initialStreamState = (): StreamState => ({ pendingCitations: [], terminal: "running" });
export function reduceStream(state: StreamState, event: "sources" | "error" | "done" | "eof", payload?: { items?: Citation[]; status?: string }) : StreamState {
  if (event === "sources") return { ...state, pendingCitations: payload?.items ?? [] };
  if (event === "error") return { ...state, terminal: "error", pendingCitations: [] };
  if (event === "done") return state.terminal === "error" ? state : { ...state, terminal: payload?.status === "completed" ? "completed" : "error", pendingCitations: payload?.status === "completed" ? state.pendingCitations : [] };
  return state.terminal === "running" ? { ...state, terminal: "interrupted", pendingCitations: [] } : state;
}