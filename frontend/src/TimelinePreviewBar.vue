<script setup lang="ts">
import { tx } from './reading-locale';
import { useRoute } from 'vue-router';
const route = useRoute();
</script>
<template>
 <div class="fusion-toolbar">
  <span>{{ tx("舒展时间线", "Reading timeline") }}</span>
  <RouterLink :to="{ path: '/type-preview', query: route.query }">{{ tx("比较 5 组字体", "Compare 5 type styles") }}</RouterLink>
  <RouterLink :to="{ path: '/', query: route.query }">{{ tx("返回首页", "Homepage") }}</RouterLink>
 </div>
</template>
