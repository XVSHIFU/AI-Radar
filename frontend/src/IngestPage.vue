<script setup lang="ts">
import { ref } from "vue";
import { ingest, err, type Run, type Source } from "./api";
const token = ref(""),
  sources = ref<Source[]>([]),
  runs = ref<Run[]>([]),
  error = ref<any>(),
  notice = ref("");
async function load() {
  error.value = null;
  try {
    [sources.value, runs.value] = await Promise.all([
      ingest.sources(token.value).then((x) => x.items),
      ingest.runs(token.value).then((x) => x.items),
    ]);
  } catch (e) {
    error.value = err(e);
  }
}
async function start() {
  try {
    const x = await ingest.start(
      token.value,
      sources.value.filter((s) => s.enabled).map((s) => s.id),
    );
    notice.value = `已接受采集请求：${x.run_id}`;
    await load();
  } catch (e) {
    error.value = err(e);
  }
}
</script>
<template>
  <section>
    <h1>采集管理</h1>
    <p class="muted">管理凭据仅保留在当前页面内存中。</p>
    <label
      >管理令牌<input
        v-model="token"
        type="password"
        class="control"
        autocomplete="off"
    /></label>
    <div class="row">
      <button @click="load">读取状态</button
      ><button :disabled="!sources.length" @click="start">开始采集</button>
    </div>
    <p aria-live="polite">{{ notice }}</p>
    <div v-if="error" class="card error" role="alert">
      <strong>{{
        error.status === 401
          ? "未授权"
          : error.status === 503
            ? "服务未配置或不可用"
            : error.code
      }}</strong
      >：{{ error.message }}
      <p v-if="error.code === 'BUDGET_EXCEEDED'">预算不足，未开始新运行。</p>
    </div>
    <div v-if="sources.length" class="card">
      <h2>来源健康</h2>
      <p v-for="s in sources">
        {{ s.name }} · {{ s.health }} · 连续失败 {{ s.consecutive_failures }}
      </p>
    </div>
    <div v-if="runs.length" class="card">
      <h2>近期运行</h2>
      <p v-for="r in runs">
        {{ r.status }} · 发现 {{ r.found }} / 保留 {{ r.kept }} · 成本
        {{ r.cost_status === "unknown" ? "未知" : r.cost }}
        <span v-if="r.error_summary">· {{ r.error_summary }}</span>
      </p>
    </div>
  </section>
</template>
