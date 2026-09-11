<script setup lang="ts">
import { ref } from "vue";
import { ask, err, isDemo, type AskResult } from "./api";
import { parseSse } from "./sse";
let generation = 0;
const question = ref(""),
  running = ref(false),
  controller = ref<AbortController>(),
  result = ref<AskResult>(),
  error = ref<ReturnType<typeof err>>(),
  status = ref(""),
  tokens = ref(""),
  sources = ref<
    { index: number; title: string; source_url: string; quote_text: string }[]
  >([]),
  expanded = ref<number>();
const stream = () =>
  new ReadableStream<Uint8Array>({
    start(c) {
      const text =
        'event: status\ndata: {"phase":"retrieving"}\n\nevent: token\ndata: {"text":"这是明确标注的模拟问答回答。[2]"}\n\nevent: sources\ndata: {"items":[{"index":2,"title":"合成演示来源","source_url":"https://example.invalid/demo","quote_text":"合成段落摘录"}]}\n\nevent: done\ndata: {"status":"completed","scope_total":1,"retrieved_count":1,"summarized_count":1,"coverage":"demo"}\n\n';
      for (const x of [text.slice(0, 47), text.slice(47)])
        setTimeout(() => c.enqueue(new TextEncoder().encode(x)), 20);
      setTimeout(() => c.close(), 60);
    },
  });
async function submit() {
  const current = ++generation;
  controller.value?.abort();
  controller.value = new AbortController();
  result.value = undefined;
  error.value = undefined;
  tokens.value = "";
  sources.value = [];
  running.value = true;
  try {
    if (isDemo()) {
      for await (const e of parseSse(stream(), controller.value.signal)) {
        if (e.event === "status") status.value = "模拟流：正在检索";
        if (e.event === "token") tokens.value += JSON.parse(e.data).text;
        if (e.event === "sources") sources.value = JSON.parse(e.data).items;
        if (e.event === "done")
          status.value =
            JSON.parse(e.data).status === "completed"
              ? "模拟流已完成"
              : "模拟流失败";
      }
      return;
    }
    status.value = "正在检索并汇总…";
    result.value = await ask(
      {
        question: question.value,
        filters: {},
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        answer_mode: "concise",
        client_request_id: crypto.randomUUID(),
      },
      controller.value.signal,
    );
    status.value = "已完成";
  } catch (e) {
    if (current !== generation) return;
    if ((e as Error).name === "AbortError")
      status.value = "已取消，未自动重试。";
    else error.value = err(e);
  } finally {
    if (current === generation) running.value = false;
  }
}
</script>
<template>
  <section>
    <h1>研究问答</h1>
    <label>问题<textarea v-model="question" class="control" rows="4" /></label>
    <p class="meta">条件：全部分类 · 无日期限制</p>
    <div class="row">
      <button :disabled="running || !question" @click="submit">开始分析</button
      ><button v-if="running" @click="controller?.abort()">取消</button>
    </div>
    <p aria-live="polite">{{ status }}</p>
    <div v-if="error" class="card error">{{ error.message }}</div>
    <article v-if="tokens" class="card">
      <p v-if="isDemo()" class="demo">模拟流，仅用于演示，不代表模型已验证。</p>
      <h2>回答</h2>
      <p>{{ tokens }}</p>
      <div v-for="s in sources" :key="s.index">
        <button @click="expanded = expanded === s.index ? undefined : s.index">
          [{{ s.index }}] {{ s.title }}
        </button>
        <blockquote v-if="expanded === s.index">{{ s.quote_text }}</blockquote>
        <a :href="s.source_url" target="_blank" rel="noopener">打开来源</a>
      </div>
      <p class="meta">完整匹配 1 · 取回 1 · 总结 1 · 覆盖：demo</p>
    </article>
    <article v-if="result" class="card">
      <h2>回答</h2>
      <p>{{ result.answer || "没有可回答的资料。" }}</p>
      <p class="meta">
        完整匹配 {{ result.scope_total }} · 取回 {{ result.retrieved_count }} ·
        总结 {{ result.summarized_count }} · 引用 {{ result.citation_count }} ·
        覆盖：{{ result.coverage }}
      </p>
    </article>
  </section>
</template>
