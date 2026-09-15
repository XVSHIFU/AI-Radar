<script setup lang="ts">
import { categoryLabel, countLabel, formatDate, precisionLabel, translate as tr } from "./reader-locale";
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
    if (!x) throw { code: "NOT_FOUND", message: tr("未找到该事件", "Event not found"), status: 404 };
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
        >{{ tr("返回事件", "Back to events") }}</RouterLink
      >
    </p>
    <div v-if="error" class="card error" role="alert">
      {{ error.status === 404 ? tr("事件不存在", "Event not found") : error.message }}
      <button v-if="error.status !== 404" @click="load">{{ tr("重试", "Retry") }}</button
      ><RouterLink
        v-else
        :to="{ path: '/', query: { demo: $route.query.demo } }"
        >{{ tr("返回事件库", "Back to event library") }}</RouterLink
      >
    </div>
    <article v-else-if="item">
      <p class="meta">
        {{ item.event_date ? formatDate(item.event_date) : tr("日期未知", "Date unknown") }} · {{ precisionLabel(item.date_precision) }}
      </p>
      <h1 class="page-title">{{ item.title_zh }}</h1>
      <p class="answer-body">{{ item.summary_zh }}</p>
      <p class="meta">{{ categoryLabel(item.category) }} · {{ tr("重要度 {value}/5", "Importance {value}/5", { value: item.importance }) }} · {{ countLabel(item.source_count, "个来源", "source") }}</p>
      <h2>{{ tr("相关实体", "Related entities") }}</h2>
      <p class="row">
        <span v-for="entity in item.entities" :key="entity" class="pill">{{
          entity
        }}</span>
      </p>
      <section class="evidence-layer">
        <h2>{{ tr("来源与摘录", "Sources & excerpts") }}</h2>
        <p v-if="isDemo()" class="demo">{{ tr("以下摘录为合成演示。", "The following excerpts are synthetic demo data.") }}</p>
        <p v-if="!item.evidence_count" class="meta">{{ tr("此事件没有关联证据。", "This event has no linked evidence.") }}</p>
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
            {{ open === x.id ? tr("收起摘录", "Collapse excerpt") : tr("展开摘录", "Expand excerpt") }}：{{ x.title }}
          </button>
          <blockquote v-if="open === x.id" :id="`quote-${x.id}`" tabindex="-1">
            {{ x.quote_text }}
            <footer class="meta">
              {{ tr("版本 {version} · 段落 {paragraph}", "Version {version} · Paragraph {paragraph}", { version: x.article_version_id, paragraph: x.paragraph_id }) }}
            </footer>
          </blockquote>
          <a
            v-if="safe(x.source_url)"
            :href="x.source_url"
            target="_blank"
            rel="noopener"
            >{{ tr("打开来源", "Open source") }}</a
          >
        </div>
      </section>
    </article>
    <p v-else>{{ tr("正在加载详情…", "Loading details…") }}</p>
  </section>
</template>
