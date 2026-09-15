<script setup lang="ts">
import { computed } from "vue";
import { locale, translate as tr } from "./locale";
import type { ResearchDataset } from "./api";
const props = defineProps<{ dataset: ResearchDataset }>();
const fields = computed(() => props.dataset.fields.slice(0, 8));
const labels: Record<string, [string, string]> = {
  date: ["日期", "Date"], category: ["分类", "Category"], count: ["事件数", "Events"],
  period: ["区间", "Period"], from: ["起始日期", "From"], to: ["截止日期", "To"],
  days: ["天数", "Days"], daily_average: ["日均事件数", "Events per day"],
};
const categories: Record<string, [string, string]> = {
  model_release: ["模型发布", "Model releases"], agent_tool: ["智能体工具", "Agent tools"],
  framework_sdk: ["框架与 SDK", "Frameworks & SDKs"], research: ["研究", "Research"],
  product: ["产品", "Products"], industry: ["产业", "Industry"],
};
const label = (field: string) => labels[field] ? tr(...labels[field]) : field;
function value(field: string, item: unknown) {
  if (typeof item === "number") return item.toLocaleString(locale.value === "en" ? "en-US" : "zh-CN", { maximumFractionDigits: 3 });
  if (field === "category" && typeof item === "string" && categories[item]) return tr(...categories[item]);
  if (field === "period") return item === "first" ? tr("基期", "Baseline") : tr("比较期", "Comparison");
  return item == null ? tr("未提供", "Not provided") : String(item);
}
</script>

<template>
  <div class="research-dataset">
    <p class="meta">{{ tr("本轮数据库快照 · 单位：事件", "This round’s database snapshot · Unit: events") }}</p>
    <div class="dataset-scroll" tabindex="0" :aria-label="tr('统计依据数据表', 'Statistical evidence table')">
      <table>
        <caption class="sr-only">{{ tr("回答引用的数据", "Data cited by the answer") }}</caption>
        <thead><tr><th v-for="field in fields" :key="field" scope="col">{{ label(field) }}</th></tr></thead>
        <tbody><tr v-for="(row, index) in dataset.rows" :key="index"><td v-for="field in fields" :key="field">{{ value(field, row[field]) }}</td></tr></tbody>
      </table>
      <p v-if="!dataset.rows.length" class="meta">{{ tr("当前范围无对应记录。", "No matching records in this scope.") }}</p>
    </div>
    <p v-if="dataset.excluded_unverified_dates" class="meta">{{ tr(`未纳入 ${dataset.excluded_unverified_dates} 条日期未核验记录。`, `${dataset.excluded_unverified_dates} records with unverified dates were excluded.`) }}</p>
    <p v-if="dataset.zero_baseline" class="meta">{{ tr("基期为零，不计算增长百分比。", "The baseline is zero; percentage growth is undefined.") }}</p>
    <p class="meta">{{ tr("仅反映本站收录情况。", "Reflects records collected by this site only.") }}</p>
  </div>
</template>

<style scoped>
.research-dataset { min-width: 0; }
.dataset-scroll { max-width: 100%; overflow-x: auto; margin-block: .6rem; }
table { width: 100%; border-collapse: collapse; font-size: .875rem; font-variant-numeric: tabular-nums; }
th, td { padding: .45rem .65rem .45rem 0; text-align: start; white-space: nowrap; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
</style>
