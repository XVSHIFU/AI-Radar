<script setup lang="ts">
import { useRoute } from 'vue-router';
import { previewDensity } from './brand-preview';
const route = useRoute();
</script>
<template>
  <div class="fusion-toolbar" aria-label="时间线预览设置">
    <span>时间线融合预览</span>
    <div class="fusion-density" role="group" aria-label="阅读密度">
      <button :aria-pressed="previewDensity === 'reading'" @click="previewDensity = 'reading'">舒展</button>
      <button :aria-pressed="previewDensity === 'compact'" @click="previewDensity = 'compact'">紧凑</button>
    </div>
    <RouterLink :to="{ path: '/brand-preview', query: route.query.demo === '1' ? { demo: '1' } : {} }">比较 8 款图标</RouterLink>
    <RouterLink :to="{ path: '/', query: route.query.demo === '1' ? { demo: '1' } : {} }">返回当前首页</RouterLink>
  </div>
</template>
