<script setup lang="ts">
import { ref } from "vue";
import { err, ingest, type Run, type Source } from "./api";
import { idempotentSubmission } from "./submission";
const token = ref(""),
  sources = ref<Source[]>([]),
  runs = ref<Run[]>([]),
  sourcesLoading = ref(false),
  runsLoading = ref(false),
  submitting = ref(false),
  sourcesError = ref<ReturnType<typeof err>>(),
  runsError = ref<ReturnType<typeof err>>(),
  submitError = ref<ReturnType<typeof err>>(),
  notice = ref(""),
  submission = idempotentSubmission();
async function loadSources() {
  sourcesLoading.value = true;
  sourcesError.value = undefined;
  try {
    sources.value = (await ingest.sources(token.value)).items;
  } catch (e) {
    sourcesError.value = err(e);
  } finally {
    sourcesLoading.value = false;
  }
}
async function loadRuns() {
  runsLoading.value = true;
  runsError.value = undefined;
  try {
    runs.value = (await ingest.runs(token.value)).items;
  } catch (e) {
    runsError.value = err(e);
  } finally {
    runsLoading.value = false;
  }
}
function load() {
  void loadSources();
  void loadRuns();
}
async function start() {
  const key = submission.begin();
  if (!key) return;
  submitting.value = true;
  submitError.value = undefined;
  try {
    const response = await ingest.start(
      token.value,
      sources.value.filter((s) => s.enabled).map((s) => s.id),
      key,
    );
    submission.finish(true);
    notice.value = `已接受采集请求：${response.run_id}`;
    void loadRuns();
  } catch (e) {
    submission.finish(false);
    submitError.value = err(e);
  } finally {
    submitting.value = false;
  }
}
</script>
<template>
  <section>
    <h1>采集管理</h1>
    <p class="muted">管理令牌仅保留在当前页面内存中。</p>
    <label
      >管理令牌<input
        v-model="token"
        type="password"
        class="control"
        autocomplete="off"
    /></label>
    <div class="row">
      <button :disabled="sourcesLoading || runsLoading || !token" @click="load">
        {{ sourcesLoading || runsLoading ? "读取中…" : "读取状态" }}</button
      ><button
        :disabled="submitting || !sources.some((s) => s.enabled)"
        @click="start"
      >
        {{ submitting ? "正在提交…" : "开始采集" }}
      </button>
    </div>
    <p aria-live="polite">{{ notice }}</p>
    <div v-if="submitError" class="card error" role="alert">
      <strong>{{
        submitError.status === 401
          ? "未授权"
          : submitError.status === 503
            ? "服务未配置或不可用"
            : submitError.code
      }}</strong
      >：{{ submitError.message }}<button @click="start">重试采集</button>
    </div>
    <div class="card">
      <h2>来源健康</h2>
      <p v-if="sourcesLoading">正在读取来源…</p>
      <div v-else-if="sourcesError" class="error" role="alert">
        {{
          sourcesError.status === 401
            ? "令牌无效"
            : sourcesError.status === 503
              ? "来源服务未配置"
              : sourcesError.message
        }}
        <button @click="loadSources">重试来源</button>
      </div>
      <p v-else-if="!sources.length" class="meta">尚未读取来源。</p>
      <p v-for="s in sources" :key="s.id">
        {{ s.name }} · {{ s.health }} · 连续失败 {{ s.consecutive_failures }}
      </p>
    </div>
    <div class="card">
      <h2>近期运行</h2>
      <p v-if="runsLoading">正在读取运行记录…</p>
      <div v-else-if="runsError" class="error" role="alert">
        {{
          runsError.status === 401
            ? "令牌无效"
            : runsError.status === 503
              ? "运行服务未配置"
              : runsError.message
        }}
        <button @click="loadRuns">重试运行记录</button>
      </div>
      <p v-else-if="!runs.length" class="meta">尚未读取运行记录。</p>
      <p v-for="r in runs" :key="r.id">
        {{ r.status }} · 发现URL {{ r.found }} · 候选报道 {{ r.candidates }} ·
        正文版本 {{ r.versions }} · 已发布事件 {{ r.kept }} · 解析失败
        {{ r.parser_failures }} / 任务失败 {{ r.failed_jobs }} · 成本
        {{
          r.cost_status === "actual"
            ? "实际"
            : r.cost_status === "estimated"
              ? "估算"
              : "未知"
        }}{{ r.cost_status === "unknown" ? "" : ` ${r.cost ?? "未提供"}` }}
        <span v-if="r.error_summary">· {{ r.error_summary }}</span>
      </p>
    </div>
  </section>
</template>
