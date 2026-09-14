<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { dataMode, err, events, type Category, type Event, type Evidence } from "../api";

const props = defineProps<{ eventId?: string }>();
const route = useRoute(); const router = useRouter();
const item = ref<Event>(); const evidence = ref<Evidence[]>([]); const loading = ref(false); const error = ref<ReturnType<typeof err>>();
let controller: AbortController | undefined; let generation = 0; let opener: HTMLElement | undefined; let scrollY = 0;
const labels: Record<Category, string> = { model_release: "模型发布", agent_tool: "智能体工具", framework_sdk: "框架与 SDK", research: "研究", product: "产品", industry: "产业" };
const safeUrl = (url: string) => /^https?:\/\//i.test(url);
const verification = (value: string) => value === "synthetic_verified" ? "合成回归：已核对" : value || "未提供";
function close() { const query = { ...route.query }; delete query.event; void router.replace({ path: "/preview", query }); }
function esc(event: KeyboardEvent) { if (event.key === "Escape" && props.eventId) { event.preventDefault(); close(); } }
async function load() {
  const id = props.eventId; const current = ++generation; controller?.abort(); item.value = undefined; evidence.value = []; error.value = undefined;
  if (!id) return; controller = new AbortController(); loading.value = true;
  try { const event = await events.one(id, controller.signal); if (!current || current !== generation) return; if (!event) throw { code: "NOT_FOUND", message: "未找到该事件", status: 404 }; item.value = event; evidence.value = await events.evidence(id, controller.signal); }
  catch (cause) { if (current === generation && (cause as Error).name !== "AbortError") error.value = err(cause); }
  finally { if (current === generation) loading.value = false; }
}
watch(() => props.eventId, async (value, previous) => {
  if (value && !previous) { const active = document.activeElement; if (active instanceof HTMLElement) opener = active; scrollY = window.scrollY; document.body.style.overflow = "hidden"; }
  if (!value && previous) { document.body.style.overflow = ""; await nextTick(); opener?.focus(); window.scrollTo(0, scrollY); }
  void load();
}, { immediate: true });
watch(() => props.eventId, () => { if (props.eventId) void nextTick(() => document.querySelector<HTMLElement>("[data-testid=preview-close]")?.focus()); });
window.addEventListener("keydown", esc);
onBeforeUnmount(() => { controller?.abort(); document.body.style.overflow = ""; window.removeEventListener("keydown", esc); });
</script>

<template>
  <Teleport to="body">
    <dialog v-if="eventId" open class="preview-reader" data-testid="preview-reader" aria-modal="true" aria-labelledby="preview-reader-title" @cancel.prevent="close">
      <header><p>事件阅读</p><button data-testid="preview-close" aria-label="关闭事件阅读" @click="close">关闭</button></header>
      <div class="preview-reader-body">
        <p v-if="dataMode === 'fixture'" class="preview-fixture">后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。</p>
        <p v-if="loading" class="preview-state" aria-live="polite">正在读取事件与保存的证据…</p>
        <div v-else-if="error" class="preview-error" role="alert">{{ error.status === 404 ? "未找到该事件。" : error.message }} <button @click="load">重试</button></div>
        <template v-else-if="item">
          <h2 id="preview-reader-title">{{ item.title_zh }}</h2>
          <p class="preview-reader-facts"><span class="preview-chip">{{ labels[item.category] }}</span><span>{{ item.event_date || "日期未知" }}</span><span>重要度 {{ item.importance }}/5</span></p>
          <p class="preview-reader-summary">{{ item.summary_zh }}</p>
          <p v-if="item.entities.length" class="preview-entities"><span v-for="entity in item.entities" :key="entity" class="preview-chip">{{ entity }}</span></p>
          <section class="preview-evidence"><h3>已保存证据</h3><p v-if="!evidence.length" class="preview-state">这个事件尚未保存可核对的段落证据。</p><div v-if="!evidence.length && item.articles?.length" class="preview-unsaved-sources"><article v-for="(source, index) in item.articles" :key="index"><h4>{{ source.title || "未提供来源标题" }}</h4><a v-if="safeUrl(source.source_url)" :href="source.source_url" target="_blank" rel="noopener">打开来源</a><p v-else class="preview-meta">未提供可安全打开的来源链接。</p><p class="preview-meta">该来源未保存段落证据。</p></article></div>
            <article v-for="row in evidence" :key="row.id" class="preview-evidence-row">
              <h4>{{ row.title || "未提供来源标题" }}</h4>
              <a v-if="safeUrl(row.source_url)" :href="row.source_url" target="_blank" rel="noopener">打开来源</a><p v-else class="preview-meta">未提供可安全打开的来源链接。</p>
              <blockquote>{{ row.quote_text || "未保存段落摘录。" }}</blockquote>
              <details data-testid="preview-source-info"><summary>来源信息</summary><p>版本 ID：{{ row.article_version_id || "未提供" }}</p><p>段落 ID：{{ row.paragraph_id || "未提供" }}</p><p>核验状态：{{ verification(row.verification_status) }}</p></details>
            </article>
          </section>
          <p class="preview-full"><RouterLink :to="{ path: `/events/${item.id}`, query: route.query.demo === '1' ? { demo: '1' } : {} }">打开完整事件页</RouterLink></p>
        </template>
      </div>
    </dialog>
  </Teleport>
</template>
