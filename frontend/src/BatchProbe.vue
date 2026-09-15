<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { admin, err, type Source } from "./api";
const props = defineProps<{ sources: Source[]; csrf: string; disabled?: boolean }>();
const emit = defineEmits<{ complete: []; unauthorized: [] }>();
const selected = ref<string[]>([]), states = ref<Record<string, "pending" | "running" | "success" | "failed" | "skipped">>({}), stopped = ref(false), active = ref(false), summary = ref("");
const available = computed(() => props.sources.map((source) => source.id));
const total = computed(() => Object.keys(states.value).length);
const done = computed(() => Object.values(states.value).filter((state) => ["success", "failed", "skipped"].includes(state)).length);
const running = computed(() => Object.values(states.value).filter((state) => state === "running").length);
const percent = computed(() => total.value ? Math.round(done.value / total.value * 100) : 0);
function chooseAll(checked: boolean) { selected.value = checked ? [...available.value] : []; }
function toggle(id: string, checked: boolean) { selected.value = checked ? [...selected.value, id] : selected.value.filter((value) => value !== id); }
async function probeAll(ids = selected.value) {
  if (active.value || !ids.length) return;
  selected.value = [...ids];
  active.value = true; stopped.value = false; summary.value = "";
  states.value = Object.fromEntries(ids.map((id) => [id, "pending"]));
  const queue = [...ids]; let successes = 0, failures = 0, skipped = 0;
  const worker = async () => { while (queue.length && !stopped.value) { const id = queue.shift(); if (!id) return; states.value = { ...states.value, [id]: "running" }; try { await admin.probe(props.csrf, id); successes += 1; states.value = { ...states.value, [id]: "success" }; } catch (cause) { const problem = err(cause); if (problem.status === 401) { stopped.value = true; emit("unauthorized"); states.value = { ...states.value, [id]: "failed" }; return; } failures += 1; states.value = { ...states.value, [id]: "failed" }; } } };
  await Promise.all([worker(), worker()]);
  if (queue.length) { skipped = queue.length; states.value = { ...states.value, ...Object.fromEntries(queue.map((id) => [id, "skipped"])) }; }
  active.value = false; summary.value = `批量探测完成：成功 ${successes}，失败 ${failures}${skipped ? `，跳过 ${skipped}` : ""}。`; emit("complete");
}
onBeforeUnmount(() => { stopped.value = true; });
</script>
<template><section class="batch-probe" aria-label="批量来源探测"><div class="batch-probe__heading"><div><strong>批量探测</strong><p class="meta">最多同时探测 2 个来源；停止后不会发出尚未开始的请求。</p></div><svg v-if="active" class="batch-progress" viewBox="0 0 36 36" role="img" :aria-label="`已完成 ${done}/${total}`"><circle cx="18" cy="18" r="15.5"/><circle cx="18" cy="18" r="15.5" :stroke-dasharray="`${percent} 100`"/><text x="18" y="20.5">{{ done }}/{{ total }}</text></svg></div><div class="batch-probe__controls"><label><input type="checkbox" :checked="selected.length === available.length && available.length > 0" :disabled="active || disabled" @change="chooseAll(($event.target as HTMLInputElement).checked)" />全选</label><button type="button" :disabled="active || disabled || !selected.length" @click="probeAll()">探测选中（{{ selected.length }}）</button><button type="button" :disabled="active || disabled || !available.length" @click="probeAll(available)">探测全部</button><button v-if="active" type="button" @click="stopped = true">停止排队</button></div><div class="batch-probe__list"><label v-for="source in sources" :key="source.id"><input type="checkbox" :checked="selected.includes(source.id)" :disabled="active || disabled" @change="toggle(source.id, ($event.target as HTMLInputElement).checked)" />{{ source.name }}<span v-if="states[source.id]" class="meta" :data-state="states[source.id]">{{ ({ pending: "等待中", running: "探测中…", success: "成功", failed: "失败", skipped: "已跳过" }[states[source.id]]) }}</span></label></div><p v-if="summary" class="admin-notice" aria-live="polite">{{ summary }}</p></section></template>