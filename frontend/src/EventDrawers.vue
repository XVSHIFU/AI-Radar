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
  isDemo,
  type Article,
  type Category,
  type Event,
  type Evidence,
} from "./api";
import { preferredReadingUrl } from "./source-links";

type SourceChoice = {
  key: string;
  title: string;
  sourceUrl: string;
  language?: string;
  evidence: Evidence[];
};

const route = useRoute();
const router = useRouter();
const props = defineProps<{ basePath?: string }>();
const pagePath = computed(() => props.basePath || route.path);
const item = ref<Event>();
const evidence = ref<Evidence[]>([]);
const loading = ref(false);
const error = ref<ReturnType<typeof err>>();
const evidenceError = ref<ReturnType<typeof err>>();
const eventDialog = ref<HTMLDialogElement>();
const sourceDialog = ref<HTMLDialogElement>();
const evidenceDialog = ref<HTMLDialogElement>();
const shieldVisible = ref(false);
const outerClosing = ref(false);
let outerExitTimer: number | undefined;
const dialogTimers = new WeakMap<HTMLDialogElement, number>();
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
const eventInactive = computed(() =>
  Boolean(sourceKey.value || evidenceId.value),
);
const sourceInactive = computed(() => Boolean(evidenceId.value));
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
  const target = router.resolve({ path: pagePath.value, query }).fullPath;
  if ((history.state as { back?: string } | null)?.back === target)
    router.back();
  else void router.replace({ path: pagePath.value, query });
}
function attachToConversation(item: Event) { window.dispatchEvent(new CustomEvent("attach-event", { detail: { id: item.id, title: item.title_zh } })); if (matchMedia("(max-width: 900px)").matches) closeAll(); }
function closeAll() {
  void router.replace({ path: pagePath.value, query: baseQuery() });
}
function closeFromBackdrop(event: MouseEvent, layer: "event" | "source" | "evidence") {
  if (event.target !== event.currentTarget) return;
  const surface = event.currentTarget as HTMLDialogElement;
  const rect = surface.getBoundingClientRect();
  const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
  const top = layer === "evidence" ? Boolean(evidenceId.value) : layer === "source" ? Boolean(sourceKey.value && !evidenceId.value) : Boolean(eventLayer.value && !sourceKey.value && !evidenceId.value);
  if (outside && top) moveToParent();
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
    path: pagePath.value,
    query: { ...baseQuery(), event: eventId.value, source: source.key },
  });
}
function openEvidence(row: Evidence) {
  rememberFocus("evidence");
  void router.push({
    path: pagePath.value,
    query: {
      ...baseQuery(),
      event: eventId.value,
      source: sourceKey.value,
      evidence: row.id,
    },
  });
}

function syncDialog(dialog: HTMLDialogElement | undefined, open: boolean) {
  if (!dialog) return;
  const pending = dialogTimers.get(dialog);
  if (open) {
    if (pending) { clearTimeout(pending); dialogTimers.delete(dialog); }
    dialog.classList.remove("drawer-surface--leaving");
    if (!dialog.open) try { dialog.show(); } catch {}
    return;
  }
  if (!dialog.open || pending) return;
  dialog.classList.add("drawer-surface--leaving");
  dialogTimers.set(dialog, window.setTimeout(() => { dialog.close(); dialog.classList.remove("drawer-surface--leaving"); dialogTimers.delete(dialog); }, 260));
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
  if (!id) return;
  item.value = undefined;
  evidence.value = [];
  error.value = undefined;
  evidenceError.value = undefined;
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
      if (outerExitTimer) { clearTimeout(outerExitTimer); outerExitTimer = undefined; }
      shieldVisible.value = true;
      outerClosing.value = false;
      const active = document.activeElement;
      if (active instanceof HTMLElement) eventOpener = active;
      lockScroll();
      backgroundInert(true);
    }
    if (!next && previous) {
      outerClosing.value = true;
      outerExitTimer = window.setTimeout(async () => {
        shieldVisible.value = false;
        outerClosing.value = false;
        unlockScroll();
        backgroundInert(false);
        await nextTick();
        eventOpener?.focus();
        outerExitTimer = undefined;
      }, 260);
    }
  },
  { immediate: true },
);
watch(sourceKey, async (next, previous) => {
  if (!next && previous && !evidenceId.value) {
    window.setTimeout(() => { if(eventLayer.value && !sourceKey.value) sourceOpener?.focus(); }, 260);
  }
});
watch(evidenceId, async (next, previous) => {
  if (!next && previous) {
    window.setTimeout(() => { if(eventLayer.value && !evidenceId.value) evidenceOpener?.focus(); }, 260);
  }
});
const onEscape = (event: KeyboardEvent) => {
  if (event.key === "Tab" && eventLayer.value && matchMedia("(max-width:900px)").matches) {
    const dialog = evidenceId.value ? evidenceDialog.value : sourceKey.value ? sourceDialog.value : eventDialog.value;
    const nodes = [...(dialog?.querySelectorAll<HTMLElement>("button,a[href],summary,input,[tabindex='0']") || []), ...document.querySelectorAll<HTMLElement>("[data-testid='assistant-toggle']")].filter(n => n.getClientRects().length && !n.hasAttribute("disabled") && !n.closest("[inert]"));
    const first=nodes[0], last=nodes.at(-1);
    if(first && last && event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
    else if(first && last && !event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
  }


  if (event.key === "Escape" && eventLayer.value && !event.defaultPrevented) { event.preventDefault(); moveToParent(); }

};

function backgroundInert(drawerOpen: boolean) {
  const assistantModal = document.documentElement.classList.contains("global-assistant-open") && matchMedia("(max-width: 900px)").matches;
  for (const node of document.querySelectorAll(".app-content main,.app-rail")) node.toggleAttribute("inert", drawerOpen || assistantModal);
}
onMounted(() => { document.addEventListener("keydown", onEscape); if(eventLayer.value) { shieldVisible.value = true; backgroundInert(true); } });

onBeforeUnmount(() => {
  generation++;
  controller?.abort();
  if (outerExitTimer) clearTimeout(outerExitTimer);
  unlockScroll();

  document.removeEventListener("keydown", onEscape);

  backgroundInert(false);

});

</script>

<template>
  <Teleport to="body">
    <div v-if="shieldVisible" class="drawer-shield" :class="{ 'drawer-shield--leaving': outerClosing }" data-testid="drawer-shield" aria-hidden="true" @click.stop.prevent="moveToParent" @pointerdown.stop></div>
    <dialog
      ref="eventDialog"
      class="drawer-surface drawer-surface--event"
      :class="{
        'drawer-surface--inactive': eventInactive,
        'drawer-surface--active': !eventInactive,
      }"
      data-testid="drawer-event" :inert="eventInactive"
      aria-labelledby="drawer-event-title"
      @cancel.prevent="moveToParent" @click="closeFromBackdrop($event, 'event')"
    >
      <div class="drawer-shell">
        <div class="drawer-header">
          <button data-testid="drawer-back" aria-label="返回时间线" @click="closeAll"><svg class="drawer-back-icon" viewBox="0 0 18 18" aria-hidden="true"><path d="M11.5 3.5 6 9l5.5 5.5M6.5 9h7" /></svg>返回</button>
          <h2 id="drawer-event-title">事件</h2>
        </div>        <div class="drawer-body">
          <p v-if="isDemo()" class="drawer-fixture">前端模拟数据：仅用于界面展示，不代表真实新闻或采集结果。</p>
          <p v-else-if="dataMode === 'fixture'" class="drawer-fixture">后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。</p>
          <p v-if="loading" class="drawer-status" aria-live="polite">
            正在读取事件与关联证据…
          </p>
          <div v-else-if="error" class="drawer-error" role="alert">
            <p>{{ error.status === 404 ? "未找到该事件。" : error.message }}</p>
            <button @click="loadEvent">重试</button>
          </div>
          <template v-else-if="item">
            <h3 class="drawer-event-title">{{ item.title_zh }}</h3><button data-testid="attach-event" @click="attachToConversation(item)">加入当前对话</button>
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
            <p class="meta tabular">
              {{ item.event_date || "日期未知" }} ·
              {{ item.source_count }} 个来源 ·
              {{ item.evidence_count }} 条关联证据
            </p>
            <h3>来源与保存证据</h3>
            <p v-if="evidenceError" class="drawer-error" role="alert">
              证据暂时无法读取：{{ evidenceError.message }}
              <button @click="loadEvent">重试</button>
            </p>
            <p v-else-if="!sources.length" class="drawer-status">
              此事件没有可打开的来源或关联证据。
            </p>
            <section v-for="source in sources" :key="source.key" class="drawer-source">
              <h4 class="drawer-source__name">{{ source.title }}</h4>
              <p v-if="safeUrl(source.sourceUrl)" class="row"><a :href="preferredReadingUrl(source.sourceUrl)" target="_blank" rel="noopener">{{ preferredReadingUrl(source.sourceUrl) === source.sourceUrl ? "打开原始来源" : "打开中文页面" }}</a><a v-if="preferredReadingUrl(source.sourceUrl) !== source.sourceUrl" :href="source.sourceUrl" target="_blank" rel="noopener">查看采集原文（英文摘录核验）</a></p>
              <p v-else class="drawer-status">该来源未提供可安全打开的链接。</p>
              <p v-if="!source.evidence.length" class="drawer-status">该来源没有已保存的段落证据。</p>
              <section v-for="row in source.evidence" :key="row.id" class="drawer-evidence">
                <blockquote class="drawer-quote">{{ row.quote_text || "未保存段落摘录。" }}</blockquote>

              </section>
              <button data-testid="source-open" @click="openSource(source)">来源详情</button>
            </section>          </template>
          <div v-else class="drawer-error" role="alert">
            <p>缺少事件标识，无法打开来源层。</p>
            <button data-testid="drawer-back" @click="moveToParent">
              返回
            </button>
          </div>
        </div>
      </div>
    </dialog>

    <dialog
      ref="sourceDialog"
      class="drawer-surface drawer-surface--source"
      :class="{
        'drawer-surface--inactive': sourceInactive,
        'drawer-surface--active': !sourceInactive,
      }"
      data-testid="drawer-source" :inert="sourceInactive"
      aria-labelledby="drawer-source-title"
      @cancel.prevent="moveToParent" @click="closeFromBackdrop($event, 'source')"
    >
      <div class="drawer-shell">
        <div class="drawer-header">
          <button data-testid="drawer-back" aria-label="返回事件" @click="moveToParent"><svg class="drawer-back-icon" viewBox="0 0 18 18" aria-hidden="true"><path d="M11.5 3.5 6 9l5.5 5.5M6.5 9h7" /></svg>返回</button>
          <h2 id="drawer-source-title">来源</h2>
        </div>        <div class="drawer-body">
          <p v-if="isDemo()" class="drawer-fixture">前端模拟数据：仅用于界面展示，不代表真实新闻或采集结果。</p>
          <p v-else-if="dataMode === 'fixture'" class="drawer-fixture">后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。</p>
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
            <p v-if="safeUrl(selectedSource.sourceUrl)" class="row"><a :href="preferredReadingUrl(selectedSource.sourceUrl)" target="_blank" rel="noopener">{{ preferredReadingUrl(selectedSource.sourceUrl) === selectedSource.sourceUrl ? "打开原始来源" : "打开中文页面" }}</a><a v-if="preferredReadingUrl(selectedSource.sourceUrl) !== selectedSource.sourceUrl" :href="selectedSource.sourceUrl" target="_blank" rel="noopener">查看采集原文（英文摘录核验）</a></p>
            <p v-else class="drawer-status">该来源未提供可安全打开的链接。</p>
            <h3>保存版本与核验</h3>
            <p v-if="!selectedSource.evidence.length" class="drawer-status">该来源没有已保存的段落证据。</p>
            <section v-for="(row, index) in selectedSource.evidence" :key="row.id" class="drawer-evidence">
              <p class="drawer-source__name">引用段落 {{ index + 1 }}</p><p>不可变版本：{{ row.article_version_id || "未提供" }}</p><p>段落：{{ row.paragraph_id || "未提供" }}</p><p>核验状态：{{ verificationLabel(row.verification_status) }}</p>
            </section>          </template>
          <p v-else class="drawer-status">正在读取来源…</p>
        </div>
      </div>
    </dialog>

    <dialog
      ref="evidenceDialog"
      class="drawer-surface drawer-surface--evidence"
      :class="{ 'drawer-surface--active': Boolean(evidenceId) }"
      data-testid="drawer-evidence"
      aria-labelledby="drawer-evidence-title"
      @cancel.prevent="moveToParent" @click="closeFromBackdrop($event, 'evidence')"
    >
      <div class="drawer-shell">
        <div class="drawer-header">
          <button data-testid="drawer-back" aria-label="返回事件" @click="moveToParent"><svg class="drawer-back-icon" viewBox="0 0 18 18" aria-hidden="true"><path d="M11.5 3.5 6 9l5.5 5.5M6.5 9h7" /></svg>返回</button>
          <h2 id="drawer-evidence-title">证据</h2>
        </div>        <div class="drawer-body">
          <p v-if="isDemo()" class="drawer-fixture">前端模拟数据：仅用于界面展示，不代表真实新闻或采集结果。</p>
          <p v-else-if="dataMode === 'fixture'" class="drawer-fixture">后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。</p>
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
