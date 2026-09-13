<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useRoute, useRouter, type LocationQueryRaw } from "vue-router";
import {
  dataMode,
  err,
  events,
  type Article,
  type Category,
  type Event,
  type Evidence,
} from "./api";

type SourceChoice = {
  key: string;
  title: string;
  sourceUrl: string;
  language?: string;
  evidence: Evidence[];
};

const route = useRoute();
const router = useRouter();
const item = ref<Event>();
const evidence = ref<Evidence[]>([]);
const loading = ref(false);
const error = ref<ReturnType<typeof err>>();
const evidenceError = ref<ReturnType<typeof err>>();
const eventDialog = ref<HTMLDialogElement>();
const sourceDialog = ref<HTMLDialogElement>();
const evidenceDialog = ref<HTMLDialogElement>();
let generation = 0;
let controller: AbortController | undefined;
let savedScroll = 0;
let locked = false;
let priorBodyStyles:
  | { position: string; top: string; width: string }
  | undefined;
let eventOpener: HTMLElement | undefined;
let sourceOpener: HTMLElement | undefined;
let evidenceOpener: HTMLElement | undefined;

const queryString = (name: "event" | "source" | "evidence") => {
  const value = route.query[name];
  return typeof value === "string" ? value : undefined;
};
const eventId = computed(() => queryString("event"));
const sourceKey = computed(() => queryString("source"));
const evidenceId = computed(() => queryString("evidence"));
const eventLayer = computed(() =>
  Boolean(eventId.value || sourceKey.value || evidenceId.value),
);
const safeUrl = (url: string) => /^https?:\/\//i.test(url);
const categoryLabels: Record<Category, string> = {
  model_release: "模型发布",
  agent_tool: "智能体工具",
  framework_sdk: "框架与 SDK",
  research: "研究",
  product: "产品",
  industry: "产业",
};
const verificationLabel = (status: string) =>
  status === "synthetic_verified" ? "合成回归：已核对" : status || "未提供";
const eventDetailHref = computed(() =>
  eventId.value
    ? router.resolve({
        path: `/events/${eventId.value}`,
        query: route.query.demo === "1" ? { demo: "1" } : {},
      }).href
    : "/",
);

const sources = computed<SourceChoice[]>(() => {
  const rows: SourceChoice[] = [];
  const byKey = new Map<string, SourceChoice>();
  for (const row of evidence.value) {
    const key = row.article_version_id
      ? row.article_version_id
      : row.source_url
        ? `url:${row.source_url}`
        : `evidence:${row.id}`;
    const existing = byKey.get(key);
    if (existing) existing.evidence.push(row);
    else {
      const source = {
        key,
        title: row.title || "未提供来源标题",
        sourceUrl: row.source_url,
        evidence: [row],
      };
      byKey.set(key, source);
      rows.push(source);
    }
  }
  for (const [index, article] of (item.value?.articles || []).entries()) {
    const source = article as Article;
    const existing = rows.find(
      (row) => source.source_url !== "" && row.sourceUrl === source.source_url,
    );
    if (!existing) {
      rows.push({
        key: `article:${index}`,
        title: source.title || "未提供来源标题",
        sourceUrl: source.source_url,
        language: source.language,
        evidence: [],
      });
    }
  }
  return rows;
});
const selectedSource = computed(() =>
  sources.value.find((source) => source.key === sourceKey.value),
);
const selectedEvidence = computed(() =>
  selectedSource.value?.evidence.find((row) => row.id === evidenceId.value),
);

function baseQuery(): LocationQueryRaw {
  const query: LocationQueryRaw = { ...route.query };
  delete query.event;
  delete query.source;
  delete query.evidence;
  return query;
}
function parentQuery(): LocationQueryRaw {
  const query = baseQuery();
  if (evidenceId.value) {
    if (eventId.value) query.event = eventId.value;
    if (sourceKey.value) query.source = sourceKey.value;
  } else if (sourceKey.value) {
    if (eventId.value) query.event = eventId.value;
  }
  return query;
}
function moveToParent() {
  const query = parentQuery();
  const target = router.resolve({ path: "/", query }).fullPath;
  if ((history.state as { back?: string } | null)?.back === target)
    router.back();
  else void router.replace({ path: "/", query });
}
function closeAll() {
  void router.replace({ path: "/", query: baseQuery() });
}
function rememberFocus(level: "source" | "evidence") {
  const active = document.activeElement;
  if (active instanceof HTMLElement) {
    if (level === "source") sourceOpener = active;
    else evidenceOpener = active;
  }
}
function openSource(source: SourceChoice) {
  rememberFocus("source");
  void router.push({
    path: "/",
    query: { ...baseQuery(), event: eventId.value, source: source.key },
  });
}
function openEvidence(row: Evidence) {
  rememberFocus("evidence");
  void router.push({
    path: "/",
    query: {
      ...baseQuery(),
      event: eventId.value,
      source: sourceKey.value,
      evidence: row.id,
    },
  });
}
function handleEscape(event: KeyboardEvent) {
  if (event.key !== "Escape" || !eventLayer.value) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  moveToParent();
}
function syncDialog(dialog: HTMLDialogElement | undefined, open: boolean) {
  if (!dialog) return;
  if (open && !dialog.open) {
    try {
      dialog.showModal();
    } catch {
      // A dialog can already be closing during a browser history transition.
    }
  }
  if (!open && dialog.open) dialog.close();
}
function syncDialogs() {
  void nextTick(() => {
    syncDialog(eventDialog.value, eventLayer.value);
    syncDialog(sourceDialog.value, Boolean(sourceKey.value));
    syncDialog(evidenceDialog.value, Boolean(evidenceId.value));
  });
}
function lockScroll() {
  if (locked) return;
  savedScroll = window.scrollY;
  priorBodyStyles = {
    position: document.body.style.position,
    top: document.body.style.top,
    width: document.body.style.width,
  };
  document.body.style.position = "fixed";
  document.body.style.top = `-${savedScroll}px`;
  document.body.style.width = "100%";
  locked = true;
}
function unlockScroll() {
  if (!locked) return;
  document.body.style.position = priorBodyStyles?.position || "";
  document.body.style.top = priorBodyStyles?.top || "";
  document.body.style.width = priorBodyStyles?.width || "";
  priorBodyStyles = undefined;
  window.scrollTo(0, savedScroll);
  locked = false;
}
async function loadEvent() {
  const id = eventId.value;
  const current = ++generation;
  controller?.abort();
  controller = undefined;
  item.value = undefined;
  evidence.value = [];
  error.value = undefined;
  evidenceError.value = undefined;
  if (!id) return;
  controller = new AbortController();
  loading.value = true;
  try {
    const value = await events.one(id, controller.signal);
    if (current !== generation) return;
    if (!value)
      throw { code: "NOT_FOUND", message: "未找到该事件", status: 404 };
    item.value = value;
    try {
      const evidenceRows = await events.evidence(id, controller.signal);
      if (current === generation) evidence.value = evidenceRows;
    } catch (cause) {
      if (current === generation && (cause as Error).name !== "AbortError")
        evidenceError.value = err(cause);
    }
  } catch (cause) {
    if (current === generation && (cause as Error).name !== "AbortError")
      error.value = err(cause);
  } finally {
    if (current === generation) loading.value = false;
  }
}

watch(eventId, loadEvent, { immediate: true });
watch([eventLayer, sourceKey, evidenceId], syncDialogs, { immediate: true });
watch(
  eventLayer,
  async (next, previous) => {
    if (next && !previous) {
      const active = document.activeElement;
      if (active instanceof HTMLElement) eventOpener = active;
      lockScroll();
    }
    if (!next && previous) {
      unlockScroll();
      await nextTick();
      eventOpener?.focus();
    }
  },
  { immediate: true },
);
watch(sourceKey, async (next, previous) => {
  if (!next && previous && !evidenceId.value) {
    await nextTick();
    sourceOpener?.focus();
  }
});
watch(evidenceId, async (next, previous) => {
  if (!next && previous) {
    await nextTick();
    evidenceOpener?.focus();
  }
});
onBeforeUnmount(() => {
  generation++;
  controller?.abort();
  unlockScroll();
});
</script>

<template>
  <Teleport to="body">
    <dialog
      ref="eventDialog"
      class="drawer-surface drawer-surface--event"
      data-testid="drawer-event"
      aria-labelledby="drawer-event-title"
      @cancel.prevent="moveToParent"
    >
      <div class="drawer-shell">
        <div class="drawer-header">
          <h2 id="drawer-event-title">事件 · 当前层</h2>
          <button
            data-testid="drawer-close"
            aria-label="关闭事件抽屉"
            @click="moveToParent"
          >
            关闭
          </button>
        </div>
        <div class="drawer-body">
          <p v-if="dataMode === 'fixture'" class="drawer-fixture">
            后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。
          </p>
          <p v-if="loading" class="drawer-status" aria-live="polite">
            正在读取事件与关联证据…
          </p>
          <div v-else-if="error" class="drawer-error" role="alert">
            <p>{{ error.status === 404 ? "未找到该事件。" : error.message }}</p>
            <button @click="loadEvent">重试</button>
          </div>
          <template v-else-if="item">
            <h3 class="drawer-event-title">{{ item.title_zh }}</h3>
            <p class="muted">{{ item.summary_zh }}</p>
            <p class="drawer-event-facts">
              <span class="pill">{{ categoryLabels[item.category] }}</span>
              <span class="meta tabular">重要度 {{ item.importance }}/5</span>
            </p>
            <p v-if="item.entities.length" class="drawer-entities">
              <span
                v-for="entity in item.entities"
                :key="entity"
                class="pill"
                >{{ entity }}</span
              >
            </p>
            <p class="drawer-full-page">
              <a :href="eventDetailHref">打开完整事件页</a>
            </p>
            <p class="meta tabular">
              {{ item.event_date || "日期未知" }} ·
              {{ item.source_count }} 个来源 ·
              {{ item.evidence_count }} 条关联证据
            </p>
            <h3>来源</h3>
            <p v-if="evidenceError" class="drawer-error" role="alert">
              证据暂时无法读取：{{ evidenceError.message }}
              <button @click="loadEvent">重试</button>
            </p>
            <p v-else-if="!sources.length" class="drawer-status">
              此事件没有可打开的来源或关联证据。
            </p>
            <div
              v-for="source in sources"
              :key="source.key"
              class="drawer-source"
            >
              <p class="drawer-source__name">{{ source.title }}</p>
              <p class="meta">
                {{
                  source.evidence.length
                    ? `${source.evidence.length} 条已保存证据`
                    : "未提供关联证据"
                }}
              </p>
              <button data-testid="source-open" @click="openSource(source)">
                查看来源
              </button>
            </div>
          </template>
          <div v-else class="drawer-error" role="alert">
            <p>缺少事件标识，无法打开来源层。</p>
            <button data-testid="drawer-back" @click="moveToParent">
              返回
            </button>
          </div>
          <button v-if="eventLayer" class="drawer-return" @click="closeAll">
            返回时间线
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      ref="sourceDialog"
      class="drawer-surface drawer-surface--source"
      data-testid="drawer-source"
      aria-labelledby="drawer-source-title"
      @cancel.prevent="moveToParent"
    >
      <div class="drawer-shell">
        <div class="drawer-header">
          <button
            data-testid="drawer-back"
            aria-label="返回事件"
            @click="moveToParent"
          >
            返回
          </button>
          <h2 id="drawer-source-title">事件 › 来源 · 当前层</h2>
          <button
            data-testid="drawer-close"
            aria-label="关闭来源抽屉"
            @click="moveToParent"
          >
            关闭
          </button>
        </div>
        <div class="drawer-body">
          <p v-if="dataMode === 'fixture'" class="drawer-fixture">
            后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。
          </p>
          <div v-if="!item && !loading" class="drawer-error" role="alert">
            无法定位此来源所属的事件。<button @click="moveToParent">
              返回
            </button>
          </div>
          <div
            v-else-if="item && !selectedSource"
            class="drawer-error"
            role="alert"
          >
            未找到指定来源；它可能不属于这个事件或链接已失效。<button
              @click="moveToParent"
            >
              返回事件
            </button>
          </div>
          <template v-else-if="selectedSource">
            <h3>{{ selectedSource.title }}</h3>
            <p v-if="selectedSource.language" class="meta">
              语言：{{ selectedSource.language }}
            </p>
            <p v-if="safeUrl(selectedSource.sourceUrl)">
              <a :href="selectedSource.sourceUrl" target="_blank" rel="noopener"
                >打开原始来源</a
              >
            </p>
            <p v-else class="drawer-status">该来源未提供可安全打开的链接。</p>
            <h3>关联证据</h3>
            <p v-if="!selectedSource.evidence.length" class="drawer-status">
              该来源没有已保存的段落证据。
            </p>
            <div
              v-for="row in selectedSource.evidence"
              :key="row.id"
              class="drawer-evidence"
            >
              <p>{{ row.title }}</p>
              <p class="meta">
                版本 {{ row.article_version_id }} · 段落 {{ row.paragraph_id }}
              </p>
              <button data-testid="evidence-open" @click="openEvidence(row)">
                查看证据
              </button>
            </div>
          </template>
          <p v-else class="drawer-status">正在读取来源…</p>
        </div>
      </div>
    </dialog>

    <dialog
      ref="evidenceDialog"
      class="drawer-surface drawer-surface--evidence"
      data-testid="drawer-evidence"
      aria-labelledby="drawer-evidence-title"
      @cancel.prevent="moveToParent"
    >
      <div class="drawer-shell">
        <div class="drawer-header">
          <button
            data-testid="drawer-back"
            aria-label="返回来源"
            @click="moveToParent"
          >
            返回
          </button>
          <h2 id="drawer-evidence-title">事件 › 来源 › 证据 · 当前层</h2>
          <button
            data-testid="drawer-close"
            aria-label="关闭证据抽屉"
            @click="moveToParent"
          >
            关闭
          </button>
        </div>
        <div class="drawer-body">
          <p v-if="dataMode === 'fixture'" class="drawer-fixture">
            后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。
          </p>
          <div v-if="!item && !loading" class="drawer-error" role="alert">
            无法定位此证据所属的事件。<button @click="moveToParent">
              返回
            </button>
          </div>
          <div
            v-else-if="item && !selectedSource"
            class="drawer-error"
            role="alert"
          >
            未找到指定来源，无法核对该证据。<button @click="moveToParent">
              返回
            </button>
          </div>
          <div
            v-else-if="selectedSource && !selectedEvidence"
            class="drawer-error"
            role="alert"
          >
            未找到指定证据；它可能不属于这个来源或链接已失效。<button
              @click="moveToParent"
            >
              返回来源
            </button>
          </div>
          <template v-else-if="selectedEvidence">
            <h3>{{ selectedEvidence.title }}</h3>
            <blockquote class="drawer-quote">
              {{ selectedEvidence.quote_text }}
            </blockquote>
            <p class="meta">
              不可变版本：{{ selectedEvidence.article_version_id }}
            </p>
            <p class="meta">段落：{{ selectedEvidence.paragraph_id }}</p>
            <p class="meta">
              核验状态：{{
                verificationLabel(selectedEvidence.verification_status)
              }}
            </p>
            <p v-if="safeUrl(selectedEvidence.source_url)">
              <a
                :href="selectedEvidence.source_url"
                target="_blank"
                rel="noopener"
                >打开原始来源</a
              >
            </p>
            <p v-else class="drawer-status">
              该证据未提供可安全打开的来源链接。
            </p>
          </template>
          <p v-else class="drawer-status">正在读取证据…</p>
        </div>
      </div>
    </dialog>
  </Teleport>
</template>
