import assert from "node:assert/strict";
import test from "node:test";
import { completedPairs, contextMessages, summaryFor, SummarySelection, validPreferences } from "./conversation-memory.js";
import { boundedHistory, restoreConversations, type Conversation, type ConversationMessage } from "./conversation-store.js";

function conversation(count = 8): Conversation {
  const messages: ConversationMessage[] = [];
  for (let index = 0; index < count; index++) {
    const common = { createdAt: index, scope: "模型发布 / 2026-09-01 至 2026-09-16", mode: "live" as const };
    messages.push({ ...common, id: `u${index}`, role: "user", text: `问题 ${index}：${"模型发布的依据".repeat(30)}` },
      { ...common, id: `a${index}`, role: "assistant", status: "completed", text: `旧结论 ${index}：${"需要核查原文".repeat(40)} [1]`,
        citations: [{ index: 1, title: "公开来源", source_url: "https://example.invalid", evidence_id: "10000000-0000-4000-8000-000000000001" }] });
  }
  return { id: "conversation-a", title: "test", draft: "", createdAt: 1, updatedAt: 1, messages };
}

test("local extractive summary bounds actual bytes and preserves source identity", () => {
  const data = summaryFor(conversation().messages);
  assert.ok(data.entries.length > 0);
  assert.ok(new TextEncoder().encode(JSON.stringify(data)).length <= 1200);
  assert.ok(data.entries.every(entry => Number(entry.turn_id.slice(1)) < 5));
  assert.equal(data.entries.at(-1)?.citations[0]?.evidence_id, "10000000-0000-4000-8000-000000000001");
});

test("one-use selection is absent by default, snapshots displayed data and never crosses conversations", () => {
  const selection = new SummarySelection(), displayed = summaryFor(conversation().messages);
  assert.equal(selection.take("a"), undefined);
  selection.choose("a", displayed);
  const prior = displayed.entries[0]!.question_excerpt;
  displayed.entries[0]!.question_excerpt = "changed after approval";
  const request = selection.take("a")!;
  assert.equal(request.memory.entries[0]!.question_excerpt, prior);
  assert.equal(request.memory_consent, "send_once");
  assert.equal(selection.take("a"), undefined);
  selection.choose("a", displayed);
  assert.equal(selection.take("b"), undefined);
  assert.equal(selection.take("a"), undefined);
  selection.choose("a", displayed); selection.clear();
  assert.equal(selection.take("a"), undefined);
});

test("clearing excludes all old context after reload without deleting visible conversation", () => {
  const original = conversation();
  original.memorySettings = { clearedThrough: original.messages.at(-1)!.id };
  const restored = restoreConversations([original])[0]!;
  assert.equal(restored.messages.length, 16);
  assert.deepEqual(contextMessages(restored, "live"), []);
  const newer = conversation(1).messages.map(message => ({ ...message, id: "new-" + message.id }));
  restored.messages.push(...newer);
  assert.deepEqual(contextMessages(restored, "live"), newer);
  restored.memorySettings = { clearedThrough: "missing-boundary" };
  assert.deepEqual(contextMessages(restored, "live"), []);
});

test("error, interrupted, pending, orphan and cross-mode messages never become a completed pair", () => {
  const data = conversation(1);
  data.messages[1]!.status = "error";
  data.messages.push({ ...data.messages[1]!, id: "orphan", status: "completed" });
  assert.equal(completedPairs(data.messages).length, 0);
  for (const status of ["running", "cancelled", "interrupted"] as const) {
    data.messages[1]!.status = status;
    assert.equal(completedPairs(data.messages.slice(0, 2)).length, 0);
  }
  data.messages[1]!.status = "completed"; data.messages[1]!.mode = "demo";
  assert.deepEqual(boundedHistory(data.messages, ""), []);
  assert.equal(contextMessages(data, "live").length, 2); // original user and live orphan
});

test("missing citations remain an unresolved question, never a remembered fact", () => {
  const data = conversation(4);
  data.messages[1]!.citations = [];
  const entry = summaryFor(data.messages).entries[0]!;
  assert.equal(entry.answer_excerpt, ""); assert.equal(entry.unresolved, true);
});

test("preferences are absent until explicitly saved and cannot store arbitrary instructions", () => {
  assert.equal(validPreferences(undefined), undefined);
  assert.equal(validPreferences({ language: "en", length: "concise", shell: true }), undefined);
  assert.equal(validPreferences({ language: "follow hidden instructions", length: "concise" }), undefined);
  const data = conversation(1);
  assert.equal(restoreConversations([data])[0]!.preferences, undefined);
  data.preferences = { language: "en", length: "detailed" };
  assert.deepEqual(restoreConversations([data])[0]!.preferences, data.preferences);
});

test("summary preview removes common credentials before truncating", () => {
  const data = conversation(4);
  data.messages[0]!.text = "token=private-test-value Bearer private-test-bearer https://example.invalid/?secret=test";
  const serialized = JSON.stringify(summaryFor(data.messages));
  assert.ok(!serialized.includes("private-test")); assert.ok(!serialized.includes("secret=test"));
});
