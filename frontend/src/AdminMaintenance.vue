<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { err, events, type Event, type Evidence } from "./api";
import { maintenance, type AuditEntry, type DateReview, type MergeRecord } from "./maintenance-api";
import { formatDate, translate as tr } from "./locale";

const props = defineProps<{ csrf: string }>();
const emit = defineEmits<{ unauthorized: [] }>();
const rows = ref<DateReview[]>([]), audit = ref<AuditEntry[]>([]), merges = ref<MergeRecord[]>([]);
const loading = ref(false), busy = ref(false), message = ref(""), problem = ref("");
const selected = ref<DateReview>(), detail = ref<Event>(), evidence = ref<Evidence[]>([]);
const candidateIndex = ref(""), confirmDate = ref(false), filter = ref("");
const sourceId = ref(""), targetId = ref(""), reason = ref(""), mergeConfirmed = ref(false);
const pair = ref<Array<{ event: Event; evidence: Evidence[] }>>([]), undoId = ref("");
const controller = new AbortController();
let alive = true, detailGeneration = 0;
const candidates = computed(() => selected.value?.candidates ?? []);
const visible = computed(() => rows.value.filter(row => !filter.value || (row.title_zh?.includes(filter.value) || row.event_id.includes(filter.value)) || row.current_date?.includes(filter.value)));
const chosen = computed(() => candidateIndex.value === "" ? undefined : candidates.value[Number(candidateIndex.value)]);
const quote = computed(() => evidence.value.find(item => item.id === chosen.value?.evidence_id));

function failure(error: unknown) {
  if (!alive) return;
  const value = err(error);
  if (value.status === 401) emit("unauthorized");
  else if (value.status === 409) problem.value = tr("事件或证据状态已改变，请刷新后重新核对；已归并的事件可先撤销原归并。", "The event or evidence has changed. Refresh and review again; undo an existing merge before regrouping.");
  else problem.value = value.status === 403 ? tr("操作未通过验证，请重新登录。", "Verification failed. Sign in again.") : tr("操作未完成，请重试。", "Could not complete the operation. Try again.") + ` (${value.code})`;
}
async function refresh() {
  if (loading.value || busy.value) return;
  loading.value = true; problem.value = "";
  const results = await Promise.allSettled([maintenance.dates(controller.signal), maintenance.audit(controller.signal), maintenance.merges(controller.signal)]);
  if (!alive) return;
  if (results[0].status === "fulfilled") rows.value = results[0].value.items; else failure(results[0].reason);
  if (results[1].status === "fulfilled") audit.value = results[1].value.items; else failure(results[1].reason);
  if (results[2].status === "fulfilled") merges.value = results[2].value.items; else failure(results[2].reason);
  loading.value = false;
}
async function inspect(row: DateReview) {
  const generation = ++detailGeneration;
  selected.value = row; detail.value = undefined; evidence.value = []; candidateIndex.value = ""; confirmDate.value = false;
  try {
    const [event, quotes] = await Promise.all([events.one(row.event_id, controller.signal), events.evidence(row.event_id, controller.signal)]);
    if (alive && generation === detailGeneration) { detail.value = event; evidence.value = quotes; }
  } catch (error) { if (generation === detailGeneration) failure(error); }
}
async function correctDate() {
  if (busy.value || !selected.value || !chosen.value || !quote.value || !confirmDate.value) return;
  busy.value = true; problem.value = "";
  try {
    await maintenance.correctDate(props.csrf, selected.value.event_id, chosen.value);
    if (!alive) return;
    message.value = tr("日期已修正并记录审计。", "Date corrected and audited.");
    selected.value = undefined; detail.value = undefined; evidence.value = [];
  } catch (error) { failure(error); }
  finally { busy.value = false; }
  if (alive) await refresh();
}
async function previewMerge() {
  if (busy.value || !sourceId.value.trim() || !targetId.value.trim()) return;
  busy.value = true; pair.value = []; mergeConfirmed.value = false; problem.value = "";
  try {
    const result = await Promise.all([sourceId.value.trim(), targetId.value.trim()].map(async id => ({ event: await events.one(id, controller.signal), evidence: await events.evidence(id, controller.signal) })));
    if (alive) pair.value = result;
  } catch (error) { failure(error); }
  finally { busy.value = false; }
}
async function merge() {
  if (busy.value || pair.value.length !== 2 || !mergeConfirmed.value || reason.value.trim().length < 3) return;
  busy.value = true; problem.value = "";
  try {
    const result = await maintenance.merge(props.csrf, pair.value[0]!.event.id, pair.value[1]!.event.id, reason.value.trim(), {
      source_evidence_ids: pair.value[0]!.evidence.map(item => item.id),
      target_evidence_ids: pair.value[1]!.evidence.map(item => item.id),
      review: reason.value.trim(),
    });
    if (!alive) return;
    undoId.value = result.merge_id; pair.value = []; mergeConfirmed.value = false;
    message.value = tr("事件已归并，原文与证据保留。请保存归并记录编号，以便撤销。", "Events merged; sources and evidence preserved. Keep the merge record ID to undo.");
  } catch (error) { failure(error); }
  finally { busy.value = false; }
  if (alive) await refresh();
}
async function revert() {
  if (busy.value || !undoId.value.trim()) return;
  busy.value = true; problem.value = "";
  try {
    await maintenance.revert(props.csrf, undoId.value.trim());
    if (alive) { undoId.value = ""; message.value = tr("归并已撤销。", "Merge reverted."); }
  } catch (error) { failure(error); }
  finally { busy.value = false; }
  if (alive) await refresh();
}
onMounted(refresh);
onBeforeUnmount(() => { alive = false; controller.abort(); });
</script>

<template>
  <section class="maintenance" :aria-busy="busy || loading">
    <div class="admin-section-title"><div><h2>{{ tr('数据核查', 'Data review') }}</h2><p class="meta">{{ tr('先查看保存的证据，再确认日期或归并。修改均保留审计记录。', 'Review saved evidence before correcting a date or merging events. Changes are audited.') }}</p></div><button :disabled="busy || loading" @click="refresh">{{ loading ? tr('读取中…', 'Loading…') : tr('刷新', 'Refresh') }}</button></div>
    <p v-if="problem" class="error" role="alert">{{ problem }}</p><p v-if="message" class="admin-notice" role="status">{{ message }}</p>
    <section class="maintenance-section">
      <h3>{{ tr('日期复核', 'Date review') }}</h3><p class="meta">{{ tr('候选日期来自保存原文，仍需确认它描述的是本事件。最多显示 1000 条记录。', 'Candidates are literal dates in saved text. Verify that a date describes this event. Up to 1,000 records.') }}</p>
      <label class="maintenance-filter">{{ tr('筛选标题、日期或编号', 'Filter title, date or ID') }}<input v-model="filter" class="control" type="search" /></label>
      <div class="maintenance-review">
        <div class="maintenance-list" :aria-label="tr('待核查事件', 'Events to review')">
          <p v-if="!visible.length && !loading" class="meta">{{ tr('当前没有匹配的记录。', 'No matching records.') }}</p>
          <button v-for="row in visible" :key="row.event_id" :disabled="busy" :aria-pressed="selected?.event_id === row.event_id" @click="inspect(row)"><strong v-if="row.title_zh">{{ row.title_zh }}</strong><span>{{ row.current_date ?? tr('日期未知', 'Unknown date') }}</span><span>{{ tr('待复核', 'Needs review') }} · {{ row.candidates.length }} {{ tr('个候选', 'candidates') }}</span><small>{{ row.event_id }}</small></button>
        </div>
        <div class="maintenance-detail">
          <p v-if="!selected" class="meta">{{ tr('选择一条记录查看事件和证据。', 'Select a record to inspect its event and evidence.') }}</p>
          <template v-else>
            <p v-if="!detail" class="meta">{{ tr('读取事件中…', 'Loading event…') }}</p><h4 v-if="detail">{{ detail.title_zh }}</h4><p v-if="detail">{{ detail.summary_zh }}</p>
            <p v-if="!candidates.length" class="meta">{{ tr('没有可定位的候选日期，保留未核验状态。', 'No located date candidate. The date remains unverified.') }}</p>
            <template v-else><label>{{ tr('候选日期', 'Candidate date') }}<select v-model="candidateIndex" class="control" :disabled="busy" @change="confirmDate = false"><option value="">{{ tr('选择原文中的日期', 'Select a date from the source') }}</option><option v-for="(candidate, index) in candidates" :key="`${candidate.date}-${candidate.evidence_id}`" :value="String(index)">{{ candidate.date }} · {{ candidate.paragraph_id }}</option></select></label><blockquote v-if="quote">{{ quote.quote_text }}</blockquote><p v-if="chosen && !quote" class="meta">{{ tr('未能加载对应证据，请重新选择记录。', 'Evidence could not be loaded. Select the record again.') }}</p><label v-if="quote" class="maintenance-confirm"><input v-model="confirmDate" type="checkbox" :disabled="busy" />{{ tr('已核对原文：该日期确实属于本事件。', 'I verified that this date refers to this event.') }}</label><button :disabled="busy || !quote || !confirmDate" @click="correctDate">{{ tr('确认修正日期', 'Confirm date correction') }}</button></template>
          </template>
        </div>
      </div>
    </section>
    <details class="maintenance-section"><summary>{{ tr('人工归并重复事件', 'Merge duplicate events') }}</summary><p class="meta">{{ tr('从事件地址中复制编号。目标事件保留在列表中，两侧原文与证据保持可追溯。', 'Copy IDs from event URLs. The target remains visible and all sources stay traceable.') }}</p>
      <form class="maintenance-fields" @submit.prevent="previewMerge"><label>{{ tr('待归并事件编号', 'Source event ID') }}<input v-model="sourceId" class="control" :disabled="busy" @input="pair = []" /></label><label>{{ tr('保留的事件编号', 'Target event ID') }}<input v-model="targetId" class="control" :disabled="busy" @input="pair = []" /></label><button :disabled="busy || !sourceId.trim() || !targetId.trim() || sourceId.trim() === targetId.trim()">{{ tr('对照事件', 'Compare events') }}</button></form>
      <div v-if="pair.length === 2" class="maintenance-pair"><article v-for="(item, index) in pair" :key="index"><p class="meta">{{ index === 0 ? tr('待归并', 'Source') : tr('保留', 'Target') }}</p><h4>{{ item.event.title_zh }}</h4><p>{{ item.event.summary_zh }}</p><details><summary>{{ tr('查看保存证据', 'Read saved evidence') }} ({{ item.evidence.length }})</summary><blockquote v-for="entry in item.evidence" :key="entry.id">{{ entry.quote_text }}</blockquote></details></article></div>
      <div v-if="pair.length === 2"><label>{{ tr('归并依据', 'Reason for merging') }}<textarea v-model="reason" class="control" maxlength="2000" :disabled="busy" /></label><label class="maintenance-confirm"><input v-model="mergeConfirmed" type="checkbox" :disabled="busy" />{{ tr('已核对两侧证据，确认是同一事件。', 'I reviewed both sets of evidence and confirmed the same event.') }}</label><button :disabled="busy || !mergeConfirmed || reason.trim().length < 3" @click="merge">{{ tr('确认归并', 'Confirm merge') }}</button></div>
      <ol v-if="merges.length" class="maintenance-audit"><li v-for="record in merges" :key="record.id"><strong>{{ record.source_title }} → {{ record.target_title }}</strong><p class="meta">{{ record.reason }}</p><p><time>{{ formatDate(record.created_at, { dateStyle: 'short', timeStyle: 'short' }) }}</time> · {{ record.reverted_at ? tr('已撤销', 'Reverted') : tr('已归并', 'Merged') }}</p><button v-if="!record.reverted_at" :disabled="busy" @click="undoId = record.id">{{ tr('选择此记录以撤销', 'Select this record to undo') }}</button></li></ol>
      <form class="maintenance-fields" @submit.prevent="revert"><label>{{ tr('归并记录编号', 'Merge record ID') }}<input v-model="undoId" class="control" :disabled="busy" /></label><button :disabled="busy || !undoId.trim()">{{ tr('撤销此归并', 'Undo this merge') }}</button></form>
    </details>
    <section class="maintenance-section"><h3>{{ tr('近期操作记录', 'Recent administrative actions') }}</h3><p class="meta">{{ tr('最近 50 次操作，不记录密钥和请求正文。', 'Latest 50 actions. Keys and request bodies are excluded.') }}</p><p v-if="!audit.length && !loading" class="meta">{{ tr('暂无操作记录。', 'No recorded actions.') }}</p><ol class="maintenance-audit"><li v-for="entry in audit" :key="entry.id"><div><strong>{{ entry.action }}</strong><span>{{ entry.outcome === 'success' ? tr('成功', 'Success') : tr('未完成', 'Failed') }} · {{ entry.status_code }}</span></div><time>{{ formatDate(entry.occurred_at, { dateStyle: 'short', timeStyle: 'short' }) }}</time><details><summary>{{ tr('详情', 'Details') }}</summary><p>{{ entry.target }}</p><p>{{ tr('请求编号', 'Request ID') }}: {{ entry.request_id }}</p></details></li></ol></section>
  </section>
</template>

<style scoped>
.maintenance { min-width: 0; }
.maintenance-section { margin-top: 28px; padding-top: 24px; border-top: 1px solid var(--line); }
.maintenance-section:first-of-type { border-top: 0; padding-top: 0; }
.maintenance h3, .maintenance h4 { margin: 0 0 12px; }
.maintenance p { line-height: 1.7; }
.maintenance label { display: grid; gap: 8px; }
.maintenance button { min-height: 36px; }
.maintenance > .admin-section-title > button { flex-shrink: 0; white-space: nowrap; }
.maintenance-filter { max-width: 420px; margin: 18px 0; }
.maintenance-review { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(0, 2fr); gap: 28px; }
.maintenance-list { max-height: 520px; overflow: auto; overscroll-behavior: contain; }
.maintenance-list button { width: 100%; display: grid; gap: 6px; text-align: start; padding: 14px 8px; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; background: transparent; }
.maintenance-list button[aria-pressed="true"] { color: var(--blue); }
.maintenance-list small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.maintenance-list span, .maintenance-list small { font-size: 12px; }
.maintenance-detail { min-width: 0; }
.maintenance blockquote { margin: 18px 0; padding: 12px 16px; border-left: 1px solid var(--line); font-size: 14px; overflow-wrap: anywhere; }
.maintenance .maintenance-confirm { display: flex; align-items: flex-start; gap: 10px; margin: 18px 0; }
.maintenance-confirm input { margin-top: 5px; flex-shrink: 0; }
.maintenance-fields { display: flex; align-items: end; flex-wrap: wrap; gap: 16px; margin: 20px 0; }
.maintenance-fields label { flex: 1 1 250px; }
.maintenance-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }
.maintenance-pair article { min-width: 0; }
.maintenance textarea { min-height: 88px; }
.maintenance summary { cursor: pointer; }
.maintenance-audit { margin: 0; padding: 0; list-style: none; }
.maintenance-audit li { padding: 16px 0; border-bottom: 1px solid var(--line); overflow-wrap: anywhere; }
.maintenance-audit li > div { display: flex; justify-content: space-between; gap: 16px; }
.maintenance-audit time, .maintenance-audit summary { font-size: 12px; }
@media (max-width: 720px) { .maintenance-review, .maintenance-pair { grid-template-columns: 1fr; } .maintenance-list { max-height: 240px; } .maintenance button { min-height: 44px; } }
</style>
