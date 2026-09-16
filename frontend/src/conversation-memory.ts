import type { Conversation, ConversationMessage } from "./conversation-store";

export type ReplyPreferences = { language: "auto" | "zh" | "en"; length: "concise" | "detailed" };
export type MemorySettings = { clearedThrough?: string };
export type MemoryReference = { index: number; evidence_id?: string; dataset_id?: string };
export type MemoryEntry = {
  turn_id: string; question_excerpt: string; answer_excerpt: string; scope_excerpt: string;
  unresolved: boolean; citations: MemoryReference[];
};
export type ConversationMemory = { version: 1; entries: MemoryEntry[] };
const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/;
const encoder = new TextEncoder();
export function validPreferences(value: unknown): ReplyPreferences | undefined {
  if (!value || typeof value !== "object") return;
  const item = value as Record<string, unknown>;
  if (Object.keys(item).some(key => !["language", "length"].includes(key)) ||
      !["auto", "zh", "en"].includes(String(item.language)) ||
      !["concise", "detailed"].includes(String(item.length))) return;
  return { language: item.language as ReplyPreferences["language"], length: item.length as ReplyPreferences["length"] };
}
export function memorySettings(value: unknown): MemorySettings {
  if (!value || typeof value !== "object") return {};
  const item = value as Record<string, unknown>;
  return typeof item.clearedThrough === "string" ? { clearedThrough: item.clearedThrough } : {};
}
export function contextMessages(conversation: Conversation, mode: "live" | "demo") {
  const boundary = memorySettings(conversation.memorySettings).clearedThrough;
  const index = boundary ? conversation.messages.findIndex(message => message.id === boundary) : -1;
  // A missing deletion boundary must not silently resurrect cleared context.
  if (boundary && index < 0) return [];
  return conversation.messages.slice(index + 1).filter(message => message.mode === mode);
}
export function completedPairs(messages: ConversationMessage[], currentUserId = "") {
  const pairs: { user: ConversationMessage; assistant: ConversationMessage }[] = [];
  let user: ConversationMessage | undefined;
  for (const message of messages) {
    if (message.id === currentUserId) break;
    if (message.role === "user") user = message;
    else {
      if (user && message.status === "completed" && !message.error && message.mode === user.mode)
        pairs.push({ user, assistant: message });
      user = undefined;
    }
  }
  return pairs;
}
function excerpt(text: string, limit: number): string {
  // Local preview only; this is not a general PII classifier. The user must
  // inspect and explicitly attach the displayed snapshot for each request.
  return Array.from(text.replace(/(?:Bearer\s+\S+|sk-[A-Za-z0-9_-]{8,}|(?:api[_ -]?key|token|password|cookie|authorization)\s*[:=]\s*\S+)/gi, "[redacted]")
    .replace(/https?:\/\/\S+/gi, "[link]").replace(/\s+/g, " ").trim()).slice(0, limit).join("");
}
export function summaryFor(messages: ConversationMessage[], currentUserId = ""): ConversationMemory {
  const pairs = completedPairs(messages, currentUserId);
  const summary: ConversationMemory = { version: 1, entries: [] };
  for (const pair of pairs.slice(0, -3).slice(-6).reverse()) {
    const citations: MemoryReference[] = (pair.assistant.citations || []).slice(0, 2)
      .filter(c => Number.isInteger(c.index) && c.index >= 1 && c.index <= 60)
      .map(c => ({ index: c.index,
        ...(c.evidence_id && uuid.test(c.evidence_id) ? { evidence_id: c.evidence_id } : {}),
        ...(c.dataset?.dataset_id && uuid.test(c.dataset.dataset_id) ? { dataset_id: c.dataset.dataset_id } : {}) }));
    if (!/^[A-Za-z0-9_-]{1,80}$/.test(pair.assistant.id)) continue;
    const entry: MemoryEntry = {
      turn_id: pair.assistant.id, question_excerpt: excerpt(pair.user.text, 100),
      answer_excerpt: citations.length ? excerpt(pair.assistant.text, 180) : "",
      scope_excerpt: excerpt(pair.user.scope, 60), unresolved: citations.length === 0, citations,
    };
    while (encoder.encode(JSON.stringify({ version: 1, entries: [entry, ...summary.entries] })).length > 1200) {
      if (entry.answer_excerpt.length > 40) entry.answer_excerpt = Array.from(entry.answer_excerpt).slice(0, -20).join("");
      else if (entry.question_excerpt.length > 24) entry.question_excerpt = Array.from(entry.question_excerpt).slice(0, -12).join("");
      else break;
    }
    if (encoder.encode(JSON.stringify({ version: 1, entries: [entry, ...summary.entries] })).length <= 1200)
      summary.entries.unshift(entry);
  }
  return summary;
}

/** Explicit one-use selection, never stored in IndexedDB or inferred from text. */
export class SummarySelection {
  private selected: { conversationId: string; summary: ConversationMemory } | undefined;
  choose(conversationId: string, displayed: ConversationMemory) {
    this.selected = displayed.entries.length ? { conversationId, summary: structuredClone(displayed) } : undefined;
  }
  clear() { this.selected = undefined; }
  take(conversationId: string): { memory: ConversationMemory; memory_consent: "send_once" } | undefined {
    const selected = this.selected; this.clear();
    if (!selected || selected.conversationId !== conversationId) return;
    return { memory: selected.summary, memory_consent: "send_once" };
  }
}
