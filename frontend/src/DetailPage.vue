<script setup lang="ts">
import { ref, watch } from "vue";
import { events, err, isDemo, type Event, type Evidence } from "./api";
import { useRoute } from "vue-router";
const route = useRoute();
const item = ref<Event>();
const evidence = ref<Evidence[]>([]);
const error = ref<ReturnType<typeof err>>();
const open = ref<string>();
const controller = ref<AbortController>();
const safe = (u: string) => /^https?:\/\//i.test(u);
async function load(id: string) {
  controller.value?.abort();
  controller.value = new AbortController();
  item.value = undefined;
  evidence.value = [];
  error.value = undefined;
  try {
    const x = await events.one(id, controller.value.signal);
    if (!x) throw { code: "NOT_FOUND", message: "未找到该事件", status: 404 };
    item.value = x;
    evidence.value = await events.evidence(id, controller.value.signal);
  } catch (e) {
    if ((e as Error).name !== "AbortError") error.value = err(e);
  }
}
watch(
  () => route.params.id,
  (id) => load(String(id)),
  { immediate: true },
);
</script>
<template>
  <p>
    <RouterLink :to="{ path: '/', query: { demo: $route.query.demo } }"
      >← 返回事件</RouterLink
    >
  </p>
  <div v-if="error" class="card error" role="alert">
    {{ error.status === 404 ? "事件不存在" : error.message }}
  </div>
  <article v-else-if="item" class="card">
    <p class="meta">
      {{ item.event_date || "日期未知" }} · {{ item.date_precision }}
    </p>
    <h1>{{ item.title_zh }}</h1>
    <p>{{ item.summary_zh }}</p>
    <h2>相关实体</h2>
    <p class="row">
      <span v-for="e in item.entities" :key="e" class="pill">{{ e }}</span>
    </p>
    <h2>来源与摘录</h2>
    <p v-if="isDemo()" class="demo">以下摘录为合成演示，不是系统保存的原文。</p>
    <p v-if="!item.evidence_count" class="meta">此事件没有关联证据。</p>
    <div
      v-for="x in item.evidence_count ? evidence : []"
      :key="x.id"
      class="card"
    >
      <button
        :aria-expanded="open === x.id"
        @click="open = open === x.id ? undefined : x.id"
      >
        {{ open === x.id ? "收起" : "展开" }}摘录：{{ x.title }}
      </button>
      <blockquote v-if="open === x.id">
        {{ x.quote_text }}
        <footer class="meta">
          版本 {{ x.article_version_id }} · 段落 {{ x.paragraph_id }}
        </footer>
      </blockquote>
      <a
        v-if="safe(x.source_url)"
        :href="x.source_url"
        target="_blank"
        rel="noopener"
        >打开来源</a
      ><span v-else class="meta">来源地址无效</span>
    </div>
  </article>
  <p v-else>正在加载详情…</p>
</template>
