<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ask, err, events, isDemo, type AskResult, type Category, type Citation, type Event } from "./api";
import EventDrawers from "./EventDrawers.vue";
import { insights, type InsightResult } from "./insights-api";
import { parseSse } from "./sse";
import { askView } from "./ask-result";
import { queryPlanFrom, type QueryPlan } from "./query-plan";
import { setAssistantScope } from "./assistant-scope";
import { categoryBuckets, chartCategories } from "./insight-charts";

const route = useRoute();
const router = useRouter();
const categoryName: Record<string, string> = {
  model_release: "模型发布", agent_tool: "智能体工具", framework_sdk: "框架与 SDK",
  research: "研究", product: "产品", industry: "产业",
};
const allCategories: Category[] = ["model_release", "agent_tool", "framework_sdk", "research", "product", "industry"];
function shanghaiToday() {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts();
  const get = (type: string) => parts.find((part) => part.type === type)?.value || "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}
function addDays(date: string, days: number) {
  const value = new Date(`${date}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}
const today = shanghaiToday();
const question = ref("");
const keyword = ref("");
const category = ref<Category | "">("");
const from = ref(today);
const to = ref(today);
const minImportance = ref(false);
const rangeMode = ref<"today" | "week" | "month" | "custom">("today");
const overview = ref<InsightResult>();
const overviewLoading = ref(false);
const overviewError = ref("");
const listItems = ref<Event[]>([]);
const listNext = ref<string | null>(null);
const listLoading = ref(false);
const listError = ref("");
const running = ref(false);
const controller = ref<AbortController>();
const result = ref<AskResult>();
const error = ref<ReturnType<typeof err>>();
const status = ref("");
const tokens = ref("");
const sources = ref<Citation[]>([]);
const metrics = ref<Pick<AskResult, "scope_total" | "retrieved_count" | "summarized_count" | "citation_count" | "coverage"> & { status?: string }>();
const expanded = ref<number>();
const plan = ref<QueryPlan>();
const rulePlan = ref<QueryPlan>();
const ruleError = ref("");
const planning = ref(false);
let ruleController: AbortController | undefined;
let ruleGeneration = 0;
let overviewController: AbortController | undefined;
let overviewGeneration = 0;
let answerGeneration = 0;
let timer: number | undefined;
let timers: number[] = [];
const errorGuidance: Record<string, string> = {
  MODEL_UNAVAILABLE: "生成模型尚未配置，已显示可用的检索范围。",
  QUERY_UNSUPPORTED: "当前问题包含暂不支持的检索表达。",
  CLARIFICATION_REQUIRED: "需要先澄清检索条件后才能继续。",
};
const errorDescription = (value: ReturnType<typeof err>) => errorGuidance[value.code] ? `${errorGuidance[value.code]} ${value.message}` : value.message;
const missingDates = computed(() => !from.value || !to.value);
const invalid = computed(() => Boolean(from.value && to.value && from.value > to.value));
const spanDays = computed(() => missingDates.value ? 0 : Math.floor((Date.parse(`${to.value}T00:00:00Z`) - Date.parse(`${from.value}T00:00:00Z`)) / 86400000) + 1);
const tooWide = computed(() => !invalid.value && spanDays.value > 366);
const filters = computed(() => ({ q: keyword.value || undefined, category: category.value || undefined, date_from: from.value || undefined, date_to: to.value || undefined, min_importance: minImportance.value ? 4 : undefined }));
const chartRows = computed(() => {
  if (!overview.value || spanDays.value > 31 || missingDates.value) return overview.value?.daily || [];
  const counts = new Map(overview.value.daily.map((row) => [row.date, row.count]));
  const rows: { date: string; count: number }[] = [];
  for (let date = from.value; date <= to.value; date = addDays(date, 1)) rows.push({ date, count: counts.get(date) || 0 });
  return rows;
});
const chartBuckets = computed(() => {
  if (spanDays.value <= 31) return chartRows.value.map((row) => ({ ...row, from: row.date, to: row.date, label: row.date.slice(5) }));
  const buckets = new Map<string, { date: string; count: number; from: string; to: string; label: string }>();
  for (const row of chartRows.value) {
    const month = row.date.slice(0, 7);
    const bucket = buckets.get(month);
    if (bucket) { bucket.count += row.count; bucket.to = row.date; }
    else buckets.set(month, { date: month, count: row.count, from: row.date, to: row.date, label: month });
  }
  return [...buckets.values()];
});
const maxDaily = computed(() => Math.max(0, ...chartBuckets.value.map((row) => row.count)));
const categories = computed(() => {
  const counts = new Map(overview.value?.categories.map((row) => [row.category, row.count]) || []);
  return allCategories.map((value) => ({ category: value, count: counts.get(value) || 0 }));
});
const maxCategory = computed(() => Math.max(0, ...categories.value.map((row) => row.count)));
const chartView = ref<"flow" | "area" | "heat">("flow");
const jointBuckets = computed(() => overview.value ? categoryBuckets(overview.value.daily_categories, spanDays.value > 31) : []);
const jointMax = computed(() => Math.max(1, ...jointBuckets.value.flatMap((bucket) => chartCategories.map((category) => bucket.counts[category]))));
const jointTotal = computed(() => Math.max(1, ...jointBuckets.value.map((bucket) => bucket.total)));
const activeBucket = ref(0);
const playing = ref(false);
let playback: number | undefined;
function chartX(index: number) { return jointBuckets.value.length < 2 ? 360 : 40 + index * 640 / (jointBuckets.value.length - 1); }
function flowPath(category: Category, categoryIndex: number) { return jointBuckets.value.map((bucket, index) => `${index ? "L" : "M"}${chartX(index)} ${24 + categoryIndex * 23 - bucket.counts[category] / jointMax.value * 12}`).join(" "); }
function areaPath(category: Category) { const upper = jointBuckets.value.map((bucket, index) => { const previous = chartCategories.slice(0, chartCategories.indexOf(category)).reduce((sum, item) => sum + bucket.counts[item], 0); return `${index ? "L" : "M"}${chartX(index)} ${146 - (previous + bucket.counts[category]) / jointTotal.value * 122}`; }); const lower = [...jointBuckets.value].reverse().map((bucket, offset) => { const index = jointBuckets.value.length - 1 - offset; const previous = chartCategories.slice(0, chartCategories.indexOf(category)).reduce((sum, item) => sum + bucket.counts[item], 0); return `L${chartX(index)} ${146 - previous / jointTotal.value * 122}`; }); return `${upper.join(" ")} ${lower.join(" ")} Z`; }
function heatOpacity(count: number) { return 0.14 + count / jointMax.value * 0.78; }
function chooseBucket(bucket: { from: string; to: string }) { selectDay(bucket.from, bucket.to); }
function togglePlayback() { playing.value = !playing.value; if (playing.value) { clearInterval(playback); playback = window.setInterval(() => { activeBucket.value = jointBuckets.value.length ? (activeBucket.value + 1) % jointBuckets.value.length : 0; }, 900); } else clearInterval(playback); }
const rangeLabel = computed(() => `${from.value || "未选择"} 至 ${to.value || "未选择"}（Asia/Shanghai，起止均包含）`);
const filterLabel = computed(() => [category.value ? `分类：${categoryName[category.value] || category.value}` : "", keyword.value ? `关键词：${keyword.value}` : "", minImportance.value ? "重要度：4及以上" : ""].filter(Boolean).join(" · "));
const validUrl = (url: string) => /^https?:\/\//i.test(url);
function slowStream() {
  let control: ReadableStreamDefaultController<Uint8Array>;
  const emit = (value: string, ms: number) => timers.push(window.setTimeout(() => control.enqueue(new TextEncoder().encode(value)), ms));
  return new ReadableStream<Uint8Array>({
    start(c) {
      control = c;
      emit('event: status\ndata: {"phase":"retrieving"}\n\n', 150);
      emit('event: token\ndata: {"text":"这是"}\n\n', 450);
      emit('event: token\ndata: {"text":"明确标注的模拟回答。[2]"}\n\n', 850);
      emit('event: sources\ndata: {"items":[{"index":2,"title":"合成演示来源","source_url":"https://example.invalid/demo","quote_text":"合成段落摘录","paragraph_id":"demo-p-001"}]}\n\n', 1150);
      emit('event: done\ndata: {"status":"completed","scope_total":1,"retrieved_count":1,"summarized_count":1,"citation_count":1,"coverage":"complete"}\n\n', 1450);
      timers.push(window.setTimeout(() => c.close(), 1600));
    },
    cancel() { timers.forEach(clearTimeout); timers = []; },
  });
}
function setRange(mode: "today" | "week" | "month" | "custom") {
  rangeMode.value = mode;
  if (mode === "today") from.value = to.value = today;
  if (mode === "week") { from.value = addDays(today, -6); to.value = today; }
  if (mode === "month") { from.value = `${today.slice(0, 8)}01`; to.value = today; }
}
function resetAnswer() {
  const hadAnswer = running.value || Boolean(result.value || tokens.value || sources.value.length || metrics.value);
  answerGeneration++;
  controller.value?.abort();
  timers.forEach(clearTimeout);
  timers = [];
  running.value = false;
  result.value = undefined;
  tokens.value = "";
  sources.value = [];
  metrics.value = undefined;
  plan.value = undefined;
  error.value = undefined;
  status.value = hadAnswer ? "范围已更新，之前的回答已清除。" : "";
}
function clearOverviewState() {
  overview.value = undefined;
  overviewError.value = "";
  listItems.value = [];
  listNext.value = null;
  listError.value = "";
}
async function loadOverview(cursor?: string, append = false) {
  if (missingDates.value || invalid.value || tooWide.value) {
    overviewLoading.value = false;
    listLoading.value = false;
    clearOverviewState();
    return;
  }
  if (append) {
    if (!cursor) return;
    const current = overviewGeneration;
    overviewController?.abort();
    overviewController = new AbortController();
    listLoading.value = true;
    listError.value = "";
    try {
      const rows = await events.list({ ...filters.value, limit: 10, cursor }, overviewController.signal);
      if (current !== overviewGeneration) return;
      listItems.value = [...listItems.value, ...(rows.items as Event[])];
      listNext.value = rows.next_cursor;
    } catch (cause) {
      if (current === overviewGeneration && (cause as Error).name !== "AbortError") listError.value = cause instanceof Error ? cause.message : "事件列表请求失败";
    } finally { if (current === overviewGeneration) listLoading.value = false; }
    return;
  }
  const current = ++overviewGeneration;
  overviewController?.abort();
  overviewController = new AbortController();
  clearOverviewState();
  overviewLoading.value = true;
  listLoading.value = true;
  const request = { q: filters.value.q, category: filters.value.category, date_from: from.value, date_to: to.value, min_importance: filters.value.min_importance };
  const summaryTask = insights(request, overviewController.signal).then((summary) => {
    if (current !== overviewGeneration) return;
    overview.value = summary;
  }).catch((cause: unknown) => {
    if (current === overviewGeneration && (cause as Error).name !== "AbortError") overviewError.value = cause instanceof Error ? cause.message : "统计请求失败";
  }).finally(() => { if (current === overviewGeneration) overviewLoading.value = false; });
  const listTask = events.list({ ...filters.value, limit: 10 }, overviewController.signal).then((rows) => {
    if (current !== overviewGeneration) return;
    listItems.value = rows.items as Event[];
    listNext.value = rows.next_cursor;
  }).catch((cause: unknown) => {
    if (current === overviewGeneration && (cause as Error).name !== "AbortError") listError.value = cause instanceof Error ? cause.message : "事件列表请求失败";
  }).finally(() => { if (current === overviewGeneration) listLoading.value = false; });
  await Promise.allSettled([summaryTask, listTask]);
}
function scheduleOverview() {
  clearTimeout(timer);
  overviewGeneration++;
  overviewController?.abort();
  clearOverviewState();
  overviewLoading.value = !missingDates.value && !invalid.value && !tooWide.value;
  listLoading.value = overviewLoading.value;
  resetAnswer();
  timer = window.setTimeout(() => void loadOverview(), 260);
}
function selectDay(date: string, end = date) { rangeMode.value = "custom"; from.value = date; to.value = end; }
async function planFromQuestion() {
  const current = ++ruleGeneration;
  ruleController?.abort();
  ruleController = new AbortController();
  ruleError.value = "";
  rulePlan.value = undefined;
  planning.value = true;
  try {
    const response = await fetch("/api/v1/query-plan", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question: question.value, filters: {}, timezone: "Asia/Shanghai", client_request_id: crypto.randomUUID() }), signal: ruleController.signal });
    if (!response.ok) throw new Error("规则解析请求失败");
    const raw = await response.json();
    if (current !== ruleGeneration) return;
    const parsed = queryPlanFrom({ query_plan_public: raw });
    if (!parsed) throw new Error("规则解析结果无效");
    rulePlan.value = parsed;
  } catch (cause) {
    if (current === ruleGeneration && (cause as Error).name !== "AbortError") ruleError.value = cause instanceof Error ? cause.message : "规则解析失败";
  } finally { if (current === ruleGeneration) planning.value = false; }
}
function hasNarrowEntityRole(value: QueryPlan) {
  const roles = value.entity_roles || [];
  return roles.length > 0 && !(roles.includes("subject") && roles.includes("product"));
}
function applyRulePlan() {
  const value = rulePlan.value;
  if (!value) return;
  if (value.requires_clarification || value.free_text || value.filters.entity_ids?.length || hasNarrowEntityRole(value)) {
    ruleError.value = "该解析包含当前筛选无法完整表达的条件，请改用分类、关键词和日期筛选。";
    return;
  }
  if (value.filters.category && !(value.filters.category in categoryName)) {
    ruleError.value = "解析出的分类无法由当前筛选表达。";
    return;
  }
  if (value.filters.category) category.value = value.filters.category as Category;
  if (value.filters.date_from) from.value = value.filters.date_from;
  if (value.filters.date_to) to.value = value.filters.date_to;
  rangeMode.value = "custom";
  rulePlan.value = undefined;
}
function selectCategory(value: Category) { category.value = value; }
function openEvent(event: MouseEvent, id: string) {
  if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  void router.push({ path: route.path, query: { ...route.query, event: id } });
}
function eventHref(id: string) { return router.resolve({ path: `/events/${id}`, query: route.query.demo === "1" ? { demo: "1" } : {} }).href; }
async function submit() {
  if (!question.value || missingDates.value || invalid.value || tooWide.value) return;
  const current = ++answerGeneration;
  controller.value?.abort();
  timers.forEach(clearTimeout);
  timers = [];
  controller.value = new AbortController();
  result.value = undefined;
  plan.value = undefined;
  error.value = undefined;
  tokens.value = "";
  sources.value = [];
  metrics.value = undefined;
  running.value = true;
  try {
    if (isDemo()) {
      for await (const event of parseSse(slowStream(), controller.value.signal)) {
        if (current !== answerGeneration) return;
        if (event.event === "status") status.value = "模拟流：正在检索";
        if (event.event === "token") tokens.value += JSON.parse(event.data).text;
        if (event.event === "sources") sources.value = JSON.parse(event.data).items as Citation[];
        if (event.event === "done") {
          const done = JSON.parse(event.data) as Pick<AskResult, "scope_total" | "retrieved_count" | "summarized_count" | "citation_count" | "coverage"> & { status?: string };
          metrics.value = done;
          status.value = done.status === "completed" ? "模拟流已完成" : "模拟流失败";
        }
      }
    } else {
      status.value = "正在检索并汇总…";
      const response = await ask({ question: question.value, filters: filters.value, timezone: "Asia/Shanghai", answer_mode: "concise", client_request_id: crypto.randomUUID() }, controller.value.signal);
      if (current !== answerGeneration) return;
      plan.value = queryPlanFrom(response);
      const view = askView(response);
      result.value = response;
      sources.value = view.citations;
      metrics.value = response;
      status.value = view.status;
    }
  } catch (cause) {
    if (current !== answerGeneration) return;
    if ((cause as Error).name === "AbortError") status.value = "已取消，未自动重试。";
    else { error.value = err(cause); plan.value = queryPlanFrom(cause); }
  } finally { if (current === answerGeneration) running.value = false; }
}
function cancel() { answerGeneration++; controller.value?.abort(); timers.forEach(clearTimeout); timers = []; running.value = false; status.value = "已取消，未自动重试。"; }
async function toggle(index: number) { expanded.value = expanded.value === index ? undefined : index; await nextTick(); document.getElementById(`citation-${index}`)?.focus(); }
watch([keyword, category, from, to, minImportance], scheduleOverview);
watch([keyword, category, from, to, minImportance], () => {
  const filters = { q: keyword.value || undefined, category: category.value || undefined, date_from: from.value || undefined, date_to: to.value || undefined, min_importance: minImportance.value ? 4 : undefined };
  const parts = ["日期：" + (from.value || "未选择") + " 至 " + (to.value || "未选择"), category.value ? "分类：" + (categoryName[category.value] || category.value) : "", keyword.value ? "关键词「" + keyword.value + "」" : "", minImportance.value ? "重要度：4及以上" : ""].filter(Boolean);
  setAssistantScope({ label: "当前统计范围", filters, snapshot: parts.join(" · "), applyPlan: (plan) => { if (plan.entity_ids?.length || plan.category && !(plan.category in categoryName)) return false; if (plan.category) category.value = plan.category as Category; if (plan.date_from) from.value = plan.date_from; if (plan.date_to) to.value = plan.date_to; rangeMode.value = "custom"; return true; } });
}, { immediate: true });
watch(question, () => {
  ruleGeneration++;
  ruleController?.abort();
  rulePlan.value = undefined;
  ruleError.value = "";
});
onMounted(() => { void loadOverview(); document.addEventListener("visibilitychange", () => { if (document.hidden && playing.value) togglePlayback(); }); });
onBeforeUnmount(() => { answerGeneration++; overviewGeneration++; controller.value?.abort(); overviewController?.abort(); ruleController?.abort(); timers.forEach(clearTimeout); clearTimeout(timer); clearInterval(playback); });
</script>

<template>
  <section class="ask-overview">
    <h1 class="page-title">统计与问答</h1>
    <p class="ask-overview__intro">统计由库内事件计算，无需 AI。</p>
    <section class="ask-controls" aria-label="统计范围">
      <div class="ask-range-buttons">
        <button :aria-pressed="rangeMode === 'today'" @click="setRange('today')">今天</button>
        <button :aria-pressed="rangeMode === 'week'" @click="setRange('week')">近7天</button>
        <button :aria-pressed="rangeMode === 'month'" @click="setRange('month')">本月</button>
        <button :aria-pressed="rangeMode === 'custom'" @click="rangeMode = 'custom'">自定义</button>
      </div>
      <div v-if="rangeMode === 'custom'" class="ask-custom-dates">
        <label>从<input v-model="from" name="date_from" type="date" class="control" /></label>
        <label>至<input v-model="to" name="date_to" type="date" class="control" /></label>
      </div>
      <details class="ask-more">
        <summary>更多筛选</summary>
        <div>
          <label>分类<select v-model="category" class="control"><option value="">全部</option><option v-for="(label, key) in categoryName" :key="key" :value="key">{{ label }}</option></select></label>
          <label>关键词<input v-model="keyword" class="control" placeholder="标题、摘要或实体" /></label>
          <label class="ask-importance"><input v-model="minImportance" type="checkbox" />重要度 4 及以上</label>
        </div>
      </details>
    </section>
    <p v-if="missingDates" class="status danger" role="alert">请选择完整的起止日期后再计算统计。</p>
    <p v-else-if="invalid" class="status danger" role="alert">日期范围无效：起始日期不能晚于截止日期。</p>
    <p v-else-if="tooWide" class="status danger" role="alert">日期范围最多 366 天，请缩小范围。</p>
    <p v-else class="ask-summary" data-testid="insights-summary" aria-live="polite">
      {{ overviewLoading ? "正在计算总览…" : overview ? `精确匹配 ${overview.total_events} 条事件 · ${rangeLabel}` : "尚未取得总览" }}
      <span v-if="filterLabel"> · {{ filterLabel }}</span>
    </p>
    <div v-if="overviewError" class="card error" data-testid="insights-error" role="alert">{{ overviewError }} <button @click="loadOverview()">重试</button></div>
    <template v-else-if="overview">
      <p v-if="!overview.total_events" class="ask-empty">当前范围暂无已收录事件。<button v-if="rangeMode === 'today'" @click="setRange('week')">查看近7天</button></p>
      <div v-else class="ask-charts">
        <section class="ask-chart" data-testid="insights-visual" :data-view="chartView">
          <h2>分类趋势</h2>
          <p class="meta">{{ spanDays > 31 ? "按自然月汇总，边界月仅计选定日期" : "按日统计" }} · 联合分类计数总和 {{ overview.total_events }} 条</p>
          <div class="chart-tabs" role="tablist" aria-label="统计视图">
            <button data-view="A" :aria-pressed="chartView === 'flow'" @click="chartView = 'flow'">A 分类流向</button>
            <button data-view="B" :aria-pressed="chartView === 'area'" @click="chartView = 'area'">B 堆叠面积</button>
            <button data-view="C" :aria-pressed="chartView === 'heat'" @click="chartView = 'heat'">C 热力矩阵</button>
          </div>
          <template v-if="chartView === 'flow'">
            <div class="chart-scroll"><svg class="native-chart" viewBox="0 0 720 190" role="img" aria-label="按日期和分类的流向图">
              <g v-for="(categoryKey, categoryIndex) in chartCategories" :key="categoryKey">
                <path class="chart-flow" :d="flowPath(categoryKey, categoryIndex)" :class="'chart-flow--' + categoryIndex" />
                <text x="2" :y="28 + categoryIndex * 23">{{ categoryName[categoryKey] }}</text>
              </g>
              <g v-for="(bucket, index) in jointBuckets" :key="bucket.date"><circle v-for="(categoryKey, categoryIndex) in chartCategories" :key="categoryKey" :cx="chartX(index)" :cy="24 + categoryIndex * 23 - bucket.counts[categoryKey] / jointMax * 12" r="5" role="button" tabindex="0" :data-date-from="bucket.from" :data-date-to="bucket.to" :data-category="categoryKey" :aria-label="bucket.label + `，` + categoryName[categoryKey] + `，` + bucket.counts[categoryKey] + `条`" @click="category = categoryKey; chooseBucket(bucket)" @keydown.enter.prevent="category = categoryKey; chooseBucket(bucket)" /><text :x="chartX(index)" y="184">{{ bucket.label }}</text></g>
            </svg></div>
          </template>
          <template v-else-if="chartView === 'area'">
            <p><button :aria-pressed="playing" @click="togglePlayback">{{ playing ? "暂停播放" : "播放日期" }}</button><span class="meta"> {{ jointBuckets[activeBucket]?.label || "无日期" }}</span></p>
            <div class="chart-scroll"><svg class="native-chart" viewBox="0 0 720 190" role="img" aria-label="分类堆叠面积图">
              <path v-for="(categoryKey, categoryIndex) in chartCategories" :key="categoryKey" :d="areaPath(categoryKey)" :class="'chart-area chart-area--' + categoryIndex" @click="selectCategory(categoryKey)" />
              <line x1="18" y1="146" x2="282" y2="146" />
              <circle v-if="jointBuckets.length === 1" cx="150" :cy="146 - jointBuckets[0].total / jointTotal * 122" r="5" />
            </svg></div>
          </template>
          <template v-else>
            <div class="heatmap" role="grid" aria-label="日期和分类热力矩阵" :style="{ gridTemplateColumns: `minmax(90px, auto) repeat(${jointBuckets.length}, minmax(56px, 1fr))` }">
              <span></span><button v-for="bucket in jointBuckets" :key="'head-' + bucket.date" @click="chooseBucket(bucket)">{{ bucket.label }}</button>
              <template v-for="categoryKey in chartCategories" :key="categoryKey"><strong>{{ categoryName[categoryKey] }}</strong><button v-for="bucket in jointBuckets" :key="categoryKey + bucket.date" class="heatmap-cell" :data-date-from="bucket.from" :data-date-to="bucket.to" :data-category="categoryKey" :style="{ '--heat': heatOpacity(bucket.counts[categoryKey]) }" :aria-label="bucket.label + '，' + categoryName[categoryKey] + '，' + bucket.counts[categoryKey] + '条'" @click="category = categoryKey; chooseBucket(bucket)">{{ bucket.counts[categoryKey] }}</button></template>
            </div>
          </template>
          <details class="ask-data-table"><summary>查看数据表</summary><table><thead><tr><th>日期</th><th v-for="categoryKey in chartCategories" :key="categoryKey">{{ categoryName[categoryKey] }}</th><th>合计</th></tr></thead><tbody><tr v-for="bucket in jointBuckets" :key="bucket.date"><td>{{ bucket.from === bucket.to ? bucket.from : bucket.from + " 至 " + bucket.to }}</td><td v-for="categoryKey in chartCategories" :key="categoryKey">{{ bucket.counts[categoryKey] }}</td><td>{{ bucket.total }}</td></tr></tbody></table></details>
        </section>
      </div>
    </template>
    <section class="ask-events" data-testid="insights-events">
      <h2>匹配事件</h2><p v-if="listLoading" class="meta">正在读取事件…</p><p v-else-if="listError" class="error">{{ listError }}</p><p v-else-if="!listItems.length" class="meta">当前范围没有可列出的事件。</p>
      <article v-for="item in listItems" :key="item.id"><span class="pill">{{ categoryName[item.category] || item.category }}</span><h3><a :href="eventHref(item.id)" @click="openEvent($event, item.id)">{{ item.title_zh }}</a></h3><p class="muted">{{ item.summary_zh }}</p></article>
      <button v-if="listNext && !listLoading" @click="loadOverview(listNext, true)">加载更多</button>
    </section>
  </section>
  <EventDrawers :base-path="route.path" />
</template>