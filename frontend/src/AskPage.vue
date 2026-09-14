<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from "vue";
import {
  ask,
  err,
  isDemo,
  type AskResult,
  type Category,
  type Citation,
} from "./api";
import { parseSse } from "./sse";
import { askView } from "./ask-result";
import { queryPlanFrom, type QueryPlan } from "./query-plan";
const props = defineProps<{ streamlined?: boolean }>();
let generation = 0;
const question = ref(""),
  category = ref<Category | "">(""),
  from = ref(""),
  to = ref(""),
  running = ref(false),
  controller = ref<AbortController>(),
  result = ref<AskResult>(),
  error = ref<ReturnType<typeof err>>(),
  status = ref(""),
  tokens = ref(""),
  sources = ref<Citation[]>([]),
  metrics = ref<
    Pick<
      AskResult,
      | "scope_total"
      | "retrieved_count"
      | "summarized_count"
      | "citation_count"
      | "coverage"
    > & { status?: string }
  >(),
  expanded = ref<number>(),
  plan = ref<QueryPlan>();
const conditionSummary = computed(() => {
  const selected = category.value ? categoryName[category.value] || category.value : "全部分类";
  const dates = from.value || to.value ? ` · ${from.value || "不限"} 至 ${to.value || "不限"}` : "";
  return `${selected}${dates}`;
});
const categoryName: Record<string, string> = {
  model_release: "模型发布",
  agent_tool: "智能体工具",
  framework_sdk: "框架与 SDK",
  research: "研究",
  product: "产品",
  industry: "产业",
};
const errorGuidance: Record<string, string> = {
  MODEL_UNAVAILABLE: "生成模型尚未配置，已显示可用的检索范围。",
  QUERY_UNSUPPORTED: "当前问题包含暂不支持的检索表达。",
  CLARIFICATION_REQUIRED: "需要先澄清检索条件后才能继续。",
};
const errorDescription = (value: ReturnType<typeof err>) =>
  errorGuidance[value.code]
    ? `${errorGuidance[value.code]} ${value.message}`
    : value.message;
let timers: number[] = [];
const validUrl = (url: string) => /^https?:\/\//i.test(url);
const invalid = () => Boolean(from.value && to.value && from.value > to.value);
function slowStream() {
  let control: ReadableStreamDefaultController<Uint8Array>;
  const emit = (x: string, ms: number) =>
    timers.push(
      window.setTimeout(() => control.enqueue(new TextEncoder().encode(x)), ms),
    );
  return new ReadableStream<Uint8Array>({
    start(c) {
      control = c;
      emit('event: status\ndata: {"phase":"retrieving"}\n\n', 150);
      emit('event: token\ndata: {"text":"这是"}\n\n', 450);
      emit('event: token\ndata: {"text":"明确标注的模拟回答。[2]"}\n\n', 850);
      emit(
        'event: sources\ndata: {"items":[{"index":2,"title":"合成演示来源","source_url":"https://example.invalid/demo","quote_text":"合成段落摘录","paragraph_id":"demo-p-001"}]}\n\n',
        1150,
      );
      emit(
        'event: done\ndata: {"status":"completed","scope_total":1,"retrieved_count":1,"summarized_count":1,"citation_count":1,"coverage":"complete"}\n\n',
        1450,
      );
      timers.push(window.setTimeout(() => c.close(), 1600));
    },
    cancel() {
      timers.forEach(clearTimeout);
      timers = [];
    },
  });
}
function cancel() {
  generation++;
  controller.value?.abort();
  timers.forEach(clearTimeout);
  timers = [];
  plan.value = undefined;
  running.value = false;
  status.value = "已取消，未自动重试。";
}
async function submit() {
  const current = ++generation;
  controller.value?.abort();
  timers.forEach(clearTimeout);
  if (invalid()) {
    error.value = { code: "INVALID_DATE", message: "起始日期不能晚于截止日期" };
    return;
  }
  controller.value = new AbortController();
  result.value = undefined;
  plan.value = undefined;
  error.value = undefined;
  tokens.value = "";
  sources.value = [];
  metrics.value = undefined;
  running.value = true;
  const filters = {
    category: category.value || undefined,
    date_from: from.value || undefined,
    date_to: to.value || undefined,
  };
  try {
    if (isDemo()) {
      for await (const e of parseSse(slowStream(), controller.value.signal)) {
        if (current !== generation) return;
        if (e.event === "status") status.value = "模拟流：正在检索";
        if (e.event === "token") tokens.value += JSON.parse(e.data).text;
        if (e.event === "sources")
          sources.value = JSON.parse(e.data).items as Citation[];
        if (e.event === "done") {
          metrics.value = JSON.parse(e.data) as Pick<
            AskResult,
            | "scope_total"
            | "retrieved_count"
            | "summarized_count"
            | "citation_count"
            | "coverage"
          >;
          status.value =
            metrics.value.status === "completed"
              ? "模拟流已完成"
              : "模拟流失败";
        }
      }
    } else {
      status.value = "正在检索并汇总…";
      const x = await ask(
        {
          question: question.value,
          filters,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          answer_mode: "concise",
          client_request_id: crypto.randomUUID(),
        },
        controller.value.signal,
      );
      if (current !== generation) return;
      plan.value = queryPlanFrom(x);
      const view = askView(x);
      result.value = x;
      sources.value = view.citations;
      metrics.value = x;
      status.value = view.status;
    }
  } catch (e) {
    if (current !== generation) return;
    status.value =
      (e as Error).name === "AbortError" ? "已取消，未自动重试。" : "";
    if ((e as Error).name !== "AbortError") {
      error.value = err(e);
      plan.value = queryPlanFrom(e);
    }
  } finally {
    if (current === generation) running.value = false;
  }
}
async function toggle(i: number) {
  expanded.value = expanded.value === i ? undefined : i;
  await nextTick();
  document.getElementById(`citation-${i}`)?.focus();
}
onBeforeUnmount(() => {
  generation++;
  controller.value?.abort();
  timers.forEach(clearTimeout);
});
</script>
<template>
  <section class="reading-shell ask-layout" :class="{ 'ask-layout--streamlined': streamlined }">
    <div class="stream">
      <h1 class="page-title">研究问答</h1>
      <label
        >问题<textarea
          v-model="question"
          class="control"
          rows="5"
          placeholder="输入需要核查的 AI 进展问题"
        />
      </label>
      <details v-if="streamlined" class="ask-conditions ask-conditions--details">
        <summary>研究条件（可选）<span v-if="category || from || to">：{{ conditionSummary }}</span></summary>
        <div class="ask-conditions__fields">
          <label>分类<select v-model="category" class="control"><option value="">全部</option><option v-for="(label, key) in categoryName" :value="key">{{ label }}</option></select></label>
          <label>从<input v-model="from" type="date" class="control" /></label><label>至<input v-model="to" type="date" class="control" /></label>
        </div>
      </details>
      <section v-else class="ask-conditions">
        <h2>研究条件</h2>
        <label>分类<select v-model="category" class="control"><option value="">全部</option><option v-for="(label, key) in categoryName" :value="key">{{ label }}</option></select></label>
        <label>从<input v-model="from" type="date" class="control" /></label><label>至<input v-model="to" type="date" class="control" /></label>
      </section>
      <div class="row">
        <button
          class="primary"
          :disabled="running || !question"
          @click="submit"
        >
          开始分析</button
        ><button v-if="running" @click="cancel">取消</button>
      </div>
      <p v-if="streamlined" class="ask-streamline-note">回答中的事实可回查到保存的来源段落。</p>
      <p aria-live="polite" class="meta">{{ status }}</p>
      <div v-if="error" class="card error" role="alert">
        <strong>{{ error.code }}</strong
        >：{{ errorDescription(error) }}
      </div>
      <section
        v-if="plan"
        class="card query-plan"
        aria-label="检索范围"
        data-testid="query-plan"
      >
        <h2>检索范围</h2>
        <p>业务日期：{{ plan.business_date }} · 时区：{{ plan.timezone }}</p>
        <p>
          分类：{{
            plan.filters.category
              ? categoryName[plan.filters.category] || plan.filters.category
              : "全部分类"
          }}
          · 日期：{{ plan.filters.date_from || "不限" }} 至
          {{ plan.filters.date_to || "不限" }}（起止日期均包含）
        </p>
        <p>
          实体：{{
            plan.filters.entity_ids?.length
              ? `已采用 ${plan.filters.entity_ids.length} 个实体条件（${plan.filters.entity_match === "all" ? "同时匹配" : "任一匹配"}）`
              : "未限定实体"
          }}
        </p>
        <p v-if="plan.requires_clarification">
          需要澄清：<span
            v-for="c in plan.clarification_candidates"
            :key="c.label"
            >{{ c.label }}
          </span>
        </p>
        <p v-if="plan.free_text">未理解限制：{{ plan.free_text }}</p>
        <p v-if="plan.entity_roles?.length">
          实体角色：{{
            plan.entity_roles
              .map((role) => (role === "subject" ? "主体" : "产品"))
              .join("、")
          }}
        </p>
        <ul v-if="plan.warnings.length">
          <li v-for="w in plan.warnings" :key="w">{{ w }}</li>
        </ul>
      </section>
      <article
        v-if="tokens || result"
        class="evidence-layer"
        data-testid="ask-answer"
      >
        <p v-if="isDemo()" class="demo">模拟流，仅用于演示。</p>
        <h2>回答</h2>
        <p class="answer-body">{{ tokens || result?.answer }}</p>
        <div v-for="s in sources" :key="s.index" class="evidence-item">
          <button
            :aria-expanded="expanded === s.index"
            :aria-controls="`citation-${s.index}`"
            @click="toggle(s.index)"
          >
            [{{ s.index }}] {{ s.title }}
          </button>
          <blockquote
            v-if="expanded === s.index"
            :id="`citation-${s.index}`"
            tabindex="-1"
          >
            {{ s.quote_text || "无段落摘录" }}
            <footer class="meta">
              段落 {{ s.paragraph_id || "未提供" }} · 来源版本未提供
            </footer>
          </blockquote>
          <a
            v-if="validUrl(s.source_url)"
            :href="s.source_url"
            target="_blank"
            rel="noopener"
            >打开来源</a
          >
        </div>
        <p v-if="result?.answer_status === 'no_answer'">没有可回答的资料。</p>
        <p v-if="metrics?.coverage === 'partial'" class="meta">
          覆盖不完整：答案仅基于部分匹配资料。
        </p>
        <p v-if="metrics" class="meta tabular">
          完整匹配 {{ metrics.scope_total }} · 取回
          {{ metrics.retrieved_count }} · 总结 {{ metrics.summarized_count }} ·
          引用 {{ metrics.citation_count }} · 覆盖：{{ metrics.coverage }}
        </p>
      </article>
    </div>
    <aside v-if="!streamlined" class="context-panel">
      <h2>研究说明</h2>
      <p class="meta">回答中的事实应回查到保存的来源段落。</p>
    </aside>
  </section>
</template>
