<script setup lang="ts">
import { useRoute } from 'vue-router';
import BrandCandidate from './BrandCandidate.vue';
import { brandStudies, previewBrand } from './brand-preview';
const route = useRoute();
</script>
<template>
  <section class="brand-studies">
    <header class="brand-studies-heading">
      <div><h1>给雷达一个自己的标记</h1><p>8 款原创 SVG。点击后，左侧品牌会同步预览；颜色跟随当前主题。</p></div>
      <RouterLink :to="{ path: '/timeline-preview', query: route.query.demo === '1' ? { demo: '1' } : {} }">放进时间线看效果</RouterLink>
    </header>
    <div class="brand-study-list">
      <button v-for="study in brandStudies" :key="study.id" class="brand-study" :aria-pressed="previewBrand === study.id" @click="previewBrand = study.id">
        <div class="brand-study-art"><BrandCandidate :name="study.id" /><span v-if="previewBrand === study.id" class="brand-study-selected">预览中</span></div>
        <div class="brand-study-copy"><h2>{{ study.name }}</h2><p>{{ study.note }}</p>
          <div class="brand-study-lockup"><BrandCandidate :name="study.id" /><strong>AI 革新雷达</strong></div>
          <div class="brand-study-tab"><BrandCandidate :name="study.id" /><span>AI 动态 · 标签页 16px</span></div>
        </div>
      </button>
    </div>
    <p class="brand-studies-note">建议先看 03「时间脉络」与 04「观察窗口」：前者呼应时间线，后者在小尺寸上更鲜明。这里只改变预览，正式图标待你选定后替换。</p>
  </section>
</template>
