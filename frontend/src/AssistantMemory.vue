<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { translate as tr } from "./locale";
import type { ConversationMemory, ReplyPreferences } from "./conversation-memory";
const props = defineProps<{
  summary: ConversationMemory; preferences?: ReplyPreferences; selected: boolean;
  recentTurns: number; busy: boolean;
}>();
const emit = defineEmits<{
  select: [value: boolean]; save: [value: ReplyPreferences]; forget: []; clear: [];
}>();
const language = ref<ReplyPreferences["language"]>("auto");
const length = ref<ReplyPreferences["length"]>("concise");
watch(() => props.preferences, value => {
  language.value = value?.language || "auto";
  length.value = value?.length || "concise";
}, { immediate: true });
const changed = computed(() => !props.preferences || props.preferences.language !== language.value || props.preferences.length !== length.value);
</script>

<template>
  <details class="assistant-memory" data-testid="assistant-memory">
    <summary>{{ tr("会话记忆", "Conversation memory") }}</summary>
    <div class="memory-content">
      <p class="memory-note">{{ tr("仅本会话。最近 {count} 轮完整问答可用于追问。", "This conversation only. {count} recent complete turns are available for follow-ups.", { count: recentTurns }) }}</p>
      <h3>{{ tr("较早轮次摘要", "Earlier context") }}</h3>
      <p class="memory-note">{{ tr("在浏览器内整理。默认不发送；勾选后，这份摘要仅随下一次提问发送给后台配置的模型服务。", "Prepared in this browser. Off by default; select it to send this snapshot to the configured model service with your next question only.") }}</p>
      <ol v-if="summary.entries.length" class="memory-excerpts" tabindex="0" :aria-label="tr('较早轮次摘要，可滚动', 'Earlier context; scroll to review')">
        <li v-for="entry in summary.entries" :key="entry.turn_id">
          <p class="memory-question">{{ entry.question_excerpt }}</p>
          <p v-if="entry.answer_excerpt">{{ entry.answer_excerpt }}</p>
          <p class="memory-note">{{ entry.scope_excerpt }}</p>
          <p class="memory-note">{{ entry.unresolved ? tr("未解决，需重新查证", "Unresolved; verify again") : tr("旧结论，需重新查证", "Earlier conclusion; verify again") }}<span v-for="source in entry.citations" :key="source.index"> · [{{ source.index }}]</span></p>
        </li>
      </ol>
      <p v-else class="memory-note">{{ tr("暂无更早的完整轮次。", "No earlier complete turns yet.") }}</p>
      <label v-if="summary.entries.length" class="memory-consent">
        <input type="checkbox" :checked="selected" :disabled="busy" @change="emit('select', ($event.target as HTMLInputElement).checked)" />
        <span>{{ tr("仅下一次使用这份摘要", "Use this snapshot once") }}</span>
      </label>
      <button type="button" class="memory-action" :disabled="busy || (!recentTurns && !summary.entries.length)" @click="emit('clear')">{{ tr("清除上下文", "Clear context") }}</button>
      <p class="memory-note">{{ tr("清除后旧消息仍可查看，但不再作为上下文发送。", "Earlier messages remain readable, but will no longer be sent as context.") }}</p>
      <h3>{{ tr("回答偏好", "Reply preferences") }}</h3>
      <label class="memory-field"><span>{{ tr("语言", "Language") }}</span>
        <select v-model="language" :disabled="busy">
          <option value="auto">{{ tr("跟随本轮问题", "Follow this question") }}</option>
          <option value="zh">中文</option><option value="en">English</option>
        </select>
      </label>
      <label class="memory-field"><span>{{ tr("长度", "Length") }}</span>
        <select v-model="length" :disabled="busy">
          <option value="concise">{{ tr("简洁", "Concise") }}</option>
          <option value="detailed">{{ tr("详细", "Detailed") }}</option>
        </select>
      </label>
      <div class="memory-actions">
        <button type="button" class="memory-action" :disabled="busy || !changed" @click="emit('save', { language, length })">{{ preferences && !changed ? tr("已记住", "Saved") : tr("记住偏好", "Remember") }}</button>
        <button v-if="preferences" type="button" class="memory-action" :disabled="busy" @click="emit('forget')">{{ tr("删除偏好", "Forget") }}</button>
      </div>
      <p class="memory-note">{{ tr("点击后仅保存在此浏览器、本会话中。本轮明确要求优先。", "Saved only in this browser and conversation when you click Remember. Explicit requests take priority.") }}</p>
    </div>
  </details>
</template>

<style scoped>
.assistant-memory { margin:8px 0 14px; border-bottom:1px solid var(--line); font-size:13px; color:var(--ink); }
.assistant-memory > summary { padding:10px 4px; cursor:pointer; color:var(--blue); background:transparent; }
.memory-content { padding:0 4px 14px; line-height:1.7; overflow-wrap:anywhere; }
.memory-content h3 { font:inherit; font-size:13px; font-weight:600; line-height:1.5; margin:22px 0 10px; color:var(--ink); }
.memory-content p { margin:6px 0; }
.memory-note { font-size:12px; color:var(--muted); }
.memory-excerpts { list-style:none; padding:0 6px 0 0; margin:12px 0; max-height:min(250px, 30dvh); overflow-y:auto; scrollbar-gutter:stable; }
.memory-excerpts:focus-visible { outline:1px solid var(--blue); outline-offset:2px; }
.memory-excerpts li { padding:10px 0; border-bottom:1px solid var(--line); }
.memory-question { font-weight:600; }
.memory-consent { display:flex; align-items:flex-start; gap:8px; margin:14px 0 8px; }
.memory-consent input { flex:none; margin-top:5px; accent-color:var(--blue); }
.memory-field { display:grid; gap:6px; margin:12px 0; }
.memory-field select { width:100%; min-width:0; min-height:36px; font:inherit; color:var(--ink); background:var(--paper); border:1px solid var(--line); border-radius:6px; padding:6px 8px; }
.memory-field select:focus-visible { outline:none; border-color:var(--blue); }
.memory-actions { display:flex; flex-wrap:wrap; gap:8px; }
.memory-action { min-height:36px; padding:6px 4px; font:inherit; border:0; background:transparent; color:var(--blue); cursor:pointer; }
.memory-action:hover { text-decoration:underline; text-underline-offset:3px; background:transparent; }
.memory-action:disabled { opacity:.55; cursor:default; text-decoration:none; }
.memory-action:focus-visible, .assistant-memory > summary:focus-visible { outline:1px solid var(--blue); outline-offset:2px; }
@media(max-width:900px) { .memory-action, .memory-field select { min-height:44px; } }
</style>
