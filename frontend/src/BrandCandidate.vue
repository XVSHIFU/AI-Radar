<script setup lang="ts">
import { computed } from 'vue';
import { brandStudies } from './brand-preview';
const props = defineProps<{ name: string }>();
const study = computed(() => brandStudies.find(s => s.id === props.name) || brandStudies[0]);
</script>
<template>
  <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path v-for="(d, i) in study.paths" :key="i" :d="d" />
    <circle v-for="(dot, i) in study.dots" :key="'dot'+i" :cx="dot[0]" :cy="dot[1]" :r="dot[2]" fill="currentColor" stroke="var(--paper)" stroke-width="1" />
  </svg>
</template>
