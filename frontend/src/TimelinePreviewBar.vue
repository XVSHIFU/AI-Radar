<script setup lang="ts">
import { tx } from './reading-locale';
import { useRoute } from 'vue-router';
import { previewDensity } from './brand-preview';
const route = useRoute();
</script>
<template>
  <div class="fusion-toolbar" :aria-label='tx("时间线预览设置", "Timeline preview settings")'>
    <span>{{ tx("时间线融合预览", "Timeline preview") }}</span>
    <div class="fusion-density" role="group" :aria-label='tx("阅读密度", "Reading density")'>
      <button :aria-pressed="previewDensity === 'reading'" @click="previewDensity = 'reading'">{{ tx("舒展", "Reading") }}</button>
      <button :aria-pressed="previewDensity === 'compact'" @click="previewDensity = 'compact'">{{ tx("紧凑", "Compact") }}</button>
    </div>
    <RouterLink :to="{ path: '/brand-preview', query: route.query.demo === '1' ? { demo: '1' } : {} }">{{ tx("比较 8 款图标", "Compare 8 marks") }}</RouterLink>
    <RouterLink :to="{ path: '/', query: route.query.demo === '1' ? { demo: '1' } : {} }">{{ tx("返回当前首页", "Current homepage") }}</RouterLink>
  </div>
</template>
