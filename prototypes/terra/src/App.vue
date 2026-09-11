<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import fixture from '../../../contracts/prototype-events.json'

type Category = 'model_release' | 'agent_tool' | 'framework_sdk' | 'research' | 'product' | 'industry'
type EventItem = (typeof fixture.items)[number]
type ViewState = 'ready' | 'loading' | 'error'

const labels: Record<string, string> = {
  model_release: '模型发布', agent_tool: '智能体工具', framework_sdk: '框架与 SDK',
  research: '研究', product: '产品', industry: '产业',
}
const categories = Object.entries(labels) as [Category, string][]
const query = ref('')
const category = ref<Category | ''>('')
const dateFrom = ref('')
const dateTo = ref('')
const page = ref(1)
const pageSize = 6
const state = ref<ViewState>('loading')
const simulatedError = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

const filtered = computed(() => fixture.items.filter((item) => {
  const text = `${item.title_zh} ${item.summary_zh} ${item.entities.join(' ')}`.toLowerCase()
  return (!query.value || text.includes(query.value.trim().toLowerCase())) &&
    (!category.value || item.category === category.value) &&
    (!dateFrom.value || (item.event_date ?? '') >= dateFrom.value) &&
    (!dateTo.value || (item.event_date ?? '') <= dateTo.value)
}))
const pageCount = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize)))
const visible = computed(() => filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const activeFilters = computed(() => [
  query.value && `关键词：${query.value}`,
  category.value && `分类：${labels[category.value]}`,
  dateFrom.value && `起始：${dateFrom.value}`,
  dateTo.value && `截止：${dateTo.value}`,
].filter(Boolean) as string[])

function request() {
  if (timer) clearTimeout(timer)
  state.value = 'loading'
  timer = setTimeout(() => { state.value = simulatedError.value ? 'error' : 'ready' }, 420)
}
function reset() { query.value = ''; category.value = ''; dateFrom.value = ''; dateTo.value = ''; page.value = 1 }
function retry() { simulatedError.value = false; request() }
function formatDate(date: string | null) { return date ? date.replaceAll('-', '.') : '日期待定' }
function stars(count: number) { return '●'.repeat(count) + '○'.repeat(5 - count) }
watch([query, category, dateFrom, dateTo], () => { page.value = 1; request() })
watch(pageCount, () => { if (page.value > pageCount.value) page.value = pageCount.value })
onMounted(request)
</script>

<template>
  <div class="min-h-screen bg-[var(--bg)] text-[var(--ink)]">
    <header class="border-b border-[var(--line)] bg-white">
      <div class="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <a href="#" class="flex items-center gap-3 font-semibold tracking-tight"><span class="grid h-9 w-9 place-items-center rounded-xl bg-[var(--brand)] text-lg text-white">◒</span><span>AI 革新雷达</span></a>
        <nav aria-label="主导航" class="flex gap-5 text-sm text-[var(--muted)]"><a class="font-medium text-[var(--brand)]" href="#events">事件库</a><a href="#method">研究方法</a><a href="#about">关于</a></nav>
        <span class="rounded-full bg-teal-50 px-3 py-1 text-xs font-medium text-[var(--brand)]">研究工作台</span>
      </div>
    </header>

    <main class="mx-auto max-w-[1280px] px-4 py-7 sm:px-6 lg:py-10">
      <section class="mb-6 grid gap-5 lg:grid-cols-[1fr_300px] lg:items-end">
        <div><p class="mb-3 text-xs font-semibold tracking-[0.16em] text-[var(--brand)]">GLOBAL AI INTELLIGENCE</p><h1 class="text-3xl font-semibold tracking-tight sm:text-4xl">把每天的变化，放进可验证的脉络。</h1><p class="mt-3 max-w-2xl text-[var(--muted)]">按事实日期整理的 AI 事件研究库，供团队筛选、比对和追溯。</p></div>
        <aside class="rounded-xl border border-[var(--line)] bg-white p-4" aria-label="数据范围"><p class="text-xs font-medium text-[var(--muted)]">当前研究范围</p><p class="mt-1 text-lg font-semibold">全球 · 6 个主题</p><p class="mt-2 text-xs text-[var(--muted)]">数据更新时间：2026.09.12</p></aside>
      </section>

      <div class="mb-5 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="note"><span aria-hidden="true">ⓘ</span><span>正在展示 <strong>synthetic-ui-v1 合成 UI fixture</strong>（32 条），不代表真实新闻或采集结果。</span></div>

      <section class="grid gap-6 lg:grid-cols-[276px_minmax(0,1fr)_250px]" id="events">
        <aside class="h-fit rounded-xl border border-[var(--line)] bg-white p-4 lg:sticky lg:top-4">
          <div class="mb-4 flex items-center justify-between"><h2 class="font-semibold">检索条件</h2><button class="text-sm text-[var(--brand)] underline-offset-2 hover:underline" @click="reset">清除</button></div>
          <label class="block text-sm font-medium">关键词<input v-model="query" class="control mt-2" placeholder="搜索标题、摘要、实体" /></label>
          <fieldset class="mt-5"><legend class="text-sm font-medium">分类</legend><div class="mt-2 grid gap-1"> <label v-for="([key, label]) in categories" :key="key" class="choice"><input v-model="category" type="radio" :value="key" name="category" /><span>{{ label }}</span></label><label class="choice"><input v-model="category" type="radio" value="" name="category" /><span>全部分类</span></label></div></fieldset>
          <fieldset class="mt-5"><legend class="text-sm font-medium">事实日期</legend><label class="mt-2 block text-xs text-[var(--muted)]">从<input v-model="dateFrom" class="control mt-1" type="date" /></label><label class="mt-3 block text-xs text-[var(--muted)]">至<input v-model="dateTo" class="control mt-1" type="date" /></label></fieldset>
          <button class="mt-5 w-full rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-[var(--danger)]" @click="simulatedError = true; request()">演示加载错误</button>
        </aside>

        <section aria-label="事件结果">
          <div class="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h2 class="text-lg font-semibold">研究事件</h2><p class="mt-1 text-sm text-[var(--muted)]" aria-live="polite">{{ state === 'loading' ? '正在更新匹配结果…' : `精确匹配 ${filtered.length} 条事件` }}</p></div><p class="text-xs text-[var(--muted)]">按日期与 ID 稳定排序</p></div>
          <div v-if="activeFilters.length" class="mb-4 flex flex-wrap gap-2" aria-label="已采用条件"><span v-for="filter in activeFilters" :key="filter" class="rounded-full bg-teal-50 px-3 py-1 text-xs text-[var(--brand)]">{{ filter }}</span></div>
          <div v-if="state === 'loading'" class="grid gap-3" aria-busy="true"><div v-for="n in 4" :key="n" class="h-36 animate-pulse rounded-xl border border-[var(--line)] bg-white"></div></div>
          <div v-else-if="state === 'error'" class="rounded-xl border border-red-200 bg-white p-7 text-center" role="alert"><p class="text-lg font-semibold">结果暂时无法加载</p><p class="mt-2 text-sm text-[var(--muted)]">已保留你的检索条件。此处是用于验收的模拟服务错误。</p><button class="mt-4 rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white" @click="retry">重新加载</button></div>
          <div v-else-if="!visible.length" class="rounded-xl border border-[var(--line)] bg-white p-7 text-center"><p class="text-lg font-semibold">这个范围内没有事件</p><p class="mt-2 text-sm text-[var(--muted)]">合成数据覆盖 2026.09.06 至 2026.09.12；可调整日期或清除条件。</p><button class="mt-4 text-sm font-medium text-[var(--brand)] underline" @click="reset">清除全部条件</button></div>
          <div v-else class="grid gap-3"><article v-for="item in visible" :key="item.id" class="event-card"><div class="flex flex-wrap items-center justify-between gap-2 text-xs"><span class="font-medium text-[var(--brand)]">{{ labels[item.category] }}</span><span class="text-[var(--muted)]">{{ formatDate(item.event_date) }}</span></div><h3 class="mt-2 text-lg font-semibold leading-snug"><a :href="`/events/${item.id}`" class="focus-ring hover:text-[var(--brand)]">{{ item.title_zh }}</a></h3><p class="mt-2 text-sm leading-6 text-[var(--muted)]">{{ item.summary_zh }}</p><div class="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--line)] pt-3 text-xs text-[var(--muted)]"><span :aria-label="`重要度 ${item.importance} / 5`" class="tracking-widest text-[var(--warning)]">{{ stars(item.importance) }}</span><span>{{ item.source_count }} 个来源 · {{ item.evidence_count ? `${item.evidence_count} 条已核验证据` : '待补证据' }}</span><a :href="`/events/${item.id}`" class="focus-ring font-medium text-[var(--brand)]">查看详情 <span aria-hidden="true">→</span></a></div></article></div>
          <nav v-if="state === 'ready' && filtered.length > pageSize" class="mt-6 flex items-center justify-between border-t border-[var(--line)] pt-4" aria-label="分页"><button class="pager" :disabled="page === 1" @click="page--">← 上一页</button><span class="text-sm text-[var(--muted)]">第 {{ page }} / {{ pageCount }} 页</span><button class="pager" :disabled="page === pageCount" @click="page++">下一页 →</button></nav>
        </section>

        <aside class="h-fit rounded-xl border border-[var(--line)] bg-white p-4 lg:sticky lg:top-4"><p class="text-xs font-semibold tracking-wider text-[var(--brand)]">今日研读</p><h2 class="mt-2 text-lg font-semibold">从信号到判断</h2><p class="mt-2 text-sm leading-6 text-[var(--muted)]">每条记录保留分类、事实日期、来源数量与证据状态，帮助研究者先确认事实，再建立观点。</p><dl class="mt-5 grid grid-cols-2 gap-3 border-t border-[var(--line)] pt-4"><div><dt class="text-xs text-[var(--muted)]">事件库</dt><dd class="mt-1 text-xl font-semibold">32</dd></div><div><dt class="text-xs text-[var(--muted)]">主题</dt><dd class="mt-1 text-xl font-semibold">6</dd></div></dl></aside>
      </section>
    </main>
  </div>
</template>
