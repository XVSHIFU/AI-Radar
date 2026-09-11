<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import fixture from '../../../contracts/prototype-events.json'

type Category = 'model_release' | 'agent_tool' | 'framework_sdk' | 'research' | 'product' | 'industry'
type EventItem = (typeof fixture.items)[number] & { category: Category }
type Result = { items: EventItem[]; total: number; total_relation: 'eq'; as_of: string }

const categories: { value: Category; label: string }[] = [
  { value: 'model_release', label: '模型发布' },
  { value: 'agent_tool', label: '智能体工具' },
  { value: 'framework_sdk', label: '框架与 SDK' },
  { value: 'research', label: '研究进展' },
  { value: 'product', label: '产品动态' },
  { value: 'industry', label: '行业观察' },
]
const categoryLabel = Object.fromEntries(categories.map((item) => [item.value, item.label])) as Record<Category, string>
const pageSize = 8
const query = ref('')
const category = ref<Category | ''>('')
const dateFrom = ref('')
const dateTo = ref('')
const page = ref(1)
const filtersOpen = ref(false)
const loading = ref(true)
const error = ref('')
const result = ref<Result>({ items: [], total: 0, total_relation: 'eq', as_of: '2026-09-12 18:00 CST' })
let controller: AbortController | null = null
let timer: ReturnType<typeof setTimeout> | null = null

function fetchEvents(signal: AbortSignal): Promise<Result> {
  return new Promise((resolve, reject) => {
    timer = setTimeout(() => {
      if (signal.aborted) return reject(new DOMException('Aborted', 'AbortError'))
      const term = query.value.trim().toLocaleLowerCase()
      const filtered = (fixture.items as EventItem[])
        .filter((item) => !term || `${item.title_zh} ${item.summary_zh} ${item.entities.join(' ')}`.toLocaleLowerCase().includes(term))
        .filter((item) => !category.value || item.category === category.value)
        .filter((item) => !dateFrom.value || (!!item.event_date && item.event_date >= dateFrom.value))
        .filter((item) => !dateTo.value || (!!item.event_date && item.event_date <= dateTo.value))
        .sort((a, b) => (b.event_date ?? '').localeCompare(a.event_date ?? '') || a.id.localeCompare(b.id))
      const start = (page.value - 1) * pageSize
      resolve({ items: filtered.slice(start, start + pageSize), total: filtered.length, total_relation: 'eq', as_of: '2026-09-12 18:00 CST' })
    }, 420)
  })
}

async function load() {
  controller?.abort()
  if (timer) clearTimeout(timer)
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    result.value = await fetchEvents(controller.signal)
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === 'AbortError') return
    error.value = '演示数据暂时无法读取，请保留当前条件后重试。'
  } finally {
    if (!controller.signal.aborted) loading.value = false
  }
}

let debounce: ReturnType<typeof setTimeout> | null = null
watch([query, category, dateFrom, dateTo], () => {
  page.value = 1
  if (debounce) clearTimeout(debounce)
  debounce = setTimeout(load, 260)
})
watch(page, load)

const totalPages = computed(() => Math.max(1, Math.ceil(result.value.total / pageSize)))
const grouped = computed(() => {
  const groups = new Map<string, EventItem[]>()
  for (const item of result.value.items) {
    const key = item.event_date ?? '日期待确认'
    groups.set(key, [...(groups.get(key) ?? []), item])
  }
  return [...groups.entries()]
})
const hasFilters = computed(() => Boolean(query.value || category.value || dateFrom.value || dateTo.value))
const dateRangeInvalid = computed(() => Boolean(dateFrom.value && dateTo.value && dateFrom.value > dateTo.value))

function clearFilters() {
  query.value = ''
  category.value = ''
  dateFrom.value = ''
  dateTo.value = ''
}

function simulateFailure() {
  controller?.abort()
  if (timer) clearTimeout(timer)
  loading.value = false
  error.value = '演示数据暂时无法读取，请保留当前条件后重试。'
}

onBeforeUnmount(() => {
  controller?.abort()
  if (timer) clearTimeout(timer)
  if (debounce) clearTimeout(debounce)
})
load()
</script>

<template>
  <div class="min-h-screen">
    <header class="border-b border-[var(--line)] bg-white">
      <div class="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <a href="/" class="brand focus-ring" aria-label="AI 革新雷达首页">
          <span class="brand-mark" aria-hidden="true">R</span>
          <span>AI 革新雷达</span>
        </a>
        <nav aria-label="主导航" class="flex items-center gap-1 text-sm font-semibold">
          <a class="nav-link active focus-ring" href="/">资讯</a>
          <a class="nav-link focus-ring" href="/ask">问答</a>
          <a class="nav-link focus-ring" href="/ingest">采集管理</a>
        </nav>
      </div>
    </header>

    <main class="mx-auto max-w-[1280px] px-4 py-8 sm:px-6 lg:px-8 lg:py-12">
      <section class="mb-8 border-b-2 border-[var(--ink)] pb-8" aria-labelledby="page-title">
        <div class="eyebrow">INTELLIGENCE EDITION · 2026.09.12</div>
        <div class="mt-3 grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <h1 id="page-title" class="headline">今天，AI 世界发生了什么</h1>
            <p class="mt-3 max-w-2xl text-[15px] leading-7 text-[var(--muted)]">按事实日期梳理模型、工具与研究进展，帮你快速找到值得继续追踪的线索。</p>
          </div>
          <div class="demo-note" role="note"><span aria-hidden="true">◇</span><div><strong>合成数据演示</strong><br><span>32 条 UI fixture，不代表真实新闻</span></div></div>
        </div>
      </section>

      <section aria-labelledby="search-heading" class="search-panel">
        <h2 id="search-heading" class="sr-only">搜索和筛选资讯</h2>
        <label for="search" class="search-wrap">
          <svg aria-hidden="true" viewBox="0 0 24 24"><path d="m21 21-4.35-4.35m2.35-5.65a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z" /></svg>
          <input id="search" v-model="query" type="search" aria-label="搜索全部资讯" placeholder="搜索标题、摘要或实体，例如 DeepSeek" autocomplete="off" />
        </label>
        <button class="filter-toggle focus-ring md:hidden" type="button" :aria-expanded="filtersOpen" aria-controls="filters" @click="filtersOpen = !filtersOpen">筛选条件 <span>{{ filtersOpen ? '收起' : '展开' }}</span></button>
        <div id="filters" class="filter-grid" :class="{ 'is-collapsed': !filtersOpen }">
          <label><span>分类</span><select v-model="category"><option value="">全部分类</option><option v-for="item in categories" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label><span>起始日期</span><input v-model="dateFrom" type="date" :aria-invalid="dateRangeInvalid" /></label>
          <label><span>结束日期</span><input v-model="dateTo" type="date" :aria-invalid="dateRangeInvalid" /></label>
          <button v-if="hasFilters" type="button" class="clear-button focus-ring" @click="clearFilters">清除全部</button>
        </div>
      </section>

      <div class="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section aria-labelledby="result-heading" :aria-busy="loading">
          <div class="result-bar">
            <h2 id="result-heading"><span class="result-number">{{ loading ? '—' : result.total }}</span> 条匹配资讯</h2>
            <span>精确总数 · 按日期倒序</span>
          </div>
          <div class="sr-only" aria-live="polite">{{ loading ? '正在更新结果' : error ? error : `已找到 ${result.total} 条匹配资讯` }}</div>

          <div v-if="dateRangeInvalid" class="state-card" role="alert">
            <div class="state-icon error" aria-hidden="true">!</div><h3>日期范围有误</h3><p>起始日期不能晚于结束日期。请调整任一日期后重试。</p>
          </div>
          <div v-else-if="loading" class="space-y-0" aria-label="正在加载演示数据">
            <div v-for="n in 4" :key="n" class="skeleton-row"><div class="skeleton h-3 w-20"></div><div class="flex-1"><div class="skeleton h-5 w-3/4"></div><div class="skeleton mt-3 h-3 w-full"></div><div class="skeleton mt-2 h-3 w-2/3"></div></div></div>
          </div>
          <div v-else-if="error" class="state-card" role="alert">
            <div class="state-icon error" aria-hidden="true">!</div><h3>读取失败</h3><p>{{ error }}</p>
            <div class="mt-5 flex justify-center gap-3"><button class="primary-button focus-ring" type="button" @click="load">重新尝试</button><button class="secondary-button focus-ring" type="button" @click="clearFilters">清除条件</button></div>
          </div>
          <div v-else-if="!result.items.length" class="state-card">
            <div class="state-icon" aria-hidden="true">⌕</div><h3>这个范围内没有演示事件</h3><p>当前关键词、分类和日期的组合没有匹配结果。条件会继续保留。</p><button class="primary-button mt-5 focus-ring" type="button" @click="clearFilters">清除筛选</button>
          </div>
          <div v-else>
            <section v-for="([date, items], groupIndex) in grouped" :key="date" class="date-group" :aria-labelledby="`date-${groupIndex}`">
              <div class="date-rule"><h3 :id="`date-${groupIndex}`">{{ date }}</h3><span>{{ items.length }} 条</span></div>
              <article v-for="item in items" :key="item.id" class="event-row">
                <div class="event-meta"><span>{{ categoryLabel[item.category] }}</span><span class="importance">重要度 {{ item.importance }}/5</span></div>
                <div class="min-w-0">
                  <a class="event-title focus-ring" :href="`/events/${item.id}`">{{ item.title_zh }} <span aria-hidden="true">↗</span></a>
                  <p class="event-summary">{{ item.summary_zh }}</p>
                  <div class="evidence-line"><span>{{ item.source_count }} 个来源</span><span aria-hidden="true">·</span><span>{{ item.evidence_count ? `${item.evidence_count} 条证据已关联` : '暂无证据摘录' }}</span></div>
                </div>
              </article>
            </section>
            <nav v-if="totalPages > 1" aria-label="结果分页" class="pagination">
              <button class="page-button focus-ring" type="button" :disabled="page === 1" @click="page--">← 上一页</button>
              <span>第 <strong>{{ page }}</strong> / {{ totalPages }} 页</span>
              <button class="page-button focus-ring" type="button" :disabled="page === totalPages" @click="page++">下一页 →</button>
            </nav>
          </div>
        </section>

        <aside class="space-y-6" aria-label="全库态势">
          <section class="aside-card"><div class="eyebrow">全库态势</div><div class="stat"><strong>32</strong><span>合成事件总数</span></div><div class="stat"><strong>6</strong><span>覆盖分类</span></div><div class="aside-foot">统计范围：synthetic-ui-v1 全库<br>更新于 {{ result.as_of }}</div></section>
          <section class="aside-card"><div class="eyebrow">浏览说明</div><p class="mt-4 text-sm leading-6 text-[var(--muted)]">日期采用事件事实日期。来源数量表示已关联的合成来源，证据状态单独展示。</p><button type="button" class="failure-link focus-ring" @click="simulateFailure">预览失败状态</button></section>
        </aside>
      </div>
    </main>
    <footer><div class="mx-auto flex max-w-[1280px] flex-wrap justify-between gap-2 px-4 py-6 sm:px-6 lg:px-8"><span>AI 革新雷达 · 首页候选 A</span><span>仅供界面评测，不构成新闻信息</span></div></footer>
  </div>
</template>
