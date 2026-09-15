<script setup lang="ts">
import { tx } from './reading-locale';
import { useRoute } from 'vue-router';
import BrandCandidate from './BrandCandidate.vue';
import { brandStudies, previewBrand } from './brand-preview';
const route = useRoute();
const english: Record<string, [string, string]> = {
 signal: ['01 · Signal ticks', 'One signal and three outward marks. A light, direct reading of radar.'],
 orbit: ['02 · Intersecting orbits', 'Two paths share a center, bringing different sources together.'],
 thread: ['03 · Timeline thread', 'A continuous spine with three nodes echoes the event timeline.'],
 aperture: ['04 · Observation window', 'An open frame with a point of discovery. Clear even at favicon size.'],
 horizon: ['05 · Knowledge horizon', 'A signal rises over the horizon: welcoming and open.'],
 lens: ['06 · Focus', 'A focusing ring and a forward line of sight. Simple and purposeful.'],
 leaves: ['07 · New branches', 'New knowledge grows from one trunk. A softer, organic direction.'],
 relay: ['08 · Knowledge relay', 'Two linked open loops connect events, sources and evidence.'],
};
</script>
<template>
  <section class="brand-studies">
    <header class="brand-studies-heading">
      <div><h1>{{ tx("给雷达一个自己的标记", "A mark of its own") }}</h1><p>{{ tx("8 款原创 SVG。点击后，左侧品牌会同步预览；颜色跟随当前主题。", "Eight original SVG studies. Choose one to preview in the navigation, using your current theme.") }}</p></div>
      <RouterLink :to="{ path: '/timeline-preview', query: route.query.demo === '1' ? { demo: '1' } : {} }">{{ tx("放进时间线看效果", "See it on the timeline") }}</RouterLink>
    </header>
    <div class="brand-study-list">
      <button v-for="study in brandStudies" :key="study.id" class="brand-study" :aria-pressed="previewBrand === study.id" @click="previewBrand = study.id">
        <div class="brand-study-art"><BrandCandidate :name="study.id" /><span v-if="previewBrand === study.id" class="brand-study-selected">{{ tx("预览中", "Previewing") }}</span></div>
        <div class="brand-study-copy"><h2>{{ tx(study.name, english[study.id][0]) }}</h2><p>{{ tx(study.note, english[study.id][1]) }}</p>
          <div class="brand-study-lockup"><BrandCandidate :name="study.id" /><strong>{{ tx("AI 革新雷达", "AI Radar") }}</strong></div>
          <div class="brand-study-tab"><BrandCandidate :name="study.id" /><span>{{ tx("AI 动态 · 标签页 16px", "AI updates · 16px browser tab") }}</span></div>
        </div>
      </button>
    </div>
    <p class="brand-studies-note">{{ tx("建议先看 03「时间脉络」与 04「观察窗口」：前者呼应时间线，后者在小尺寸上更鲜明。这里只改变预览，正式图标待你选定后替换。", "Start with 03 Timeline thread or 04 Observation window: one echoes the timeline, the other reads clearly at small sizes. Selection only changes this preview.") }}</p>
  </section>
</template>
