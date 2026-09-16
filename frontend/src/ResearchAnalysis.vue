<script setup lang="ts">
import type { Citation } from "./api";
import ResearchDataset from "./ResearchDataset.vue";
import { translate as tr } from "./locale";
defineProps<{ source: Citation }>();
</script>
<template>
  <section>
    <p>{{ tr('分析输出', 'Analysis output') }}</p>
    <pre class="analysis-output">{{ source.analysis?.stdout || tr('未输出文字，结果见分析文件。', 'No text output; see the analysis files.') }}</pre>
    <p v-if="source.analysis?.stdout_truncated" class="meta">{{ tr('文字输出过长，此处仅显示前段。', 'Text output was shortened for display.') }}</p>
    <details v-if="source.analysis?.code"><summary>{{ tr('查看分析代码', 'View analysis code') }}</summary><pre class="analysis-output">{{ source.analysis.code }}</pre></details>
    <p>{{ tr('输入数据', 'Input data') }}</p>
    <ResearchDataset v-for="dataset in source.datasets || (source.dataset ? [source.dataset] : [])" :key="dataset.dataset_id" :dataset="dataset" />
  </section>
</template>
<style scoped>
.analysis-output { max-height: 14rem; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-size: .875rem; line-height: 1.6; }
</style>
