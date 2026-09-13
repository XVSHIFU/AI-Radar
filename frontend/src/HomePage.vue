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
import {
  buildTimeline,
  reconcileTimelineState,
  setTimelineGranularity,
  type TimelineState,
} from "./timeline";
import { latestRequest } from "./latest";
import "./home-timeline.css";

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
const categories: { v: Category; l: string }[] = [
  { v: "model_release", l: "模型发布" },
  { v: "agent_tool", l: "智能体工具" },
  { v: "framework_sdk", l: "框架与 SDK" },
  { v: "research", l: "研究" },
  { v: "product", l: "产品" },
  { v: "industry", l: "产业" },
];
const timeline = computed(() => buildTimeline(items.value));
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
  void router.push({ path: "/", query: { ...query(), event: id } });
}
watch(() => route.query, sync, { immediate: true });
watch(timeline, (value) => {
  timelineState.value = reconcileTimelineState(timelineState.value, value);
});
watch([q, category, from, to], schedule);
onMounted(async () => {
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
});
</script>

<template>
  <section class="home-layout">
    <div class="home-stream">
      <h1 class="page-title">AI 动态</h1>
      <p class="page-subtitle">从事件流开始，再回查来源与证据。</p>
      <div class="filter-strip">
        <label class="search-field"
          >关键词<input
            v-model="q"
            class="control"
            placeholder="标题、摘要、实体"
        /></label>
        <button
          v-if="compact"
          class="mobile"
          :aria-expanded="advanced"
          aria-controls="advanced"
          @click="advanced = !advanced"
        >
          分类与日期 {{ advanced ? "−" : "+" }}
        </button>
        <div id="advanced" v-show="!compact || advanced" class="filter-details">
          <fieldset class="category-list">
            <legend>分类</legend>
            <label v-for="entry in categories" :key="entry.v"
              ><input v-model="category" type="radio" :value="entry.v" />{{
                entry.l
              }}</label
            >
          </fieldset>
          <div class="date-controls">
            <label>从<input v-model="from" type="date" class="control" /></label
            ><label>至<input v-model="to" type="date" class="control" /></label>
          </div>
        </div>
        <div class="filter-actions"><button @click="clear">清除</button></div>
      </div>
      <p v-if="invalid" class="status danger">
        日期范围无效：起始日期不能晚于截止日期。
      </p>
      <p v-else class="meta" aria-live="polite">
        {{ loading ? "正在更新匹配结果…" : `精确匹配 ${total} 条事件` }}
      </p>
      <div v-if="loading" class="loading-state" aria-live="polite">
        正在读取事件流…
      </div>
      <div v-if="error" class="card error" role="alert">
        {{ error.message }}<button @click="load()">重试</button>
      </div>
      <div v-else-if="!loading && !items.length" class="empty">
        这个范围内没有事件。
      </div>
      <div v-else class="timeline-controls" aria-label="时间线展开控制">
        <button @click="setAll(true)">展开全部</button
        ><button @click="setAll(false)">折叠全部</button>
      </div>
      <section
        v-for="year in timeline"
        :key="year.key"
        class="timeline-year"
        :class="{ 'timeline-year--unknown': year.unknown }"
      >
        <button
          class="timeline-year__toggle"
          data-testid="timeline-year-toggle"
          :data-key="year.key"
          :aria-expanded="timelineState[year.key]"
          @click="toggle(year.key)"
        >
          {{ year.label }}
        </button>
        <div v-if="timelineState[year.key]">
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
              {{ month.label }}
            </button>
            <div v-if="timelineState[month.key]">
              <section
                v-for="day in month.days"
                :key="day.key"
                class="timeline-day"
              >
                <button
                  class="timeline-day__toggle"
                  data-testid="timeline-day-toggle"
                  :data-key="day.key"
                  :aria-expanded="timelineState[day.key]"
                  @click="toggle(day.key)"
                >
                  <span>{{ day.label }}</span
                  ><span class="timeline-day__loaded"
                    >已加载 {{ day.events.length }} 条</span
                  >
                </button>
                <div v-if="timelineState[day.key]">
                  <article
                    v-for="item in day.events"
                    :key="item.id"
                    class="timeline-event"
                  >
                    <span class="pill">{{
                      categories.find((entry) => entry.v === item.category)?.l
                    }}</span>
                    <h2 class="timeline-event__title">
                      <a
                        :href="directEventHref(item.id)"
                        @click="openEvent($event, item.id)"
                        >{{ item.title_zh }}</a
                      >
                    </h2>
                    <p class="muted">{{ item.summary_zh }}</p>
                    <p class="meta tabular timeline-event__meta">
                      重要度 {{ item.importance }}/5 ·
                      {{ item.source_count }} 个来源 ·
                      {{ item.evidence_count }} 条关联证据
                    </p>
                    <p
                      v-if="item.entities.length"
                      class="timeline-event__entities"
                    >
                      <span
                        v-for="entity in item.entities"
                        :key="entity"
                        class="pill"
                        >{{ entity }}</span
                      >
                    </p>
                  </article>
                </div>
              </section>
            </div>
          </section>
        </div>
      </section>
      <button v-if="next && !loading" @click="load(next, true)">
        加载更多
      </button>
    </div>
    <aside class="context-panel">
      <h2>全库范围</h2>
      <p v-if="overview" class="tabular">
        {{ overview.scope === "global" ? "全库" : overview.scope }} ·
        {{ overview.total_events }} 条事件
      </p>
      <div v-if="overview" class="meta">
        <p>更新时间：{{ new Date(overview.as_of).toLocaleString("zh-CN") }}</p>
        <ul>
          <li v-for="(count, name) in overview.categories" :key="name">
            {{ categories.find((entry) => entry.v === name)?.l || name }}
            {{ count }}
          </li>
        </ul>
      </div>
      <p v-else class="meta">
        {{ statsError ? "全库态势暂时无法读取" : "正在读取全库态势…" }}
      </p>
    </aside>
  </section>
  <EventDrawers />
</template>
