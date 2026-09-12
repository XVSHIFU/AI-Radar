<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { events, err, isDemo, type Event, type Evidence } from "./api";
import { useRoute } from "vue-router";
const route = useRoute(),
  item = ref<Event>(),
  evidence = ref<Evidence[]>([]),
  error = ref<ReturnType<typeof err>>(),
  open = ref<string>();
let generation = 0;
let controller: AbortController | undefined;
const safe = (u: string) => /^https?:\/\//i.test(u);
async function load() {
  const current = ++generation;
  controller?.abort();
  controller = new AbortController();
  item.value = undefined;
  evidence.value = [];
  error.value = undefined;
  try {
    const id = String(route.params.id);
    const x = await events.one(id, controller.signal);
    if (current !== generation) return;
    if (!x) throw { code: "NOT_FOUND", message: "未找到该事件", status: 404 };
    item.value = x;
    const list = await events.evidence(id, controller.signal);
    if (current === generation) evidence.value = list;
  } catch (e) {
    if (current === generation && (e as Error).name !== "AbortError")
      error.value = err(e);
  }
}
async function toggle(id: string) {
  open.value = open.value === id ? undefined : id;
  await nextTick();
  document.getElementById(`quote-${id}`)?.focus();
}
watch(() => [route.params.id, route.query.demo], load, { immediate: true });
onBeforeUnmount(() => {
  generation++;
  controller?.abort();
});
</script>
<template>
  <section class="stream">
    <p>
      <RouterLink :to="{ path: '/', query: { demo: $route.query.demo } }"
        >返回事件</RouterLink
      >
    </p>
    <div v-if="error" class="card error" role="alert">
      {{ error.status === 404 ? "事件不存在" : error.message }}
      <button v-if="error.status !== 404" @click="load">重试</button
      ><RouterLink
        v-else
        :to="{ path: '/', query: { demo: $route.query.demo } }"
        >返回事件库</RouterLink
      >
    </div>
    <article v-else-if="item">
      <p class="meta">
        {{ item.event_date || "日期未知" }} · {{ item.date_precision }}
      </p>
      <h1 class="page-title">{{ item.title_zh }}</h1>
      <p class="answer-body">{{ item.summary_zh }}</p>
      <h2>相关实体</h2>
      <p class="row">
        <span v-for="entity in item.entities" :key="entity" class="pill">{{
          entity
        }}</span>
      </p>
      <section class="evidence-layer">
        <h2>来源与摘录</h2>
        <p v-if="isDemo()" class="demo">以下摘录为合成演示。</p>
        <p v-if="!item.evidence_count" class="meta">此事件没有关联证据。</p>
        <div
          v-for="x in item.evidence_count ? evidence : []"
          :key="x.id"
          class="evidence-item"
        >
          <button
            :aria-expanded="open === x.id"
            :aria-controls="`quote-${x.id}`"
            @click="toggle(x.id)"
          >
            {{ open === x.id ? "收起" : "展开" }}摘录：{{ x.title }}
          </button>
          <blockquote v-if="open === x.id" :id="`quote-${x.id}`" tabindex="-1">
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
          >
        </div>
      </section>
    </article>
    <p v-else>正在加载详情…</p>
  </section>
</template>
