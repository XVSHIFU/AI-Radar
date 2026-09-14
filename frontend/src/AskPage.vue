<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ask, err, events, isDemo, type AskResult, type Category, type Citation, type Event } from "./api";
import EventDrawers from "./EventDrawers.vue";
import { insights, type InsightResult } from "./insights-api";
import { parseSse } from "./sse";
import { askView } from "./ask-result";
import { queryPlanFrom, type QueryPlan } from "./query-plan";

const route = useRoute();
const router = useRouter();
const categoryName: Record<string, string> = {
  model_release: "模型发布", agent_tool: "智能体工具", framework_sdk: "框架与 SDK",
  research: "研究", product: "产品", industry: "产业",
};
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
const errorGuidance: Record<string, string> = { MODEL_UNAVAILABLE: "生成模型尚未配置，已显示可用的检索范围。", QUERY_UNSUPPORTED: "当前问题包含暂不支持的检索表达。", CLARIFICATION_REQUIRED: "需要先澄清检索条件后才能继续。" };
const errorDescription = (value: ReturnType<typeof err>) => errorGuidance[value.code] ? `${errorGuidance[value.code]} ${value.message}` : value.message;
const invalid = computed(() => Boolean(from.value && to.value && from.value > to.value));
const spanDays = computed(() => Math.floor((Date.parse(`${to.value}T00:00:00Z`) - Date.parse(`${from.value}T00:00:00Z`)) / 86400000) + 1);
const tooWide = computed(() => !invalid.value && spanDays.value > 366);
const filters = computed(() => ({ q: keyword.value || undefined, category: category.value || undefined, date_from: from.value, date_to: to.value, min_importance: minImportance.value ? 4 : undefined }));
const chartRows = computed(() => overview.value?.daily || []);
const maxDaily = computed(() => Math.max(1, ...chartRows.value.map((row) => row.count)));
const categories = computed(() => overview.value?.categories || []);
const maxCategory = computed(() => Math.max(1, ...categories.value.map((row) => row.count)));
const rangeLabel = computed(() => `${from.value} 至 ${to.value}（Asia/Shanghai，起止均包含）`);
const filterLabel = computed(() => [category.value ? `分类：${categoryName[category.value] || category.value}` : "", keyword.value ? `关键词：${keyword.value}` : "", minImportance.value ? "重要度：4及以上" : ""].filter(Boolean).join(" · "));
const validUrl = (url: string) => /^https?:\/\//i.test(url);
function slowStream() {
  let control: ReadableStreamDefaultController<Uint8Array>;
  const emit = (value: string, ms: number) => timers.push(window.setTimeout(() => control.enqueue(new TextEncoder().encode(value)), ms));
  return new ReadableStream<Uint8Array>({ start(c) { control = c; emit('event: status\ndata: {"phase":"retrieving"}\n\n', 150); emit('event: token\ndata: {"text":"这是"}\n\n', 450); emit('event: token\ndata: {"text":"明确标注的模拟回答。[2]"}\n\n', 850); emit('event: sources\ndata: {"items":[{"index":2,"title":"合成演示来源","source_url":"https://example.invalid/demo","quote_text":"合成段落摘录","paragraph_id":"demo-p-001"}]}\n\n', 1150); emit('event: done\ndata: {"status":"completed","scope_total":1,"retrieved_count":1,"summarized_count":1,"citation_count":1,"coverage":"complete"}\n\n', 1450); timers.push(window.setTimeout(() => c.close(), 1600)); }, cancel() { timers.forEach(clearTimeout); timers = []; } });
}
function setRange(mode: "today" | "week" | "month" | "custom") {
  rangeMode.value = mode;
  if (mode === "today") from.value = to.value = today;
  if (mode === "week") { from.value = addDays(today, -6); to.value = today; }
  if (mode === "month") { from.value = `${today.slice(0, 8)}01`; to.value = today; }
}
function resetAnswer() {
  answerGeneration++;
  controller.value?.abort();
  running.value = false;
  result.value = undefined;
  tokens.value = "";
  sources.value = [];
  metrics.value = undefined;
  plan.value = undefined;
  error.value = undefined;
  status.value = "范围已更新，之前的回答已清除。";
}
async function loadOverview(cursor?: string, append = false) {
  overviewController?.abort();
  if (invalid.value || tooWide.value) {
    overview.value = undefined; listItems.value = []; listNext.value = null; overviewLoading.value = false; listLoading.value = false;
    return;
  }
  const current = ++overviewGeneration;
  overviewController = new AbortController();
  overviewLoading.value = true; listLoading.value = true; overviewError.value = ""; listError.value = "";
  if (!append) { listItems.value = []; listNext.value = null; }
  try {
    const [summary, rows] = await Promise.all([
      insights({ q: filters.value.q, category: filters.value.category, date_from: from.value, date_to: to.value, min_importance: filters.value.min_importance }, overviewController.signal),
      events.list({ ...filters.value, limit: 10, cursor }, overviewController.signal),
    ]);
    if (current !== overviewGeneration) return;
    overview.value = summary;
    listItems.value = append ? [...listItems.value, ...(rows.items as Event[])] : (rows.items as Event[]);
    listNext.value = rows.next_cursor;
  } catch (cause) {
    if (current !== overviewGeneration || (cause as Error).name === "AbortError") return;
    const message = cause instanceof Error ? cause.message : "统计请求失败";
    overviewError.value = message; listError.value = message;
  } finally {
    if (current === overviewGeneration) { overviewLoading.value = false; listLoading.value = false; }
  }
}
function scheduleOverview() {
  clearTimeout(timer);
  resetAnswer();
  timer = window.setTimeout(() => void loadOverview(), 260);
}
function selectDay(date: string) { rangeMode.value = "custom"; from.value = date; to.value = date; }
async function planFromQuestion() {
  const current = ++ruleGeneration;
  ruleController?.abort(); ruleController = new AbortController(); ruleError.value = ""; rulePlan.value = undefined; planning.value = true;
  try {
    const response = await fetch("/api/v1/query-plan", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question: question.value, filters: {}, timezone: "Asia/Shanghai", client_request_id: crypto.randomUUID() }), signal: ruleController.signal });
    if (!response.ok) throw new Error("规则解析请求失败");
    const raw = await response.json();
    if (current !== ruleGeneration) return;
    const parsed = queryPlanFrom(raw) || (raw as QueryPlan);
    if (!parsed.filters || parsed.requires_clarification === undefined) throw new Error("规则解析结果无效");
    rulePlan.value = parsed;
  } catch (cause) { if (current === ruleGeneration && (cause as Error).name !== "AbortError") ruleError.value = cause instanceof Error ? cause.message : "规则解析失败"; }
  finally { if (current === ruleGeneration) planning.value = false; }
}
function applyRulePlan() {
  const value = rulePlan.value; if (!value) return;
  if (value.requires_clarification || value.free_text || value.filters.entity_ids?.length) { ruleError.value = "该解析包含当前筛选无法完整表达的条件，请改用分类、关键词和日期筛选。"; return; }
  if (value.filters.category && value.filters.category in categoryName) category.value = value.filters.category as Category;
  if (value.filters.date_from) from.value = value.filters.date_from;
  if (value.filters.date_to) to.value = value.filters.date_to;
  rangeMode.value = "custom";
}
function selectCategory(value: Category) { category.value = value; }
function openEvent(event: MouseEvent, id: string) {
  if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  void router.push({ path: route.path, query: { ...route.query, event: id } });
}
function eventHref(id: string) { return router.resolve({ path: `/events/${id}`, query: route.query.demo === "1" ? { demo: "1" } : {} }).href; }
async function submit() {
  if (!question.value || invalid.value || tooWide.value) return;
  const current = ++answerGeneration;
  controller.value?.abort();
  controller.value = new AbortController();
  result.value = undefined; error.value = undefined; tokens.value = ""; sources.value = []; metrics.value = undefined; plan.value = undefined; running.value = true;
  try {
    status.value = "正在检索并汇总…";
    const response = await ask({ question: question.value, filters: filters.value, timezone: "Asia/Shanghai", answer_mode: "concise", client_request_id: crypto.randomUUID() }, controller.value.signal);
    if (current !== answerGeneration) return;
    plan.value = queryPlanFrom(response);
    const view = askView(response);
    result.value = response; sources.value = view.citations; metrics.value = response; status.value = view.status;
  } catch (cause) {
    if (current !== answerGeneration) return;
    if ((cause as Error).name === "AbortError") status.value = "已取消，未自动重试。";
    else { error.value = err(cause); plan.value = queryPlanFrom(cause); }
  } finally { if (current === answerGeneration) running.value = false; }
}
function cancel() { answerGeneration++; controller.value?.abort(); timers.forEach(clearTimeout); timers = []; running.value = false; status.value = "已取消，未自动重试。"; }
async function toggle(index: number) { expanded.value = expanded.value === index ? undefined : index; await nextTick(); document.getElementById(`citation-${index}`)?.focus(); }
watch([keyword, category, from, to, minImportance], scheduleOverview);
onMounted(() => void loadOverview());
onBeforeUnmount(() => { answerGeneration++; overviewGeneration++; controller.value?.abort(); overviewController?.abort(); ruleController?.abort(); timers.forEach(clearTimeout); clearTimeout(timer); });
</script>

<template>
  <section class="ask-overview">
    <h1 class="page-title">统计与问答</h1>
    <p class="ask-overview__intro">统计由库内事件计算，无需 AI。</p>
    <section class="ask-controls" aria-label="统计范围">
      <div class="ask-range-buttons"><button :aria-pressed="rangeMode === 'today'" @click="setRange('today')">今天</button><button :aria-pressed="rangeMode === 'week'" @click="setRange('week')">近7天</button><button :aria-pressed="rangeMode === 'month'" @click="setRange('month')">本月</button><button :aria-pressed="rangeMode === 'custom'" @click="rangeMode = 'custom'">自定义</button></div>
      <div v-if="rangeMode === 'custom'" class="ask-custom-dates"><label>从<input v-model="from" name="date_from" type="date" class="control" /></label><label>至<input v-model="to" name="date_to" type="date" class="control" /></label></div>
      <details class="ask-more"><summary>更多筛选</summary><div><label>分类<select v-model="category" class="control"><option value="">全部</option><option v-for="(label, key) in categoryName" :key="key" :value="key">{{ label }}</option></select></label><label>关键词<input v-model="keyword" class="control" placeholder="标题、摘要或实体" /></label><label class="ask-importance"><input v-model="minImportance" type="checkbox" />重要度 4 及以上</label></div></details>
    </section>
    <p v-if="invalid" class="status danger" role="alert">日期范围无效：起始日期不能晚于截止日期。</p><p v-else-if="tooWide" class="status danger" role="alert">日期范围最多 366 天，请缩小范围。</p>
    <p v-else class="ask-summary" data-testid="insights-summary" aria-live="polite">{{ overviewLoading ? '正在计算总览…' : `精确匹配 ${overview?.total_events ?? 0} 条事件 · ${rangeLabel}` }}</p>
    <div v-if="overviewError" class="card error" data-testid="insights-error" role="alert">{{ overviewError }} <button @click="loadOverview()">重试</button></div>
    <template v-else-if="overview">
      <p v-if="!overview.total_events" class="ask-empty">当前范围暂无已收录事件。<button v-if="rangeMode === 'today'" @click="setRange('week')">查看近7天</button></p>
      <div class="ask-charts"><section class="ask-chart" data-testid="insights-daily"><h2>每日事件</h2><p class="meta">按日统计</p><div class="daily-bars" role="list" aria-label="每日事件数"><button v-for="row in chartRows" :key="row.date" :data-date-from="row.date" :data-date-to="row.date" :style="{ height: `${Math.max(20, row.count / maxDaily * 150)}px` }" :aria-label="`${row.date}，${row.count} 条`" @click="selectDay(row.date)"><span>{{ row.count }}</span><small>{{ row.date.slice(5) }}</small></button></div><details><summary>查看数据表</summary><table><thead><tr><th>日期</th><th>事件数</th></tr></thead><tbody><tr v-for="row in chartRows" :key="row.date"><td>{{ row.date }}</td><td>{{ row.count }}</td></tr></tbody></table></details></section><section class="ask-chart" data-testid="insights-categories"><h2>分类分布</h2><p class="meta">点击条形筛选</p><div class="category-bars" role="list"><button v-for="row in categories" :key="row.category" :data-category="row.category" @click="selectCategory(row.category)"><span>{{ categoryName[row.category] || row.category }}</span><i :style="{ width: `${row.count / maxCategory * 100}%` }"></i><b>{{ row.count }}</b></button></div><details><summary>查看数据表</summary><table><thead><tr><th>分类</th><th>事件数</th></tr></thead><tbody><tr v-for="row in categories" :key="row.category"><td>{{ categoryName[row.category] || row.category }}</td><td>{{ row.count }}</td></tr></tbody></table></details></section></div>
    </template>
    <section class="ask-question"><h2>对这个范围提问</h2><label>问题<textarea v-model="question" class="control" rows="4" placeholder="输入需要核查的 AI 进展问题" /></label><div class="row"><button class="primary" :disabled="running || !question || invalid || tooWide" @click="submit">开始分析</button><button :disabled="planning || !question" @click="planFromQuestion">按问题筛选（规则解析）</button><button v-if="running" @click="cancel">取消</button></div><p v-if="ruleError" class="error" role="alert">{{ ruleError }}</p><section v-if="rulePlan" class="query-plan"><p>规则解析：分类 {{ rulePlan.filters.category || "沿用当前" }} · 日期 {{ rulePlan.filters.date_from || from }} 至 {{ rulePlan.filters.date_to || to }}</p><p v-if="rulePlan.requires_clarification || rulePlan.free_text || rulePlan.filters.entity_ids?.length" class="meta">部分条件无法完整映射到当前筛选，请改用筛选控件。</p><button @click="applyRulePlan">应用到总览</button></section><p class="meta" aria-live="polite">{{ status }}</p><div v-if="error" class="card error" role="alert"><strong>{{ error.code }}</strong>：{{ errorDescription(error) }}</div><section v-if="plan" class="card query-plan" data-testid="query-plan"><h2>检索范围</h2><p>分类：{{ plan.filters.category || '全部' }} · 日期：{{ plan.filters.date_from || '不限' }} 至 {{ plan.filters.date_to || '不限' }}</p></section><article v-if="result || tokens" class="evidence-layer" data-testid="ask-answer"><p v-if="isDemo()" class="demo">模拟流，仅用于演示。</p><h2>回答</h2><p class="answer-body">{{ tokens || result?.answer }}</p><div v-for="source in sources" :key="source.index" class="evidence-item"><button :aria-expanded="expanded === source.index" @click="toggle(source.index)">[{{ source.index }}] {{ source.title }}</button><blockquote v-if="expanded === source.index" :id="`citation-${source.index}`" tabindex="-1">{{ source.quote_text || '无段落摘录' }}</blockquote><a v-if="validUrl(source.source_url)" :href="source.source_url" target="_blank" rel="noopener">打开来源</a></div><p v-if="metrics" class="meta">完整匹配 {{ metrics.scope_total }} · 覆盖：{{ metrics.coverage }}</p></article></section>
    <section class="ask-events" data-testid="insights-events"><h2>匹配事件</h2><p v-if="listLoading" class="meta">正在读取事件…</p><p v-else-if="listError" class="error">{{ listError }}</p><p v-else-if="!listItems.length" class="meta">当前范围没有可列出的事件。</p><article v-for="item in listItems" :key="item.id"><span class="pill">{{ categoryName[item.category] || item.category }}</span><h3><a :href="eventHref(item.id)" @click="openEvent($event, item.id)">{{ item.title_zh }}</a></h3><p class="muted">{{ item.summary_zh }}</p></article><button v-if="listNext && !listLoading" @click="loadOverview(listNext, true)">加载更多</button></section>
  </section>
  <EventDrawers :base-path="route.path" />
</template>