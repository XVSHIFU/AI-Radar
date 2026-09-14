import { reactive } from "vue";

export type Attachment = { id: string; title: string };
export type StoredPlan = {
  business_date: string; timezone: string; filters: { category?: string; date_from?: string; date_to?: string; entity_ids?: string[]; entity_match?: "all" | "any"; event_ids?: string[] };
  requires_clarification: boolean; clarification_candidates: { label: string; entity_id: string | null }[]; warnings: string[]; free_text?: string; entity_roles?: ("subject" | "product")[]; history_turns_considered?: number; history_user_turns_used?: number; event_targets?: { event_id:string; title_zh:string|null; status:"matched"|"filtered_out"|"not_found" }[];
};
export type ConversationMessage = {
  id: string; role: "user" | "assistant"; text: string; createdAt: number; scope: string;
  filters?: Record<string, unknown>; mode: "demo" | "live"; citations?: { index: number; title: string; quote_text?: string; source_url: string; paragraph_id?: string }[];
  status?: "running" | "completed" | "cancelled" | "interrupted" | "error"; attachment?: Attachment; plan?: StoredPlan; metrics?: { scope_total?: number; retrieved_count?: number; summarized_count?: number; citation_count?: number; coverage?: string }; error?: { code: string; message: string };
};
export type Conversation = { id: string; title: string; draft: string; attachment?: Attachment; createdAt: number; updatedAt: number; messages: ConversationMessage[] };
const storeName = "conversations"; const rowsKey = "all"; const activeKey = "active";
let memory: Conversation[] = []; let writes = Promise.resolve();
export const storageState = reactive({ failed: false });
const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
function validMessage(value: unknown): value is ConversationMessage { return !!value && typeof value === "object" && typeof (value as ConversationMessage).id === "string" && ((value as ConversationMessage).role === "user" || (value as ConversationMessage).role === "assistant") && typeof (value as ConversationMessage).text === "string" && typeof (value as ConversationMessage).scope === "string" && ((value as ConversationMessage).mode === "demo" || (value as ConversationMessage).mode === "live"); }

function valid(value: unknown): value is Conversation[] { return Array.isArray(value) && value.every((row) => row && typeof row === "object" && typeof (row as Conversation).id === "string" && typeof (row as Conversation).title === "string" && typeof (row as Conversation).draft === "string" && Array.isArray((row as Conversation).messages) && (row as Conversation).messages.every(validMessage)); }
export function restoreConversations(value: unknown): Conversation[] {
  if (!valid(value)) return [];
  return copy(value).map((conversation) => ({ ...conversation, messages: conversation.messages.map((message) => message.status === "running" ? { ...message, status: "interrupted", text: message.text || "本次请求在页面关闭前中断，未自动重试。" } : message) }));
}
export function boundedHistory(messages: ConversationMessage[], currentUserId: string) {
  const pairs: { user:{ role:"user";content:string;filters?:Record<string,unknown>}; assistant:{role:"assistant";content:string} }[]=[];
  let user: ConversationMessage | undefined;
  for (const message of messages) { if(message.id===currentUserId) continue; if(message.role==="user") user=message; else if(user&&message.status==="completed") { pairs.push({user:{role:"user",content:user.text.slice(0,4000),filters:user.filters},assistant:{role:"assistant",content:message.text.slice(0,4000)}});user=undefined; } }
  const selected: typeof pairs=[]; let total=0;
  for(const pair of pairs.slice(-3).reverse()){const size=pair.user.content.length+pair.assistant.content.length;if(total+size>12000)continue;selected.unshift(pair);total+=size;}
  return selected.flatMap((pair)=>[pair.user,pair.assistant]);
}function openDatabase(): Promise<IDBDatabase> { return new Promise((resolve, reject) => { if (typeof indexedDB === "undefined") return reject(new Error("IndexedDB 不可用")); const request = indexedDB.open("ai-radar-conversations", 1); request.onupgradeneeded = () => request.result.createObjectStore(storeName); request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error); }); }
async function read(key: string): Promise<unknown> { const db = await openDatabase(); try { return await new Promise((resolve, reject) => { const tx = db.transaction(storeName); const request = tx.objectStore(storeName).get(key); request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error); tx.onabort = () => reject(tx.error); }); } finally { db.close(); } }
async function write(key: string, value: unknown) { const db = await openDatabase(); try { await new Promise<void>((resolve, reject) => { const tx = db.transaction(storeName, "readwrite"); tx.objectStore(storeName).put(copy(value), key); tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error); tx.onabort = () => reject(tx.error); }); } finally { db.close(); } }
export async function loadConversations() { try { memory = restoreConversations(await read(rowsKey)); return copy(memory); } catch { storageState.failed = true; return copy(memory); } }
export async function loadActiveConversation() { try { const value = await read(activeKey); return typeof value === "string" ? value : ""; } catch { storageState.failed = true; return ""; } }
export function saveConversations(rows: Conversation[]) { const frozen = copy(rows); memory = frozen; writes = writes.then(() => write(rowsKey, frozen)).catch(() => { storageState.failed = true; }); return writes; }
export function saveActiveConversation(id: string) { writes = writes.then(() => write(activeKey, id)).catch(() => { storageState.failed = true; }); return writes; }
export function exportConversation(value: Conversation) { return JSON.stringify(copy(value), null, 2); }
