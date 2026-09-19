<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { err, type ApiError, type Category } from "./api";
import { adminError } from "./admin-locale";
import { translate as tr } from "./locale";
import { contentApi, type ContentArticle, type ContentBatch, type ContentDraft, type ContentSettings, type ContentTask, type DraftContent, type ImportItem } from "./content-api";
import "./content-workbench.css";

const props = defineProps<{ csrf: string }>();
const emit = defineEmits<{ unauthorized: [] }>();
const categories: Array<{ code: Category; zh: string; en: string }> = [
  { code: "model_release", zh: "模型发布", en: "Model release" },
  { code: "agent_tool", zh: "Agent 工具", en: "Agent tool" },
  { code: "framework_sdk", zh: "框架 / SDK", en: "Framework / SDK" },
  { code: "research", zh: "研究", en: "Research" },
  { code: "product", zh: "产品", en: "Product" },
  { code: "industry", zh: "产业", en: "Industry" },
];
function normalizeContent(value: ContentDraft["content"]): DraftContent {
  const raw = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const entities = Array.isArray(raw.entities) ? raw.entities.filter((item): item is Record<string, unknown> => !!item && typeof item === "object") : [];
  const evidence = Array.isArray(raw.evidence) ? raw.evidence.filter((item): item is Record<string, unknown> => !!item && typeof item === "object") : [];
  const category = categories.some(item => item.code === raw.category) ? raw.category as Category : null;
  return {
    relevant: typeof raw.relevant === "boolean" ? raw.relevant : true,
    title_zh: typeof raw.title_zh === "string" ? raw.title_zh : "",
    summary_zh: typeof raw.summary_zh === "string" ? raw.summary_zh : "",
    category,
    importance: typeof raw.importance === "number" && Number.isFinite(raw.importance) ? raw.importance : null,
    event_date: typeof raw.event_date === "string" ? raw.event_date : null,
    date_precision: raw.date_precision === "day" || raw.date_precision === "month" ? raw.date_precision : "unknown",
    date_basis: raw.date_basis === "explicit_body" || raw.date_basis === "official_publication" ? raw.date_basis : "unknown",
    date_evidence_paragraph_id: typeof raw.date_evidence_paragraph_id === "string" ? raw.date_evidence_paragraph_id : null,
    entities: entities.map(item => ({
      canonical_name: typeof item.canonical_name === "string" ? item.canonical_name : "",
      entity_type: typeof item.entity_type === "string" ? item.entity_type : "organization",
      role: item.role === "subject" || item.role === "product" ? item.role : "mention",
    })),
    evidence: evidence.map(item => ({
      paragraph_id: typeof item.paragraph_id === "string" ? item.paragraph_id : "",
      quote_text: typeof item.quote_text === "string" ? item.quote_text : "",
      claim_key: typeof item.claim_key === "string" ? item.claim_key : null,
      claim_text: typeof item.claim_text === "string" ? item.claim_text : null,
      support_type: typeof item.support_type === "string" ? item.support_type : "direct",
    })),
  };
}
const paragraphEntries = (article: ContentDraft["article"]) => Object.entries(article?.paragraphs ?? {});
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const articles = ref<ContentArticle[]>([]), tasks = ref<ContentTask[]>([]), selected = ref<string[]>([]);
const mode = ref<"manual" | "agent">("manual");
const settings = ref<ContentSettings>(), savedSettings = ref<ContentSettings>(), apiKey = ref("");
const importText = ref(""), importItems = ref<ImportItem[]>([]), exportedPrompt = ref("");
const draft = ref<ContentDraft>(), editor = ref<DraftContent>(), savedContent = ref(""), openedContent = ref("");
const batch = ref<ContentBatch>(), busy = ref(""), loading = ref(true), error = ref<ApiError>(), notice = ref("");
let pollTimer: ReturnType<typeof setTimeout> | undefined;
let mounted = true;
const taskByArticle = computed(() => new Map(tasks.value.map(item => [item.article_version_id, item])));
const selectedCount = computed(() => selected.value.length);
const settingsChanged = computed(() => !!settings.value && (JSON.stringify(settings.value) !== JSON.stringify(savedSettings.value) || !!apiKey.value));
const draftChanged = computed(() => !!editor.value && JSON.stringify(editor.value) !== savedContent.value);
const editorEdited = computed(() => !!editor.value && JSON.stringify(editor.value) !== openedContent.value);
const validAutoSettings = computed(() => {
  const s = savedSettings.value;
  return !!s?.enabled && !!s.profile.has_api_key && !!s.profile.provider && !!s.profile.base_url && !!s.profile.model &&
    s.batch_limit > 0 && s.daily_article_limit > 0 && s.daily_input_tokens > 0 && s.daily_output_tokens > 0 && s.max_output_tokens > 0 && s.article_max_calls > 0 && s.concurrency > 0;
});
const batchActive = computed(() => !!batch.value && ["queued", "running", "processing"].includes(batch.value.status));
const selectedArticleIds = computed(() => selected.value.filter(id => articles.value.some(article => article.article_version_id === id)));
const autoSelectionAllowed = computed(() => selectedCount.value <= (savedSettings.value?.batch_limit ?? 0) && selected.value.every(id => {
  const task = taskByArticle.value.get(id);
  return !task?.draft_id && !task?.batch_id && !["published", "skipped", "unknown", "auto_processing", "queued_auto", "superseded"].includes(task?.status ?? "");
}));
const readableStatus = (status?: string | null) => ({
  error: tr("导入失败", "Import error"),
  candidate: tr("待处理", "Pending"), extraction_failed: tr("提取失败", "Extraction failed"), extraction_unknown: tr("提取结果未知", "Extraction outcome unknown"), filtered: tr("已筛选待审", "Filtered for review"), superseded: tr("已有更新版本", "Newer version available"), queued_auto: tr("自动排队中", "Queued for Agent"), auto_processing: tr("自动处理中", "Agent processing"),
  pending: tr("待处理", "Pending"), waiting_manual: tr("等待手动结果", "Awaiting manual result"), manual_exported: tr("等待手动结果", "Awaiting manual result"),
  processing: tr("自动处理中", "Processing"), queued: tr("排队中", "Queued"), running: tr("处理中", "Running"),
  draft: tr("待审草稿", "Draft for review"), needs_review: tr("待审草稿", "Draft for review"),
  validation_failed: tr("校验失败", "Validation failed"), invalid: tr("校验失败", "Validation failed"), failed: tr("失败", "Failed"),
  unknown: tr("结果未知", "Outcome unknown"), budget_paused: tr("预算暂停", "Budget paused"), paused: tr("已暂停", "Paused"),
  published: tr("已发布", "Published"), skipped: tr("已跳过", "Skipped"), completed: tr("已完成", "Completed"),
}[status ?? ""] ?? status ?? tr("待处理", "Pending"));
function readableIssue(message: string) {
  const required = /^([a-z_]+): (Field required|field required)$/i.exec(message);
  if (required) {
    const field = ({ title_zh: tr("中文标题", "Chinese title"), summary_zh: tr("中文摘要", "Chinese summary"),
      category: tr("分类", "Category"), importance: tr("重要度", "Importance"),
      evidence: tr("引用", "Evidence"), entities: tr("实体", "Entities") } as Record<string, string>)[required[1]] ?? required[1];
    return tr("{field}：缺少必填项", "{field}: required", { field });
  }
  const messages: Record<string, [string, string]> = {
    "evidence quote is not an exact paragraph substring": ["引用未逐字出现在对应原文段落中。", "Quote is not an exact substring of the selected paragraph."],
    "relevant must be true for a publishable event": ["无关内容请使用“标为无关并跳过”。", "Use Mark irrelevant and skip for unrelated content."],
    "Unknown task": ["任务编号未知，请核对导出的任务。", "Unknown task ID. Check the exported task."],
    "title_zh is required": ["缺少中文标题。", "Chinese title is required."],
  };
  const matched = messages[message];
  return matched ? tr(matched[0], matched[1]) : message;
}const formatDate = (value?: string | null) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value)) : tr("日期待确认", "Date unconfirmed");
function report(e: unknown) { if (!mounted) return; const problem = err(e); if (problem.status === 401) emit("unauthorized"); else error.value = problem; }
function clearFeedback() { error.value = undefined; notice.value = ""; }
function toggle(id: string, checked: boolean) {
  if (!checked) { selected.value = selected.value.filter(value => value !== id); return; }
  if (selected.value.length >= 5) { notice.value = tr("每批最多选择 5 篇文章。", "Select up to five articles per batch."); return; }
  selected.value = [...selected.value, id];
}
function eligible(article: ContentArticle) {
  const status = taskByArticle.value.get(article.article_version_id)?.status ?? article.status;
  if (["published", "skipped", "auto_processing", "superseded"].includes(status ?? "")) return false;
  if (mode.value === "agent" && status === "queued_auto") return false;
  if (mode.value === "agent" && (["unknown", "needs_review", "validation_failed"].includes(status ?? "") || !!taskByArticle.value.get(article.article_version_id)?.draft_id)) return false;
  return true;
}
async function refresh() {
  if (!mounted) return;
  loading.value = true; error.value = undefined;
  try {
    const [articleResult, taskResult, settingResult] = await Promise.all([contentApi.articles(), contentApi.tasks(), contentApi.settings()]);
    if (!mounted) return;
    articles.value = articleResult.items; tasks.value = taskResult.items;
    settings.value = clone(settingResult); savedSettings.value = clone(settingResult);
    selected.value = selected.value.filter(id => articleResult.items.some(article => article.article_version_id === id));
    const linked = taskResult.items.find(item => item.batch_id && ["queued_auto", "auto_processing"].includes(item.status))?.batch_id
      ?? taskResult.items.find(item => item.batch_id)?.batch_id;
    if (linked) { const currentBatch = await contentApi.batch(linked); if (!mounted) return; batch.value = currentBatch; schedulePoll(); }
  } catch (e) { if (mounted) report(e); }
  finally { if (mounted) loading.value = false; }
}
async function refreshTasks() {
  try {
    const [articleResult, taskResult] = await Promise.all([contentApi.articles(), contentApi.tasks()]);
    if (!mounted) return;
    articles.value = articleResult.items; tasks.value = taskResult.items;
  } catch (e) { if (mounted) report(e); }
}
async function ensureSelectedTasks() {
  const result = await contentApi.createTasks(props.csrf, selectedArticleIds.value);
  return result.items;
}
async function exportPrompt() {
  if (!selectedCount.value || busy.value) return;
  busy.value = "export"; clearFeedback();
  try {
    const selectedTasks = await ensureSelectedTasks();
    if (!mounted) return;
    for (const task of selectedTasks) { if (task.batch_id) await contentApi.switchManual(props.csrf, task.id); }
    if (!mounted) return;
    const result = await contentApi.export(props.csrf, selectedTasks.map(item => item.id));
    if (!mounted) return;
    exportedPrompt.value = result.prompt;
    notice.value = tr("任务已生成。复制到网页聊天工具，完成后将 JSON 回答粘贴到下方。", "Task ready. Copy it into a web chat, then paste its JSON answer below.");
    await refreshTasks();
  } catch (e) { report(e); }
  finally { busy.value = ""; }
}
async function copyPrompt() {
  if (!exportedPrompt.value) return;
  try { await navigator.clipboard.writeText(exportedPrompt.value); notice.value = tr("任务已复制。", "Task copied."); }
  catch { notice.value = tr("复制失败，请选中下方任务文本手动复制，或下载文件。", "Copy failed. Select the task text below or download it."); }
}
function downloadPrompt() {
  if (!exportedPrompt.value) return;
  const url = URL.createObjectURL(new Blob([exportedPrompt.value], { type: "text/plain;charset=utf-8" }));
  const link = document.createElement("a"); link.href = url; link.download = "ai-radar-content-task.txt"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function importResult() {
  if (!importText.value.trim() || busy.value) return;
  busy.value = "import"; clearFeedback(); importItems.value = [];
  try {
    const result = await contentApi.import(props.csrf, importText.value);
    if (!mounted) return;
    importItems.value = result.items;
    const accepted = result.items.filter(item => item.draft_id && !item.errors?.length).length;
    notice.value = tr(`已处理 ${result.items.length} 项，${accepted} 项可继续审阅。`, `Processed ${result.items.length} items; ${accepted} ready for review.`);
    await refreshTasks();
  } catch (e) { report(e); }
  finally { busy.value = ""; }
}
async function openDraft(id: string) {
  if (busy.value) return;
  busy.value = "draft"; clearFeedback();
  try {
    const result = await contentApi.draft(id);
    if (!mounted) return;
    draft.value = result; editor.value = normalizeContent(result.content); savedContent.value = JSON.stringify(result.content); openedContent.value = JSON.stringify(editor.value);
  } catch (e) { report(e); }
  finally { busy.value = ""; }
}
function closeDraft(force = false) { if (!force && editorEdited.value && !window.confirm(tr("当前草稿有未保存修改，确定关闭？", "Discard unsaved changes and close this draft?"))) return; draft.value = undefined; editor.value = undefined; savedContent.value = ""; openedContent.value = ""; }
async function saveDraft() {
  if (!draft.value || !editor.value || busy.value) return;
  busy.value = "save-draft"; clearFeedback();
  try {
    const result = await contentApi.saveDraft(props.csrf, draft.value.id, draft.value.revision, editor.value);
    if (!mounted) return;
    draft.value = result; editor.value = normalizeContent(result.content); savedContent.value = JSON.stringify(editor.value); openedContent.value = savedContent.value;
    notice.value = tr("草稿已保存。请核对校验提示后再发布。", "Draft saved. Review validation feedback before publishing.");
    await refreshTasks();
  } catch (e) { report(e); }
  finally { busy.value = ""; }
}
async function publishDraft() {
  if (!draft.value || draftChanged.value || busy.value) return;
  busy.value = "publish"; clearFeedback();
  try {
    const result = await contentApi.publishDraft(props.csrf, draft.value.id, draft.value.revision);
    if (!mounted) return;
    if (result.status !== "published") {
      const updated = await contentApi.draft(draft.value.id);
      if (!mounted) return;
      draft.value = updated; editor.value = normalizeContent(updated.content);
      savedContent.value = JSON.stringify(editor.value); openedContent.value = savedContent.value;
      notice.value = tr("发布前校验未通过，请按提示修改草稿。", "Publication validation failed. Revise the draft using the feedback.");
      await refreshTasks();
      return;
    }
    notice.value = tr("草稿已发布。", "Draft published."); closeDraft(true); await refreshTasks();
  } catch (e) { report(e); }
  finally { busy.value = ""; }
}
async function skipDraft() {
  if (!draft.value || !editor.value || editor.value.relevant || busy.value) return;
  if (!window.confirm(tr("确认将此文章标为无关并跳过？", "Mark this article irrelevant and skip it?"))) return;
  busy.value = "skip"; clearFeedback();
  try {
    const taskId = draft.value.task_id;
    await contentApi.switchManual(props.csrf, taskId);
    if (!mounted) return;
    await contentApi.skipTask(props.csrf, taskId);
    if (!mounted) return;
    closeDraft(true);
    notice.value = tr("文章已标为无关并跳过。", "Article marked irrelevant and skipped.");
    selected.value = selected.value.filter(id => taskByArticle.value.get(id)?.id !== taskId);
    await refreshTasks();
  } catch (e) { report(e); }
  finally { busy.value = ""; }
}function addEvidence() { editor.value?.evidence.push({ paragraph_id: "", quote_text: "", claim_key: null, claim_text: null, support_type: "direct" }); }
function addEntity() { editor.value?.entities.push({ canonical_name: "", entity_type: "organization", role: "mention" }); }
async function saveSettings() {
  if (!settings.value || busy.value) return;
  busy.value = "settings"; clearFeedback();
  try {
    const current = settings.value;
    const payload = {
      enabled: current.enabled, auto_publish: current.auto_publish, batch_limit: current.batch_limit,
      daily_article_limit: current.daily_article_limit, daily_input_tokens: current.daily_input_tokens,
      daily_output_tokens: current.daily_output_tokens, article_max_calls: current.article_max_calls,
      max_output_tokens: current.max_output_tokens, concurrency: current.concurrency,
      profile: { provider: current.profile.provider, base_url: current.profile.base_url, model: current.profile.model,
        ...(apiKey.value ? { api_key: apiKey.value } : {}) },
    };
    const saved = await contentApi.saveSettings(props.csrf, payload);
    if (!mounted) return;
    settings.value = clone(saved); savedSettings.value = clone(saved); apiKey.value = "";
    notice.value = tr("内容 Agent 设置已保存。保存不会发起模型调用。", "Content Agent settings saved. Saving does not call the model.");
  } catch (e) { report(e); }
  finally { busy.value = ""; }
}function schedulePoll() {
  if (pollTimer) clearTimeout(pollTimer);
  if (!mounted || !batchActive.value) return;
  pollTimer = setTimeout(() => { void refreshBatch(); }, 3000);
}
async function refreshBatch() {
  if (!batch.value || !mounted) return;
  try { const result = await contentApi.batch(batch.value.id); if (!mounted) return; batch.value = result; await refreshTasks(); }
  catch (e) { if (mounted) report(e); }
  finally { schedulePoll(); }
}
async function startBatch() {
  if (!selectedCount.value || !autoSelectionAllowed.value || !validAutoSettings.value || settingsChanged.value || busy.value || batchActive.value) return;
  busy.value = "batch"; clearFeedback();
  try {
    const selectedTasks = await ensureSelectedTasks();
    if (!mounted) return;
    const result = await contentApi.startBatch(props.csrf, selectedTasks.map(item => item.id));
    if (!mounted) return;
    batch.value = result;
    notice.value = tr("本批已提交。自动处理仅使用已选文章与已保存的独立额度。", "Batch submitted for selected articles under the saved content-only limits.");
    await refreshTasks(); schedulePoll();
  } catch (e) { report(e); }
  finally { busy.value = ""; }
}
async function pauseBatch() {
  if (!batch.value || busy.value) return;
  busy.value = "pause"; clearFeedback();
  try { const result = await contentApi.pauseBatch(props.csrf, batch.value.id); if (!mounted) return; batch.value = result; notice.value = tr("已请求暂停，正在执行的单篇可能仍会完成。未调用的文章可走手动模式。", "Pause requested. An in-flight article may finish; uncalled articles can use manual mode."); await refreshTasks(); schedulePoll(); }
  catch (e) { report(e); }
  finally { busy.value = ""; }
}
onMounted(() => { mounted = true; void refresh(); });
onUnmounted(() => { mounted = false; if (pollTimer) clearTimeout(pollTimer); });
</script>

<template>
  <section class="content-workbench admin-stack" :aria-label="tr('内容工作台', 'Content Workbench')">
    <header class="content-workbench__heading">
      <div><h2>{{ tr('内容工作台', 'Content Workbench') }}</h2><p class="meta">{{ tr('从冻结原文制作草稿，审阅后发布。默认手动处理，不调用本站模型 API。', 'Create drafts from frozen articles and review before publishing. Manual processing is the default and makes no model API call here.') }}</p></div>
      <button type="button" :disabled="!!busy || loading" @click="refresh">{{ tr('刷新', 'Refresh') }}</button>
    </header>
    <p v-if="notice" class="admin-notice" role="status">{{ notice }}</p>
    <p v-if="error" class="error admin-feedback" role="alert">{{ adminError(error) }}</p>
    <p v-if="loading" class="admin-skeleton" role="status">{{ tr('正在加载冻结文章与内容任务…', 'Loading frozen articles and content tasks…') }}</p>
    <template v-else>
      <div class="content-workbench__modes" role="group" :aria-label="tr('生成方式', 'Generation mode')">
        <button type="button" :class="{ active: mode === 'manual' }" :aria-pressed="mode === 'manual'" @click="mode = 'manual'">{{ tr('手动处理', 'Manual') }}</button>
        <button type="button" :class="{ active: mode === 'agent' }" :aria-pressed="mode === 'agent'" @click="mode = 'agent'">{{ tr('Agent 自动', 'Agent automation') }}</button>
      </div>
      <div v-if="batchActive" class="admin-notice content-workbench__running" role="status"><span>{{ tr('内容 Agent 批次正在运行', 'Content Agent batch is active') }}：{{ readableStatus(batch?.status) }}</span><button type="button" :disabled="!!busy" @click="pauseBatch">{{ tr('暂停剩余任务', 'Pause remaining') }}</button></div>
      <section class="card content-workbench__queue">
        <div class="admin-section-title"><div><h3>{{ tr('选择文章', 'Select articles') }}</h3><p class="meta">{{ tr('每批最多 5 篇；仅处理本次勾选的冻结版本。已发布文章不能再提交；自动结果未知时仍可手动导出，不能自动重试。', 'Up to five per batch. Only selected frozen versions are processed. Published articles cannot be submitted again. Unknown Agent outcomes can still be exported manually, but cannot be retried automatically.') }}</p></div><span class="content-workbench__count">{{ selectedCount }}/5</span></div>
        <p v-if="!articles.length" class="empty meta">{{ tr('暂无可处理的冻结文章。先在来源页采集文章，刷新后再选择。', 'No frozen articles are available. Ingest a source first, then refresh this list.') }}</p>
        <div v-else class="content-workbench__list">
          <article v-for="article in articles" :key="article.article_version_id" class="content-workbench__row">
            <label class="content-workbench__select"><input type="checkbox" :checked="selected.includes(article.article_version_id)" :disabled="!!busy || !eligible(article) || (selectedCount >= 5 && !selected.includes(article.article_version_id))" @change="toggle(article.article_version_id, ($event.target as HTMLInputElement).checked)" /><span class="content-workbench__article"><strong>{{ article.title }}</strong><span class="meta">{{ formatDate(article.published_at) }} · <a :href="article.source_url" target="_blank" rel="noopener noreferrer" @click.stop>{{ article.source_url }}</a></span></span></label>
            <div class="content-workbench__row-end"><span class="content-workbench__status">{{ readableStatus(taskByArticle.get(article.article_version_id)?.status ?? article.status) }}</span><button v-if="taskByArticle.get(article.article_version_id)?.draft_id && !['skipped', 'published'].includes(taskByArticle.get(article.article_version_id)?.status ?? '')" type="button" :disabled="!!busy" @click="openDraft(taskByArticle.get(article.article_version_id)!.draft_id!)">{{ tr('审阅草稿', 'Review draft') }}</button></div>
          </article>
        </div>
      </section>
      <section v-if="mode === 'manual'" class="card content-workbench__flow">
        <div class="admin-section-title"><div><h3>{{ tr('导出任务', 'Export task') }}</h3><p class="meta">{{ tr('任务包含所选公开文章的原文与段落标记，不含 API 密钥或研究会话。', 'The task contains selected public articles and paragraph markers, with no API keys or research sessions.') }}</p></div><button type="button" :disabled="!!busy || !selectedCount" @click="exportPrompt">{{ busy === 'export' ? tr('生成中…', 'Preparing…') : tr('生成摘要任务', 'Prepare summary task') }}</button></div>
        <div v-if="exportedPrompt" class="content-workbench__prompt"><div class="content-workbench__actions"><button type="button" @click="copyPrompt">{{ tr('复制任务', 'Copy task') }}</button><button type="button" @click="downloadPrompt">{{ tr('下载任务文件', 'Download task file') }}</button></div><label>{{ tr('任务文本', 'Task text') }}<textarea class="control" :value="exportedPrompt" readonly rows="8" @focus="($event.target as HTMLTextAreaElement).select()" /></label></div>
        <div class="content-workbench__import"><h3>{{ tr('导入结果', 'Import results') }}</h3><p class="meta">{{ tr('粘贴网页聊天工具返回的 JSON；支持 JSON 代码块。每篇独立显示成功或错误，导入不自动发布。', 'Paste JSON from a web chat, including a JSON code block. Each article gets its own result. Importing never publishes automatically.') }}</p><label class="content-workbench__full">{{ tr('JSON 回答', 'JSON answer') }}<textarea v-model="importText" class="control" rows="8" spellcheck="false" :disabled="!!busy" :placeholder="tr('在此粘贴包含 task_id 的结果', 'Paste results containing task_id here')" /></label><button type="button" :disabled="!!busy || !importText.trim()" @click="importResult">{{ busy === 'import' ? tr('校验中…', 'Validating…') : tr('校验并导入', 'Validate and import') }}</button>
          <ul v-if="importItems.length" class="content-workbench__results" :aria-label="tr('逐篇导入结果', 'Per-article import results')"><li v-for="(item, index) in importItems" :key="`${item.task_id}-${index}`"><strong>{{ item.task_id }}</strong><span>{{ readableStatus(item.status) }}</span><button v-if="item.draft_id" type="button" :disabled="!!busy" @click="openDraft(item.draft_id)">{{ tr('审阅草稿', 'Review draft') }}</button><ul v-if="item.errors?.length"><li v-for="(problem, i) in item.errors" :key="i" class="error">{{ readableIssue(problem) }}</li></ul></li></ul>
        </div>
      </section>
      <section v-else class="card content-workbench__agent">
        <div class="admin-section-title"><div><h3>{{ tr('内容 Agent 设置', 'Content Agent settings') }}</h3><p class="meta">{{ tr('独立于公众研究助手。保存配置不会测试连接或发起模型调用；只有点击“开始本批”才会处理所选文章。', 'Separate from the public research assistant. Saving makes no test or model call; only Start batch processes selected articles.') }}</p></div><span class="content-workbench__status">{{ savedSettings?.enabled ? tr('已启用', 'Enabled') : tr('已关闭', 'Disabled') }}</span></div>
        <form v-if="settings" class="content-workbench__settings" @submit.prevent="saveSettings">
          <label>{{ tr('服务商 / 协议', 'Provider / protocol') }}<input v-model="settings.profile.provider" class="control" :disabled="!!busy" placeholder="openai-compatible" /></label>
          <label>{{ tr('Base URL', 'Base URL') }}<input v-model="settings.profile.base_url" class="control" type="url" :disabled="!!busy" placeholder="https://…" /></label>
          <label>{{ tr('模型名称', 'Model name') }}<input v-model="settings.profile.model" class="control" :disabled="!!busy" /></label>
          <label>{{ tr('新 API 密钥', 'New API key') }}<input v-model="apiKey" class="control" type="password" autocomplete="new-password" :disabled="!!busy" :placeholder="tr('留空保留已有密钥', 'Leave blank to keep saved key')" /></label>
          <p class="meta content-workbench__full">{{ settings.profile.has_api_key ? tr('已保存密钥，系统不会回显。', 'A key is saved and will not be displayed.') : tr('尚未保存密钥。', 'No key is saved yet.') }}</p>
          <label>{{ tr('单批文章上限', 'Articles per batch') }}<input v-model.number="settings.batch_limit" class="control" type="number" min="1" max="5" :disabled="!!busy" /></label>
          <label>{{ tr('每日文章上限', 'Daily article limit') }}<input v-model.number="settings.daily_article_limit" class="control" type="number" min="0" :disabled="!!busy" /></label>
          <label>{{ tr('每日输入 token 上限', 'Daily input token limit') }}<input v-model.number="settings.daily_input_tokens" class="control" type="number" min="0" :disabled="!!busy" /></label>
          <label>{{ tr('每日输出 token 上限', 'Daily output token limit') }}<input v-model.number="settings.daily_output_tokens" class="control" type="number" min="0" :disabled="!!busy" /></label>
          <label>{{ tr('每篇最大输出 tokens', 'Maximum output tokens per article') }}<input v-model.number="settings.max_output_tokens" class="control" type="number" min="1" max="2000" :disabled="!!busy" /></label>
          <label>{{ tr('每篇最多调用次数', 'Maximum calls per article') }}<input v-model.number="settings.article_max_calls" class="control" type="number" min="1" max="1" :disabled="!!busy" /></label>
          <label>{{ tr('并发数', 'Concurrency') }}<input v-model.number="settings.concurrency" class="control" type="number" min="1" max="1" :disabled="!!busy" /></label>
          <label class="toggle content-workbench__full"><input v-model="settings.auto_publish" type="checkbox" :disabled="!!busy" />{{ tr('校验通过后自动发布', 'Publish automatically after validation') }}</label>
          <label class="toggle content-workbench__full"><input v-model="settings.enabled" type="checkbox" :disabled="!!busy" />{{ tr('启用内容 Agent', 'Enable Content Agent') }}</label>
          <div class="content-workbench__actions content-workbench__full"><button type="submit" :disabled="!!busy || !settingsChanged">{{ busy === 'settings' ? tr('保存中…', 'Saving…') : tr('保存 Agent 设置', 'Save Agent settings') }}</button><span class="meta">{{ tr('额度为 0 时不能开始批次。默认不自动发布。', 'A zero limit blocks batch starts. Auto-publish is off by default.') }}</span></div>
        </form>
        <div class="content-workbench__batch"><div class="content-workbench__actions"><button type="button" :disabled="!!busy || !selectedCount || !autoSelectionAllowed || !validAutoSettings || settingsChanged || batchActive" @click="startBatch">{{ busy === 'batch' ? tr('提交中…', 'Submitting…') : tr('开始本批', 'Start batch') }}</button><button v-if="batchActive" type="button" :disabled="!!busy" @click="pauseBatch">{{ busy === 'pause' ? tr('暂停中…', 'Pausing…') : tr('暂停剩余任务', 'Pause remaining') }}</button><button v-if="batch" type="button" :disabled="!!busy" @click="refreshBatch">{{ tr('刷新状态', 'Refresh status') }}</button></div><p v-if="!validAutoSettings" class="meta">{{ tr('需先启用专用配置、保存密钥，并填写非零额度。', 'Enable the dedicated profile, save a key, and set nonzero limits first.') }}</p><p v-else-if="settingsChanged" class="meta">{{ tr('先保存设置，才能以新额度开始。', 'Save settings before starting with new limits.') }}</p><p v-else-if="selectedCount && !autoSelectionAllowed" class="meta">{{ tr('请只选无草稿、未自动处理且不超过单批上限的文章。', 'Select fresh articles without drafts or prior Agent work, within the batch limit.') }}</p><div v-if="batch" class="content-workbench__batch-status" role="status"><strong>{{ tr('批次状态', 'Batch status') }}：{{ readableStatus(batch.status) }}</strong><span class="meta">{{ batch.id }}</span><ul v-if="batch.items?.length"><li v-for="item in batch.items" :key="item.id">{{ item.id }} · {{ readableStatus(item.status) }}<span v-if="item.error" class="error"> · {{ item.error }}</span></li></ul></div></div>
      </section>
      <section v-if="draft && editor" class="card content-workbench__draft" aria-labelledby="content-draft-title"><div class="admin-section-title"><div><h3 id="content-draft-title">{{ tr('草稿预览与审阅', 'Draft preview and review') }}</h3><p class="meta">{{ draft.article?.title }} · {{ draft.article?.source_url }}</p></div><button type="button" :disabled="!!busy" @click="closeDraft()">{{ tr('关闭', 'Close') }}</button></div>
        <p v-if="draft.validation_errors?.length" class="error" role="alert">{{ tr('当前校验提示', 'Validation feedback') }}：{{ draft.validation_errors.map(readableIssue).join('；') }}</p>
        <div class="content-workbench__editor"><label class="content-workbench__full">{{ tr('中文标题', 'Chinese title') }}<input v-model="editor.title_zh" class="control" maxlength="220" /></label><label class="content-workbench__full">{{ tr('中文摘要', 'Chinese summary') }}<textarea v-model="editor.summary_zh" class="control" rows="4" maxlength="2000" /></label><label>{{ tr('分类', 'Category') }}<select v-model="editor.category" class="control"><option v-for="category in categories" :key="category.code" :value="category.code">{{ tr(category.zh, category.en) }}</option></select></label><label>{{ tr('重要度', 'Importance') }}<input v-model.number="editor.importance" class="control" type="number" min="1" max="5" /></label><label>{{ tr('事件日期', 'Event date') }}<input v-model="editor.event_date" class="control" type="date" /></label><label>{{ tr('日期精度', 'Date precision') }}<select v-model="editor.date_precision" class="control"><option value="unknown">{{ tr('未知', 'Unknown') }}</option><option value="day">{{ tr('日', 'Day') }}</option><option value="month">{{ tr('月', 'Month') }}</option></select></label><label>{{ tr('日期依据', 'Date basis') }}<select v-model="editor.date_basis" class="control"><option value="unknown">{{ tr('未知', 'Unknown') }}</option><option value="explicit_body">{{ tr('正文明确说明', 'Explicit in body') }}</option><option value="official_publication">{{ tr('官方发布时间', 'Official publication') }}</option></select></label><label>{{ tr('日期证据段落 ID', 'Date evidence paragraph ID') }}<input v-model="editor.date_evidence_paragraph_id" class="control" /></label><label class="toggle content-workbench__full"><input v-model="editor.relevant" type="checkbox" />{{ tr('与 AI 事件相关', 'Relevant AI event') }}</label></div>
        <div class="content-workbench__evidence"><div class="admin-section-title"><h4>{{ tr('引用与实体', 'Evidence and entities') }}</h4><button type="button" @click="addEvidence">{{ tr('添加引用', 'Add quote') }}</button></div><div v-for="(item, index) in editor.evidence" :key="index" class="content-workbench__evidence-row"><label>{{ tr('段落 ID', 'Paragraph ID') }}<input v-model="item.paragraph_id" class="control" /></label><label>{{ tr('原文逐字引用', 'Exact source quote') }}<textarea v-model="item.quote_text" class="control" rows="2" /></label><button type="button" @click="editor.evidence.splice(index, 1)">{{ tr('移除', 'Remove') }}</button></div><div class="content-workbench__actions"><button type="button" @click="addEntity">{{ tr('添加实体', 'Add entity') }}</button></div><div v-for="(item, index) in editor.entities" :key="index" class="content-workbench__entity-row"><label>{{ tr('实体名称', 'Entity name') }}<input v-model="item.canonical_name" class="control" /></label><label>{{ tr('类型', 'Type') }}<select v-model="item.entity_type" class="control"><option value="organization">{{ tr('组织', 'Organization') }}</option><option value="company">{{ tr('公司', 'Company') }}</option><option value="model">{{ tr('模型', 'Model') }}</option><option value="product">{{ tr('产品', 'Product') }}</option><option value="person">{{ tr('人物', 'Person') }}</option><option value="technology">{{ tr('技术', 'Technology') }}</option></select></label><label>{{ tr('角色', 'Role') }}<select v-model="item.role" class="control"><option value="subject">{{ tr('主体', 'Subject') }}</option><option value="product">{{ tr('产品', 'Product') }}</option><option value="mention">{{ tr('提及', 'Mention') }}</option></select></label><button type="button" @click="editor.entities.splice(index, 1)">{{ tr('移除', 'Remove') }}</button></div></div>
        <details v-if="paragraphEntries(draft.article).length" class="content-workbench__paragraphs"><summary>{{ tr('核对冻结原文段落', 'Check frozen source paragraphs') }}</summary><ol><li v-for="[paragraphId, paragraphText] in paragraphEntries(draft.article)" :key="paragraphId"><code>{{ paragraphId }}</code> {{ paragraphText }}</li></ol></details>
        <div class="content-workbench__actions content-workbench__footer"><button type="button" :disabled="!!busy || !draftChanged" @click="saveDraft">{{ busy === 'save-draft' ? tr('保存中…', 'Saving…') : tr('保存草稿', 'Save draft') }}</button><button v-if="!editor.relevant" type="button" :disabled="!!busy" @click="skipDraft">{{ busy === 'skip' ? tr('跳过中…', 'Skipping…') : tr('标为无关并跳过', 'Mark irrelevant and skip') }}</button><button type="button" class="content-workbench__publish" :disabled="!!busy || draftChanged || !editor.relevant || !!draft.validation_errors?.length || draft.status === 'published'" @click="publishDraft">{{ busy === 'publish' ? tr('发布中…', 'Publishing…') : tr('确认发布', 'Publish') }}</button><span v-if="draftChanged" class="meta">{{ tr('先保存修改，再发布。', 'Save changes before publishing.') }}</span></div>
      </section>
    </template>
  </section>
</template>
