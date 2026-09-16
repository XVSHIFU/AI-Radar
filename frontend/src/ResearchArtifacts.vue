<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { artifactsFrom, fetchArtifact, type ResearchArtifact } from "./research-artifacts";
import { translate as tr } from "./locale";
const props = defineProps<{ items: ResearchArtifact[] }>();
const emit = defineEmits<{ source: [index: number] }>();
const valid = computed(() => { try { return artifactsFrom(props.items); } catch { return []; } });
const now = ref(Date.now());
const previews = ref<Record<string, string>>({});
const pending = ref<Record<string, boolean>>({});
const errors = ref<Record<string, string>>({});
const controllers = new Map<string, AbortController>();
const expired = (item: ResearchArtifact) => now.value >= Date.parse(item.expires_at);
function discard(id: string) { if (previews.value[id]) URL.revokeObjectURL(previews.value[id]!); delete previews.value[id]; }
const timer = window.setInterval(() => {
  now.value = Date.now();
  for (const item of valid.value) if (expired(item)) { controllers.get(item.id)?.abort(); discard(item.id); }
}, 15000);
async function load(item: ResearchArtifact, download = false) {
  if (pending.value[item.id] || expired(item)) return;
  const controller = new AbortController(); controllers.set(item.id, controller);
  pending.value[item.id] = true; delete errors.value[item.id];
  try {
    const blob = await fetchArtifact(item, controller.signal);
    if (controller.signal.aborted) return;
    const url = URL.createObjectURL(blob);
    if (download) {
      const link = document.createElement("a"); link.href = url; link.download = item.name;
      link.click(); if(item.mime === "image/png") { discard(item.id); previews.value[item.id] = URL.createObjectURL(blob); } window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } else { discard(item.id); previews.value[item.id] = url; }
  } catch (cause) {
    if (!controller.signal.aborted) errors.value[item.id] = cause instanceof Error && cause.message === "expired" ? "expired" : "unavailable";
  } finally { pending.value[item.id] = false; controllers.delete(item.id); }
}
watch(valid, (items) => { for (const id of Object.keys(previews.value)) if(!items.some(item => item.id === id)) {controllers.get(id)?.abort();discard(id);} for (const item of items) if (item.mime === "image/png" && !previews.value[item.id]) void load(item); }, {immediate: true});
onBeforeUnmount(() => { clearInterval(timer); controllers.forEach(c => c.abort()); Object.keys(previews.value).forEach(discard); });
</script>

<template>
  <section v-if="valid.length" class="research-artifacts" :aria-label="tr('分析产物', 'Analysis files')">
    <figure v-for="item in valid" :key="item.id" class="research-artifact">
      <img v-if="previews[item.id]" :src="previews[item.id]" :alt="tr('分析图表：', 'Analysis chart: ') + item.name" />
      <figcaption>
        <div class="artifact-label"><strong>{{ item.name }}</strong><span class="meta">{{ (item.size_bytes / 1024).toFixed(1) }} KB</span></div>
        <button class="artifact-action" :aria-label="tr('查看分析依据', 'View analysis evidence')" @click="emit('source', item.citation_index)">[{{ item.citation_index }}] {{ tr('依据', 'Evidence') }}</button>
        <button v-if="!expired(item) && errors[item.id] !== 'expired'" class="artifact-action artifact-download" :disabled="pending[item.id]" :title="tr('下载文件', 'Download file')" :aria-label="tr('下载文件：', 'Download file: ') + item.name" @click="load(item, true)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M5 17v4h14v-4"/></svg></button>
        <span v-else class="meta">{{ tr('已过期', 'Expired') }}</span>
      </figcaption>
      <p v-if="pending[item.id]" class="meta" role="status">{{ tr('正在读取文件…', 'Loading file…') }}</p>
      <p v-else-if="errors[item.id]" class="meta" role="status">{{ errors[item.id] === 'expired' ? tr('文件已过期或当前会话无法访问。', 'This file has expired or is unavailable to this session.') : tr('文件暂时无法读取，可再次点击下载。', 'The file could not be loaded. Try the download again.') }}</p>
    </figure>
    <p class="meta artifact-lifetime">{{ tr('文件保留 15 分钟；请及时下载。', 'Files are available for 15 minutes. Download them to keep a copy.') }}</p>
  </section>
</template>

<style scoped>
.research-artifacts { min-width: 0; margin-block: 1rem; }
.research-artifact { margin: 0; padding-block: .75rem; border-block-start: 1px solid var(--line); }
.research-artifact img { display: block; max-width: 100%; height: auto; margin-block-end: .65rem; }
figcaption { display: flex; align-items: center; gap: .65rem; }
.artifact-label { display: flex; flex: 1; min-width: 0; flex-wrap: wrap; align-items: baseline; gap: .4rem; }
.artifact-label strong { font-size: .875rem; overflow-wrap: anywhere; }
.artifact-action { flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; min-height: 32px; padding: .2rem; border: 0; background: none; color: var(--accent); font: inherit; font-size: .875rem; cursor: pointer; }
.artifact-action:hover { text-decoration: underline; text-underline-offset: .2em; }
.artifact-action:disabled { opacity: .55; cursor: wait; }
.artifact-download { min-width: 32px; }
.artifact-download svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
.artifact-lifetime { margin-block-end: 0; }
</style>
