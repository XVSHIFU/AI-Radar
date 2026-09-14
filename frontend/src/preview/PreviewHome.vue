<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { events, err, type Category, type Event, type EventQuery } from "../api";
import { latestRequest } from "../latest";
import {
  buildTimeline,
  reconcileTimelineState,
  type TimelineState,
} from "../timeline";
import PreviewReader from "./PreviewReader.vue";
import "./preview.css";

const route = useRoute();
const router = useRouter();
const q = ref("");
const category = ref<Category | "">("");
const from = ref("");
const to = ref("");
const items = ref<Event[]>([]);
const total = ref(0);
const next = ref<string | null>(null);
const loading = ref(false);
const error = ref<ReturnType<typeof err>>();
const timer = ref<number>();
const latest = latestRequest();
const timelineState = ref<TimelineState>({});
const categories: { v: Category; l: string }[] = [
  { v: "model_release", l: "模型发布" },
  { v: "agent_tool", l: "智能体工具" },
  { v: "framework_sdk", l: "框架与 SDK" },
  { v: "research", l: "研究" },
  { v: "product", l: "产品" },
  { v: "industry", l: "产业" },
];
const timeline = computed(() => buildTimeline(items.value));
const invalid = computed(() => Boolean(from.value && to.value && from.value > to.value));
const hasFilters = computed(() => Boolean(q.value || category.value || from.value || to.value));
const eventId = computed(() =>
  typeof route.query.event === "string" ? route.query.event : undefined,
);
const categoryName = (value: Category) =>
  categories.find((entry) => entry.v === value)?.l || value;
const countRows = (days: { events: Event[] }[]) =>
  days.reduce((sum, day) => sum + day.events.length, 0);

function sync() {
  q.value = String(route.query.q || "");
  category.value = String(route.query.category || "") as Category | "";
  from.value = String(route.query.date_from || "");
  to.value = String(route.query.date_to || "");
}
function baseQuery(cursor?: string) {
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
    const response = await events.list(
      {
        q: q.value || undefined,
        category: category.value || undefined,
        date_from: from.value || undefined,
        date_to: to.value || undefined,
        limit: 10,
        cursor,
      } as EventQuery,
      request.signal,
    );
    if (!request.current()) return;
    const rows = response.items as Event[];
    items.value = append ? [...items.value, ...rows] : rows;
    total.value = response.total;
    next.value = response.next_cursor;
  } catch (cause) {
    if (request.current() && (cause as Error).name !== "AbortError") {
      error.value = err(cause);
    }
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
    loading.value = false;
    return;
  }
  timer.value = window.setTimeout(() => {
    void router.replace({ path: "/preview", query: baseQuery() });
    void load();
  }, 260);
}
function clear() {
  q.value = "";
  category.value = "";
  from.value = "";
  to.value = "";
  schedule();
}
function toggle(key: string) {
  timelineState.value = { ...timelineState.value, [key]: !timelineState.value[key] };
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
  ) return;
  event.preventDefault();
  void router.push({ path: "/preview", query: { ...baseQuery(), event: id } });
}
watch(() => route.query, sync, { immediate: true });
watch(timeline, (value) => {
  timelineState.value = reconcileTimelineState(timelineState.value, value);
});
watch([q, category, from, to], schedule);
onMounted(() => void load());
onBeforeUnmount(() => {
  latest.cancel();
  clearTimeout(timer.value);
});
</script>

<template>
  <section class="preview-page">
    <h1 class="preview-title">AI 动态</h1>
    <section class="preview-filters" aria-label="筛选事件">
      <div class="preview-filter-main">
        <label class="preview-search"><span class="sr-only">搜索事件</span>
          <input v-model="q" data-testid="preview-search" placeholder="搜索标题、摘要或实体" />
        </label>
        <fieldset class="preview-categories">
          <legend class="sr-only">分类</legend>
          <label><input v-model="category" type="radio" value="" data-testid="preview-category" data-category="" />全部</label>
          <label v-for="entry in categories" :key="entry.v"><input v-model="category" type="radio" :value="entry.v" data-testid="preview-category" :data-category="entry.v" />{{ entry.l }}</label>
        </fieldset>
      </div>
      <div class="preview-filter-meta">
        <details class="preview-dates" :open="Boolean(from || to)">
          <summary data-testid="preview-date-toggle">日期{{ from || to ? `：${from || "不限"} 至 ${to || "不限"}` : "" }}</summary>
          <div><label>从<input v-model="from" name="date_from" type="date" /></label><label>至<input v-model="to" name="date_to" type="date" /></label></div>
        </details>
        <p v-if="!invalid" class="preview-count" aria-live="polite">{{ loading ? "正在更新事件…" : `精确匹配 ${total} 条事件` }}</p>
        <button v-if="hasFilters" class="preview-clear" @click="clear">清除条件</button>
      </div>
    </section>
    <p v-if="invalid" class="preview-error" role="alert">日期范围无效：起始日期不能晚于截止日期。</p>
    <section class="preview-reading" aria-label="AI 事件时间线">
      <p v-if="loading" class="preview-state" aria-live="polite">正在读取事件流…</p>
      <div v-else-if="error" class="preview-error" role="alert">{{ error.message }} <button @click="load()">重试</button></div>
      <p v-else-if="!invalid && !items.length" class="preview-state">这个范围内没有事件。</p>
      <section v-for="year in timeline" :key="year.key" class="preview-year">
        <div class="preview-year-heading"><h2>{{ year.label }}</h2><small>已加载 {{ year.months.reduce((sum, month) => sum + countRows(month.days), 0) }} 条</small></div>
        <section v-for="month in year.months" :key="month.key" class="preview-later-month">
          <button class="timeline-month-toggle" data-testid="timeline-month-toggle" :data-key="month.key" :aria-expanded="timelineState[month.key]" @click="toggle(month.key)">{{ month.label }} <small>已加载 {{ countRows(month.days) }} 条</small></button>
          <div v-if="timelineState[month.key]">
            <section v-for="day in month.days" :key="day.key" class="preview-day">
              <p class="preview-day-heading"><span>{{ day.label }}</span><small>已加载 {{ day.events.length }} 条</small></p>
              <article v-for="item in day.events" :key="item.id" class="preview-event" data-testid="preview-event"><p><span class="preview-chip">{{ categoryName(item.category) }}</span></p><h2><a :href="directEventHref(item.id)" @click="openEvent($event, item.id)">{{ item.title_zh }}</a></h2><p class="preview-summary">{{ item.summary_zh }}</p><p v-if="item.entities.length" class="preview-entities"><span v-for="entity in item.entities" :key="entity" class="preview-chip">{{ entity }}</span></p></article>
            </section>
          </div>
        </section>
      </section>      <button v-if="next && !loading" data-testid="preview-load-more" class="preview-more" @click="load(next, true)">加载更多</button>
    </section>
    <PreviewReader :event-id="eventId" />
  </section>
</template>