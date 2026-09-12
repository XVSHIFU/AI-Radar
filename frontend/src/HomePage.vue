<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  events,
  err,
  stats,
  type Category,
  type Event,
  type EventQuery,
  type Stats,
} from "./api";
import { latestRequest } from "./latest";
const route = useRoute(),
  router = useRouter(),
  q = ref(""),
  category = ref<Category | "">(""),
  from = ref(""),
  to = ref(""),
  items = ref<Event[]>([]),
  total = ref(0),
  next = ref<string | null>(null),
  loading = ref(false),
  error = ref<ReturnType<typeof err>>(),
  advanced = ref(false),
  compact = ref(innerWidth < 768),
  timer = ref<number>(),
  latest = latestRequest(),
  overview = ref<Stats>(),
  statsError = ref(false);
const categories: { v: Category; l: string }[] = [
  { v: "model_release", l: "模型发布" },
  { v: "agent_tool", l: "智能体工具" },
  { v: "framework_sdk", l: "框架与 SDK" },
  { v: "research", l: "研究" },
  { v: "product", l: "产品" },
  { v: "industry", l: "产业" },
];
const invalid = computed(() =>
  Boolean(from.value && to.value && from.value > to.value),
);
function sync() {
  q.value = String(route.query.q || "");
  category.value = String(route.query.category || "") as Category | "";
  from.value = String(route.query.date_from || "");
  to.value = String(route.query.date_to || "");
}
function query(cursor?: string) {
  return Object.fromEntries(
    Object.entries({
      q: q.value || undefined,
      category: category.value || undefined,
      date_from: from.value || undefined,
      date_to: to.value || undefined,
      limit: "10",
      cursor,
      demo: route.query.demo,
    }).filter(([, v]) => v !== undefined),
  );
}
async function load(cursor?: string, append = false) {
  latest.cancel();
  if (invalid.value) {
    items.value = [];
    total.value = 0;
    next.value = null;
    loading.value = false;
    return;
  }
  const req = latest.begin();
  loading.value = true;
  error.value = undefined;
  if (!append) {
    items.value = [];
    next.value = null;
  }
  try {
    const x: EventQuery = {
      q: q.value,
      category: category.value || undefined,
      date_from: from.value || undefined,
      date_to: to.value || undefined,
      limit: 10,
      cursor,
    };
    const out = await events.list(x, req.signal);
    if (!req.current()) return;
    items.value = append
      ? [...items.value, ...(out.items as Event[])]
      : (out.items as Event[]);
    total.value = out.total;
    next.value = out.next_cursor;
  } catch (e) {
    if (req.current() && (e as Error).name !== "AbortError")
      error.value = err(e);
  } finally {
    if (req.current()) loading.value = false;
  }
}
function schedule() {
  latest.cancel();
  clearTimeout(timer.value);
  if (invalid.value) {
    items.value = [];
    total.value = 0;
    next.value = null;
    return;
  }
  timer.value = window.setTimeout(() => {
    router.replace({ query: query() });
    load();
  }, 300);
}
function clear() {
  q.value = "";
  category.value = "";
  from.value = "";
  to.value = "";
  schedule();
}
function resize() {
  compact.value = innerWidth < 768;
  if (!compact.value) advanced.value = true;
}
watch(() => route.query, sync, { immediate: true });
onMounted(async () => {
  load();
  try {
    overview.value = await stats();
  } catch {
    statsError.value = true;
  }
});
watch([q, category, from, to], schedule);
window.addEventListener("resize", resize);
onBeforeUnmount(() => {
  latest.cancel();
  clearTimeout(timer.value);
  window.removeEventListener("resize", resize);
});
</script>
<template>
  <section><div class="reading-shell"><aside class="side-panel"><h2>检索条件</h2><label>关键词<input v-model="q" class="control" placeholder="标题、摘要、实体" /></label><button v-if="compact" class="mobile" :aria-expanded="advanced" aria-controls="advanced" @click="advanced=!advanced">分类与日期 {{advanced?'−':'+'}}</button><div id="advanced" v-show="!compact||advanced" class="category-list"><fieldset><legend>分类</legend><label v-for="c in categories" :key="c.v"><input v-model="category" type="radio" :value="c.v" />{{c.l}}</label></fieldset><label>从<input v-model="from" type="date" class="control" /></label><label>至<input v-model="to" type="date" class="control" /></label></div><button @click="clear">清除</button></aside><main class="stream"><p class="meta">按日期浏览</p><h1 class="page-title">AI 动态</h1><p class="page-subtitle">从事件流开始，再回查来源与证据。</p><div class="filter-strip"><p v-if="invalid" class="status danger">日期范围无效：起始日期不能晚于截止日期。</p><p v-else aria-live="polite" class="meta">{{loading?'正在更新匹配结果…':`精确匹配 ${total} 条事件`}}</p></div><div v-if="error" class="card error" role="alert">{{error.message}}<button @click="load()">重试</button></div><div v-else-if="!loading&&!items.length" class="empty">这个范围内没有事件。</div><article v-for="x in items" :key="x.id" class="event"><p class="meta">{{x.event_date||'日期未知'}}</p><span class="pill">{{categories.find(c=>c.v===x.category)?.l}}</span><h2><RouterLink :to="{path:`/events/${x.id}`,query:{demo:route.query.demo}}">{{x.title_zh}}</RouterLink></h2><p class="muted">{{x.summary_zh}}</p><p class="meta tabular">重要度 {{x.importance}}/5 · {{x.source_count}} 个来源 · {{x.evidence_count}} 条关联证据</p></article><button v-if="next&&!loading" @click="load(next,true)">加载更多</button></main><aside class="context-panel"><h2>全库范围</h2><p v-if="overview" class="tabular">{{overview.scope==='global'?'全库':overview.scope}} · {{overview.total_events}} 条事件</p><p v-if="overview" class="meta">更新时间：{{overview.as_of}}</p><p v-else class="meta">{{statsError?'全库态势暂时无法读取':'正在读取全库态势…'}}</p></aside></div></section>
</template>