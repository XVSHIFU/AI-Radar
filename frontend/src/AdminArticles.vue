<script setup lang="ts">
import { onMounted, ref } from "vue";
import { admin, err, type AdminArticle } from "./api";
import { formatDate, translate as tr } from "./locale";

const props = defineProps<{ csrf: string }>();
const emit = defineEmits<{ unauthorized: [] }>();
const status = ref<"published" | "hidden">("published");
const rows = ref<AdminArticle[]>([]);
const total = ref(0);
const loading = ref(false);
const error = ref("");
const actionId = ref("");
const notice = ref("");
const formatTime = (value: string | null) => value ? formatDate(value, { dateStyle: "short", timeStyle: "short" }) : tr("未知", "Unknown");
const safeUrl = (value: string | null) => value && /^https?:\/\//i.test(value) ? value : null;

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const result = await admin.articles(status.value);
    rows.value = result.items;
    total.value = result.total;
  } catch (cause) {
    const problem = err(cause);
    if (problem.status === 401) emit("unauthorized");
    else error.value = problem.message;
  } finally { loading.value = false; }
}
async function change(row: AdminArticle) {
  if (actionId.value) return;
  actionId.value = row.id;
  notice.value = "";
  error.value = "";
  try {
    const next = row.status === "published" ? "hidden" : "published";
    await admin.setArticleStatus(props.csrf, row.id, next);
    notice.value = next === "hidden" ? tr("文章已隐藏。", "Article hidden.") : tr("文章已恢复。", "Article restored.");
    await load();
  } catch (cause) {
    const problem = err(cause);
    if (problem.status === 401) emit("unauthorized");
    else error.value = problem.message;
  } finally { actionId.value = ""; }
}
function select(next: "published" | "hidden") { status.value = next; void load(); }
onMounted(() => void load());
</script>

<template>
  <details class="card admin-articles" open>
    <summary class="admin-articles__summary"><div><h2>{{ tr("最近收录", "Recent articles") }}</h2><p class="meta">{{ tr("可隐藏无关文章，也可在“已隐藏”中恢复。", "Hide irrelevant articles or restore them from Hidden.") }}</p></div></summary>
    <div class="admin-articles__content">
    <button type="button" class="admin-action" :disabled="loading || !!actionId" @click="load">{{ tr("刷新", "Refresh") }}</button>
    <div class="admin-articles__tabs" role="group" :aria-label="tr('文章状态', 'Article status')">
      <button type="button" :aria-pressed="status === 'published'" @click="select('published')">{{ tr("已收录", "Published") }}</button>
      <button type="button" :aria-pressed="status === 'hidden'" @click="select('hidden')">{{ tr("已隐藏", "Hidden") }}</button>
    </div>
    <p v-if="notice" class="meta" role="status">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button type="button" @click="load">{{ tr("重试", "Retry") }}</button></p>
    <p v-else-if="loading" class="meta" aria-live="polite">{{ tr("正在读取文章…", "Loading articles…") }}</p>
    <p v-else-if="!rows.length" class="meta">{{ status === "published" ? tr("暂无收录文章。", "No published articles yet.") : tr("暂无隐藏文章。", "No hidden articles.") }}</p>
    <template v-else>
      <p class="meta">{{ tr("共 {count} 篇，显示最近 50 篇。", "{count} articles; showing the latest 50.", { count: total }) }}</p>
      <article v-for="row in rows" :key="row.id" class="admin-articles__row">
        <div>
          <strong><a v-if="safeUrl(row.source_url)" :href="safeUrl(row.source_url)!" target="_blank" rel="noopener noreferrer">{{ row.title }}</a><span v-else>{{ row.title }}</span></strong>
          <p class="meta">{{ row.source_name || tr("来源未提供", "Source unavailable") }} · {{ tr("发表", "Published") }} {{ formatTime(row.published_at) }} · {{ tr("收录", "Collected") }} {{ formatTime(row.ingested_at) }}</p>
        </div>
        <button type="button" class="admin-action" :disabled="!!actionId" @click="change(row)">{{ actionId === row.id ? tr("保存中…", "Saving…") : row.status === "published" ? tr("隐藏", "Hide") : tr("恢复", "Restore") }}</button>
      </article>
    </template>
    </div>
  </details>
</template>

<style scoped>
.admin-articles__summary { display:flex; align-items:start; justify-content:space-between; gap:16px; cursor:pointer; list-style:none; }
.admin-articles__summary::-webkit-details-marker { display:none; }
.admin-articles__summary::after { content:""; flex:none; width:8px; height:8px; margin:7px 3px 0 0; border-right:2px solid var(--muted); border-bottom:2px solid var(--muted); transform:rotate(45deg); transition:transform .16s ease; }
.admin-articles[open] > .admin-articles__summary::after { transform:rotate(225deg); }
.admin-articles__summary h2 { margin:0; font-size:20px; }
.admin-articles__summary .meta { margin:4px 0 0; }
.admin-articles[open] > .admin-articles__summary { padding-bottom:var(--s3); border-bottom:1px solid var(--line); margin-bottom:var(--s3); }
.admin-articles__content > .admin-action { margin-bottom:var(--s3); }
.admin-articles__summary:focus-visible { outline:2px solid var(--blue); outline-offset:4px; border-radius:4px; }
@media (prefers-reduced-motion: reduce) { .admin-articles__summary::after { transition:none; } }

.admin-articles__tabs { display:flex; gap:8px; margin:16px 0 12px; }
.admin-articles__tabs button[aria-pressed="true"] { color:var(--blue); border-color:var(--blue); }
.admin-articles__row { display:flex; align-items:start; justify-content:space-between; gap:16px; padding:12px 0; border-top:1px solid var(--line); }
.admin-articles__row > div { min-width:0; }
.admin-articles__row strong, .admin-articles__row a { overflow-wrap:anywhere; }
.admin-articles__row p { margin:4px 0 0; }
@media (max-width:720px) { .admin-articles__row { display:grid; } .admin-articles__row button { min-height:44px; } }
</style>

