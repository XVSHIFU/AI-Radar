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
import EventDrawers from "./EventDrawers.vue";
import DateRangePicker from "./DateRangePicker.vue";
import type {DateRange} from "./date-range";
import {
  buildTimeline,
  reconcileTimelineState,
  setTimelineGranularity,
  type TimelineState,
} from "./timeline";
import { locale, formatDate } from "./locale";
import { tx } from "./reading-locale";
import { latestRequest } from "./latest";
import { setAssistantScope } from "./assistant-scope";

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
  statsError = ref(false),
  timelineState = ref<TimelineState>({});
const categories = computed<{ v: Category; l: string }[]>(() => [
  { v: "model_release", l: tx("模型发布", "Model releases") },
  { v: "agent_tool", l: tx("智能体工具", "Agent tools") },
  { v: "framework_sdk", l: tx("框架与 SDK", "Frameworks & SDKs") },
  { v: "research", l: tx("研究", "Research") },
  { v: "product", l: tx("产品", "Products") },
  { v: "industry", l: tx("产业", "Industry") },
]);
const timeline = computed(() => buildTimeline(items.value).map(year => ({ ...year, label: year.unknown ? tx("日期未知", "Date unknown") : locale.value === "en" ? year.key : year.label, months: year.months.map(month => ({ ...month, label: year.unknown ? tx("未提供日期", "No date supplied") : locale.value === "en" ? new Intl.DateTimeFormat("en", { month: "long", timeZone: "UTC" }).format(new Date(month.key+"-01T00:00:00Z")) : month.label, days: month.days.map(day => ({ ...day, label: year.unknown ? tx("日期未知", "Unknown") : locale.value === "en" ? String(Number(day.key.slice(-2))) : day.label })) })) })));
const hasFilters = computed(() =>
  Boolean(q.value || category.value || from.value || to.value),
);
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
    }).filter(([, value]) => value !== undefined),
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
  const request = latest.begin();
  loading.value = true;
  error.value = undefined;
  if (!append) {
    items.value = [];
    next.value = null;
  }
  try {
    const params: EventQuery = {
      q: q.value,
      category: category.value || undefined,
      date_from: from.value || undefined,
      date_to: to.value || undefined,
      limit: 10,
      cursor,
    };
    const response = await events.list(params, request.signal);
    if (!request.current()) return;
    items.value = append
      ? [...items.value, ...(response.items as Event[])]
      : (response.items as Event[]);
    total.value = response.total;
    next.value = response.next_cursor;
  } catch (cause) {
    if (request.current() && (cause as Error).name !== "AbortError")
      error.value = err(cause);
  } finally {
    if (request.current()) loading.value = false;
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
    void router.replace({ query: query() });
    void load();
  }, 300);
}
function applyDates(range: DateRange) { from.value=range.from; to.value=range.to; }
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
function toggle(key: string) {
  timelineState.value = {
    ...timelineState.value,
    [key]: !timelineState.value[key],
  };
}
function setAll(open: boolean) {
  timelineState.value = setTimelineGranularity(timeline.value, open);
}
function directEventHref(id: string) {
  return router.resolve({
    path: `/events/${id}`,
    query: route.query.demo === "1" ? { demo: "1" } : {},
  }).href;
}
function openEvent(event: MouseEvent, id: string) {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  )
    return;
  event.preventDefault();
  const drawerQuery = { ...route.query };
  delete drawerQuery.source;
  delete drawerQuery.evidence;
  drawerQuery.event = id;
  void router.push({ path: route.path, query: drawerQuery });
}
watch(() => route.query, sync, { immediate: true });
watch(timeline, (value) => {
  timelineState.value = reconcileTimelineState(timelineState.value, value);
});
watch([q, category, from, to], schedule);
watch([q, category, from, to], () => {
  const filters = { q: q.value || undefined, category: category.value || undefined, date_from: from.value || undefined, date_to: to.value || undefined };
  const parts = [q.value ? tx("关键词：", "Keyword: ") + q.value : "", category.value ? tx("分类：", "Category: ") + (categories.value.find((item) => item.v === category.value)?.l || category.value) : "", from.value || to.value ? tx("日期：", "Date: ") + (from.value || tx("不限", "Any")) + tx(" 至 ", " to ") + (to.value || tx("不限", "Any")) : ""].filter(Boolean);
  setAssistantScope({ label: tx("当前动态列表范围", "Current event feed"), filters, snapshot: parts.length ? parts.join(" · ") : tx("当前列表范围：未限定单个事件", "Current feed: no single event selected") });
}, { immediate: true });
const onAssistantPlan = (event: globalThis.Event) => { const plan = (event as unknown as globalThis.CustomEvent<{ category?: string; date_from?: string; date_to?: string }>).detail; if (plan.category && categories.value.some((item) => item.v === plan.category)) category.value = plan.category as Category; if (plan.date_from) from.value = plan.date_from; if (plan.date_to) to.value = plan.date_to; };
onMounted(async () => { window.addEventListener("assistant-apply-plan", onAssistantPlan as EventListener);
  load();
  try {
    overview.value = await stats();
  } catch {
    statsError.value = true;
  }
});
window.addEventListener("resize", resize);
onBeforeUnmount(() => {
  latest.cancel();
  clearTimeout(timer.value);
  window.removeEventListener("resize", resize);
  window.removeEventListener("assistant-apply-plan", onAssistantPlan as EventListener);
});
</script>

<template>
  <section class="home-layout">
    <div class="home-stream">
      <h1 class="page-title">{{ tx("AI 动态", "AI updates") }}</h1>
      <p class="page-subtitle">{{ tx("从事件流开始，再回查来源与证据。", "Follow events. Explore their sources and evidence.") }}</p>
      <div class="filter-strip">
        <label class="search-field"
          >{{ tx("关键词", "Keyword") }}<input
            v-model="q"
            class="control"
            :placeholder='tx("标题、摘要、实体", "Title, summary, entity")'
        /></label>
        <button
          v-if="compact && !['/', '/timeline-preview'].includes(route.path)"
          class="mobile"
          :aria-expanded="advanced"
          aria-controls="advanced"
          @click="advanced = !advanced"
        >
          {{ tx("分类与日期", "Category and date") }} {{ advanced ? "−" : "+" }}
        </button>
        <div id="advanced" v-show="!compact || advanced || ['/', '/timeline-preview'].includes(route.path)" class="filter-details">
          <fieldset class="category-list">
            <legend>{{ tx("分类", "Category") }}</legend>
            <label class="category-list__all"><input v-model="category" type="radio" value="" />{{ tx("全部", "All") }}</label>
            <label v-for="entry in categories" :key="entry.v"
              ><input v-model="category" type="radio" :value="entry.v" />{{
                entry.l
              }}</label
            >
          </fieldset>
          <div class="date-controls"><DateRangePicker :from="from" :to="to" :allow-unbounded="true" @change="applyDates" /></div>
        </div>
        <div v-if="hasFilters" class="filter-actions"><button class="filter-clear" @click="clear">{{ tx("清除条件", "Clear filters") }}</button></div>
      </div>
      <p v-if="invalid" class="status danger">
        {{ tx("日期范围无效：起始日期不能晚于截止日期。", "Invalid range: the start date must precede the end date.") }}
      </p>
      <p v-else class="meta" aria-live="polite">
        {{ loading ? tx("正在更新匹配结果…", "Updating results…") : tx(`精确匹配 ${total} 条事件`, `${total} matching events`) }}
      </p>
      <p v-if="(from || to) && !invalid" class="meta">{{ tx("日期范围只计入已核验的事件日期；未核验报道日期和冲突日期不计入。", "Date ranges include verified event dates only; unverified report dates and conflicts are excluded.") }}</p>
      <div v-if="loading" class="loading-state" aria-live="polite">
        {{ tx("正在读取事件流…", "Loading events…") }}
      </div>
      <div v-if="error" class="card error" role="alert">
        {{ error.message }}<button @click="load()">{{ tx("重试", "Retry") }}</button>
      </div>
      <div v-else-if="!loading && !items.length" class="empty">
        {{ tx("这个范围内没有事件。", "No events in this range.") }}
      </div>
      <div class="timeline-spine">
      <section
        v-for="year in timeline"
        :key="year.key"
        class="timeline-year"
        :class="{ 'timeline-year--unknown': year.unknown }"
      >
        <div class="timeline-year__heading">
          <h2 class="timeline-year__label">{{ year.label }}</h2>
          <span class="timeline-year__count"
            >{{ tx("已加载", "Loaded") }}
            {{
              year.months.reduce(
                (sum, month) =>
                  sum +
                  month.days.reduce(
                    (days, day) => days + day.events.length,
                    0,
                  ),
                0,
              )
            }}
            {{ tx("条", "events") }}</span
          >
        </div>
        <section
          v-for="month in year.months"
          :key="month.key"
          class="timeline-month"
        >
          <button
            class="timeline-month__toggle"
            data-testid="timeline-month-toggle"
            :data-key="month.key"
            :aria-expanded="timelineState[month.key]"
            @click="toggle(month.key)"
          >
            <svg class="timeline-fold-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="m6 4 4 4-4 4" /></svg><span>{{ month.label }}</span>
            <span class="timeline-month__count"
              >{{ tx("已加载", "Loaded") }}
              {{ month.days.reduce((sum, day) => sum + day.events.length, 0) }}
              {{ tx("条", "events") }}</span
            >
          </button>
          <div v-if="timelineState[month.key]">
            <section v-for="day in month.days" :key="day.key" class="timeline-day">
              <button class="timeline-day__toggle" data-testid="timeline-day-toggle" :aria-label="day.key" :aria-expanded="timelineState[day.key]" :aria-controls="'day-'+day.key" @click="toggle(day.key)">
                <svg class="timeline-fold-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="m6 4 4 4-4 4" /></svg><span>{{ day.label }}</span>
                <span class="timeline-day__loaded">{{ tx("已加载", "Loaded") }} {{ day.events.length }} {{ tx("条", "events") }}</span>
              </button>
              <div v-if="timelineState[day.key]" :id="'day-'+day.key">
              <article v-for="item in day.events" :key="item.id" class="timeline-event" :class="{ 'timeline-event--important': item.importance >= 4 }">
                <span class="pill">{{ categories.find((entry) => entry.v === item.category)?.l }}</span>
                <h2 class="timeline-event__title">
                  <a :href="directEventHref(item.id)" @click="openEvent($event, item.id)">{{ item.title_zh }}</a>
                </h2>
                <p class="muted timeline-event__summary">{{ item.summary_zh }}</p>
                <p class="meta tabular timeline-event__meta">
                  {{ tx("重要度", "Importance") }} {{ item.importance }}/5 · {{ item.source_count }} {{ tx("个来源", "sources") }} · {{ item.evidence_count }} {{ tx("条关联证据", "evidence excerpts") }}
                </p>
                <p v-if="item.date_conflict || item.date_basis === 'report_date_unverified'" class="meta">{{ item.date_conflict ? tx('日期有冲突 · 待核验', 'Conflicting dates · pending review') : tx('按报道日期展示 · 待核验事件日期', 'Shown by report date · event date unverified') }}</p>
                <p v-if="item.entities.length" class="timeline-event__entities">
                  <span v-for="entity in item.entities" :key="entity" class="pill">{{ entity }}</span>
                </p>
              </article>
              </div>
            </section>
          </div>
        </section>
      </section>
      </div>
      <button v-if="next && !loading" @click="load(next, true)">
        {{ tx("加载更多", "Load more") }}
      </button>
    </div>
    <aside class="context-panel">
      <h2>{{ tx("全库范围", "Entire collection") }}</h2>
      <p v-if="overview" class="tabular">
        {{ overview.scope === "global" ? tx("全库", "All") : overview.scope }} ·
        {{ overview.total_events }} {{ tx("条事件", "events") }}
      </p>
      <div v-if="overview" class="meta">
        <p>{{ tx("更新时间：", "Updated: ") }}{{ formatDate(overview.as_of) }}</p>
        <ul>
          <li v-for="(count, name) in overview.categories" :key="name">
            {{ categories.find((entry) => entry.v === name)?.l || name }}
            {{ count }}
          </li>
        </ul>
      </div>
      <p v-else class="meta">
        {{ statsError ? tx("全库态势暂时无法读取", "Collection overview unavailable") : tx("正在读取全库态势…", "Loading overview…") }}
      </p>
    </aside>
  </section>
  <EventDrawers />
</template>
