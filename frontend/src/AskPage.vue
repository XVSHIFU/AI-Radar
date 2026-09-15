<script setup lang="ts">
import { translate as tr } from "./locale";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { events, type Category, type Event } from "./api";
import EventDrawers from "./EventDrawers.vue";
import DateRangePicker from "./DateRangePicker.vue";
import type {DateRange} from "./date-range";
import { insights, type InsightResult } from "./insights-api";
import { parseSse } from "./sse";
import { askView } from "./ask-result";
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
const rangeMode = ref<"today" | "week" | "month30" | "month" | "custom">("today");
const overview = ref<InsightResult>();
const overviewLoading = ref(false);
const overviewError = ref("");
const listItems = ref<Event[]>([]);
const listNext = ref<string | null>(null);
const listLoading = ref(false);
const listError = ref("");
let overviewController: AbortController | undefined;
let overviewGeneration = 0;
let timer: number | undefined;
const missingDates = computed(() => !from.value || !to.value);
const invalid = computed(() => Boolean(from.value && to.value && from.value > to.value));
const spanDays = computed(() => missingDates.value ? 0 : Math.floor((Date.parse(`${to.value}T00:00:00Z`) - Date.parse(`${from.value}T00:00:00Z`)) / 86400000) + 1);
const tooWide = computed(() => !invalid.value && spanDays.value > 366);
const filters = computed(() => ({ q: keyword.value || undefined, category: category.value || undefined, date_from: from.value || undefined, date_to: to.value || undefined, min_importance: minImportance.value ? 4 : undefined }));
const categories = computed(() => { const counts = new Map(overview.value?.categories.map((row) => [row.category, row.count]) || []); return allCategories.map((category) => ({ category, count: counts.get(category) || 0 })); });
const chartBuckets = computed(() => { const rows = overview.value?.daily || []; if (spanDays.value <= 31) return rows.map((row) => ({ ...row, from: row.date, to: row.date, label: row.date.slice(5) })); const buckets = new Map<string, { date:string; count:number; from:string; to:string; label:string }>(); for (const row of rows) { const key=row.date.slice(0,7); const old=buckets.get(key); if(old){old.count+=row.count;old.to=row.date}else buckets.set(key,{date:key,count:row.count,from:row.date,to:row.date,label:key}); } return [...buckets.values()]; });
const chartView = ref<"A" | "B" | "C">("C");
const rankedCategories = computed(() => categories.value.map((row) => ({ ...row, share: overview.value?.total_events ? Math.round(row.count / overview.value.total_events * 100) : 0 })).sort((a,b) => b.count - a.count || a.category.localeCompare(b.category)));
const rankMax = computed(() => Math.max(1, ...rankedCategories.value.map((row) => row.count)));
const dailyBins = computed(() => chartBuckets.value);
const dailyMax = computed(() => Math.max(1, ...dailyBins.value.map((row) => row.count)));
const peakDays = computed(() => dailyBins.value.filter((row) => row.count === dailyMax.value));
const heatMax = computed(() => jointMax.value);
const heatPalette=["#e8edf1","#f7eeeb","#f2dcd5","#eac7bd","#e4b4a6","#dba08e","#ce8673","#c2725d","#b65e49","#a94b3b","#9d3c2e","#8f3027","#822a23"];
const heatLevel=(count:number)=>count?Math.max(1,Math.ceil(count/heatMax.value*12)):0;
const heatColor=(count:number)=>heatPalette[heatLevel(count)];
const heatText=(count:number)=>heatLevel(count)>=8?"#fff":"#201511";
const factSummary = computed(() => { const top = rankedCategories.value[0]; if (!top || !overview.value) return "尚无完整匹配事件。"; const ties = rankedCategories.value.filter((row) => row.count === top.count); return ties.length > 1 ? `${overview.value.total_events} 条完整匹配事件；${ties.map((row) => categoryName[row.category]).join("、")}并列最多，各 ${top.count} 条。` : `${overview.value.total_events} 条完整匹配事件；${categoryName[top.category]}最多，共 ${top.count} 条。`; });
const jointBuckets = computed(() => overview.value ? categoryBuckets(overview.value.daily_categories, spanDays.value > 31) : []);
const jointMax = computed(() => Math.max(1, ...jointBuckets.value.flatMap((bucket) => chartCategories.map((category) => bucket.counts[category]))));
const jointTotal = computed(() => Math.max(1, ...jointBuckets.value.map((bucket) => bucket.total)));
const activeBucket = ref(0);
const playing = ref(false);
const flowPlaying = ref(false);
const motionReduced = ref(matchMedia("(prefers-reduced-motion: reduce)").matches);
let playback: number | undefined;
function chartX(index: number) { return jointBuckets.value.length < 2 ? 360 : 40 + index * 640 / (jointBuckets.value.length - 1); }
const flowHeight = computed(() => Math.max(220, 58 + jointBuckets.value.length * 24));
function flowBucketY(index: number) { return jointBuckets.value.length < 2 ? 108 : 42 + index * 24; }
function flowBand(category: Category, categoryIndex: number, bucketIndex: number) { const count = jointBuckets.value[bucketIndex]?.counts[category] || 0; if (!count) return ""; const thickness = 3 + count / jointMax.value * 15; const sourceY = 32 + categoryIndex * 25; const targetY = flowBucketY(bucketIndex); return `M 180 ${sourceY - thickness / 2} C 310 ${sourceY - thickness / 2}, 450 ${targetY - thickness / 2}, 560 ${targetY - thickness / 2} L 560 ${targetY + thickness / 2} C 450 ${targetY + thickness / 2}, 310 ${sourceY + thickness / 2}, 180 ${sourceY + thickness / 2} Z`; }
function areaPath(category: Category, reveal = jointBuckets.value.length) { const visible = jointBuckets.value.slice(0, reveal); const upper = visible.map((bucket, index) => { const previous = chartCategories.slice(0, chartCategories.indexOf(category)).reduce((sum, item) => sum + bucket.counts[item], 0); return `${index ? "L" : "M"}${chartX(index)} ${146 - (previous + bucket.counts[category]) / jointTotal.value * 122}`; }); const lower = [...visible].reverse().map((bucket, offset) => { const index = visible.length - 1 - offset; const previous = chartCategories.slice(0, chartCategories.indexOf(category)).reduce((sum, item) => sum + bucket.counts[item], 0); return `L${chartX(index)} ${146 - previous / jointTotal.value * 122}`; }); return `${upper.join(" ")} ${lower.join(" ")} Z`; }
function heatOpacity(count: number) { return 0.14 + count / jointMax.value * 0.78; }
function heatTextColor(count: number) { return count / jointMax.value > 0.52 ? "#fff" : "#102a43"; }
function chartColor(index: number) { return ["#1d5f95", "#4f7d4d", "#92602a", "#7b5a9e", "#a04d5d", "#3d7f80"][index]; }
function chooseBucket(bucket: { from: string; to: string }) { selectDay(bucket.from, bucket.to); }
function stopMotion() { flowPlaying.value = false; playing.value = false; clearInterval(playback); }
function togglePlayback() { if (motionReduced.value) return; playing.value = !playing.value; if (playing.value) { clearInterval(playback); playback = window.setInterval(() => { activeBucket.value = jointBuckets.value.length ? (activeBucket.value + 1) % jointBuckets.value.length : 0; }, 900); } else clearInterval(playback); }
function toggleFlow() { if (!motionReduced.value) flowPlaying.value = !flowPlaying.value; }
const rangeLabel = computed(() => `${from.value || "未选择"} 至 ${to.value || "未选择"}（Asia/Shanghai，起止均包含）`);
const filterLabel = computed(() => [category.value ? `分类：${categoryName[category.value] || category.value}` : "", keyword.value ? `关键词：${keyword.value}` : "", minImportance.value ? "重要度：4及以上" : ""].filter(Boolean).join(" · "));
function setRange(mode: "today" | "week" | "month30" | "month" | "custom") {
  rangeMode.value = mode;
  if (mode === "today") from.value = to.value = today;
  if (mode === "week") { from.value = addDays(today, -6); to.value = today; }
  if (mode === "month30") { from.value = addDays(today, -29); to.value = today; }
  if (mode === "month") { from.value = `${today.slice(0, 8)}01`; to.value = today; }
}
function applyDates(range:DateRange) { from.value=range.from; to.value=range.to; rangeMode.value="custom"; }
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

  timer = window.setTimeout(() => void loadOverview(), 260);
}
function selectDay(date: string, end = date) { rangeMode.value = "custom"; from.value = date; to.value = end; }
function selectCategory(value: Category) { category.value = value; }
function openEvent(event: MouseEvent, id: string) {
  if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  void router.push({ path: route.path, query: { ...route.query, event: id } });
}
function eventHref(id: string) { return router.resolve({ path: `/events/${id}`, query: route.query.demo === "1" ? { demo: "1" } : {} }).href; }
watch([keyword, category, from, to, minImportance], scheduleOverview);
watch([keyword, category, from, to, minImportance], () => {
  const filters = { q: keyword.value || undefined, category: category.value || undefined, date_from: from.value || undefined, date_to: to.value || undefined, min_importance: minImportance.value ? 4 : undefined };
  const parts = ["日期：" + (from.value || "未选择") + " 至 " + (to.value || "未选择"), category.value ? "分类：" + (categoryName[category.value] || category.value) : "", keyword.value ? "关键词「" + keyword.value + "」" : "", minImportance.value ? "重要度：4及以上" : ""].filter(Boolean);
  setAssistantScope({ label: "当前统计范围", filters, snapshot: parts.join(" · ") });
}, { immediate: true });
const onVisibilityChange = () => { if (document.hidden) stopMotion(); };
const onAssistantPlan = (event: globalThis.Event) => { const plan = (event as unknown as globalThis.CustomEvent<{ category?: string; date_from?: string; date_to?: string }>).detail; if (plan.category && plan.category in categoryName) category.value = plan.category as Category; if (plan.date_from) from.value = plan.date_from; if (plan.date_to) to.value = plan.date_to; rangeMode.value = "custom"; };
onMounted(() => { window.addEventListener("assistant-apply-plan", onAssistantPlan as EventListener); void loadOverview(); document.addEventListener("visibilitychange", onVisibilityChange); });
onBeforeUnmount(() => { overviewGeneration++; overviewController?.abort(); clearTimeout(timer); stopMotion(); document.removeEventListener("visibilitychange", onVisibilityChange); window.removeEventListener("assistant-apply-plan", onAssistantPlan as EventListener); });
</script>

<template>
  <section class="ask-overview">
    <h1 class="page-title">{{ tr("统计与问答", "Insights & Q&A") }}</h1>
    <p class="ask-overview__intro">{{ tr("统计由库内事件计算，无需 AI。", "Statistics are calculated from events in the library; no AI is required.") }}</p>
    <section class="ask-controls" aria-label="统计范围">
      <div class="ask-range-toolbar"><DateRangePicker :from="from" :to="to" @change="applyDates" />
      <div class="ask-range-buttons">
        <button :aria-pressed="rangeMode === 'today'" @click="setRange('today')">{{ tr("今天", "Today") }}</button>
        <button :aria-pressed="rangeMode === 'week'" @click="setRange('week')">{{ tr("近7天", "Last 7 days") }}</button>
        <button :aria-pressed="rangeMode === 'month30'" @click="setRange('month30')">{{ tr("近30天", "Last 30 days") }}</button>
        <button :aria-pressed="rangeMode === 'month'" @click="setRange('month')">{{ tr("本月", "This month") }}</button>
      </div></div>
      <details class="ask-more">
        <summary>{{ tr("更多筛选", "More filters") }}</summary>
        <div>
          <label>{{ tr("分类", "Category") }}<select v-model="category" class="control"><option value="">{{ tr("全部", "All") }}</option><option v-for="(label, key) in categoryName" :key="key" :value="key">{{ label }}</option></select></label>
          <label>{{ tr("关键词", "Keywords") }}<input v-model="keyword" class="control" placeholder="标题、摘要或实体" /></label>
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
    <div v-if="overviewError" class="card error" data-testid="insights-error" role="alert">{{ overviewError }} <button @click="loadOverview()">{{ tr("重试", "Retry") }}</button></div>
    <template v-else-if="overview">
      <p v-if="!overview.total_events" class="ask-empty">当前范围暂无已收录事件。<button v-if="rangeMode === 'today'" @click="setRange('week')">查看近7天</button></p>
      <div v-else class="ask-charts">
        <section class="ask-chart" data-testid="insights-visual" :data-view="chartView">
          <h2>{{ tr("统计视图", "Statistics view") }}</h2>
          <p class="meta">{{ factSummary }}</p>
          <div class="chart-tabs" role="group" aria-label="统计图表类型">
            <button data-view="A" :aria-pressed="chartView === 'A'" @click="chartView = 'A'">A 分类排行</button>
            <button data-view="B" :aria-pressed="chartView === 'B'" @click="chartView = 'B'">B 每日数量</button>
            <button data-view="C" :aria-pressed="chartView === 'C'" @click="chartView = 'C'">C 日期×分类</button>
          </div>
          <div v-if="chartView === 'A'" class="rank-chart">
            <button v-for="row in rankedCategories" :key="row.category" class="rank-row" :data-category="row.category" @click="selectCategory(row.category)"><span>{{ categoryName[row.category] }}</span><i :style="{ width: (row.count / rankMax * 100) + '%' }"></i><b>{{ row.count }} · {{ row.share }}%</b></button>
          </div>
          <div v-else-if="chartView === 'B'"><p v-if="dailyBins.length === 1" class="meta">只有一天数据，不显示趋势。</p><p v-else class="meta">峰值：{{ peakDays.map((row) => row.label + ' ' + row.count + '条').join('、') }}</p><div class="daily-chart"><button v-for="row in dailyBins" :key="row.date" class="daily-count" :data-date-from="row.from" :data-date-to="row.to" :style="{ '--height': (row.count / dailyMax * 180) + 'px' }" @click="selectDay(row.from,row.to)"><b>{{ row.count }}</b><i></i><small>{{ row.label }}</small></button></div></div><div v-else class="heat-compact" role="group" aria-label="日期和分类热力图，可横向滚动" :style="{ '--heat-columns': jointBuckets.length, gridTemplateColumns: 'minmax(88px, auto) repeat(' + jointBuckets.length + ', minmax(34px, 1fr))' }">
            <span></span><span v-for="bucket in jointBuckets" :key="bucket.date">{{ bucket.label }}</span>
            <template v-for="categoryKey in chartCategories" :key="categoryKey"><strong>{{ categoryName[categoryKey] }}</strong><button v-for="bucket in jointBuckets" :key="categoryKey + bucket.date" :aria-label="bucket.label + ' · ' + categoryName[categoryKey] + ' · ' + bucket.counts[categoryKey] + ' 条事件'" :data-category="categoryKey" :data-date-from="bucket.from" :data-date-to="bucket.to" :style="{ '--heat': heatColor(bucket.counts[categoryKey]), color: heatText(bucket.counts[categoryKey]) }" @click="category = categoryKey; selectDay(bucket.from,bucket.to)">{{ bucket.counts[categoryKey] }}</button></template>
          </div>
          <p v-if="chartView === 'C'" class="meta">横向看日期，纵向看分类。点击色块查看对应事件。</p><p v-if="chartView === 'C'" class="meta heat-legend">色标：0 浅灰 · {{ heatMax }} 深红</p>
          <details class="ask-data-table"><summary>{{ tr("查看数据表", "View data table") }}</summary><table><thead><tr><th>日期</th><th v-for="categoryKey in chartCategories" :key="categoryKey">{{ categoryName[categoryKey] }}</th><th>合计</th></tr></thead><tbody><tr v-for="bucket in jointBuckets" :key="bucket.date"><td>{{ bucket.from === bucket.to ? bucket.from : bucket.from + " 至 " + bucket.to }}</td><td v-for="categoryKey in chartCategories" :key="categoryKey">{{ bucket.counts[categoryKey] }}</td><td>{{ bucket.total }}</td></tr></tbody></table></details>
        </section>
      </div>
    </template>
    <section class="ask-events" data-testid="insights-events">
      <h2>匹配事件</h2><p v-if="listLoading" class="meta">{{ tr("正在读取事件…", "Loading events…") }}</p><p v-else-if="listError" class="error">{{ listError }}</p><p v-else-if="!listItems.length" class="meta">当前范围没有可列出的事件。</p>
      <article v-for="item in listItems" :key="item.id"><span class="pill">{{ categoryName[item.category] || item.category }}</span><h3><a :href="eventHref(item.id)" @click="openEvent($event, item.id)">{{ item.title_zh }}</a></h3><p class="muted">{{ item.summary_zh }}</p></article>
      <button v-if="listNext && !listLoading" @click="loadOverview(listNext, true)">{{ tr("加载更多", "Load more") }}</button>
    </section>
  </section>
  <EventDrawers :base-path="route.path" />
</template>
