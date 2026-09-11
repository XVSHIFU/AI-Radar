<script setup lang="ts">
import { computed } from "vue";
import { dataMode, isDemo } from "./api";
const link = (path: string, demo: unknown) =>
  demo ? path + "?demo=" + encodeURIComponent(String(demo)) : path;
const viewKey = computed(
  () => location.pathname + `|${isDemo() ? "demo" : "api"}`,
);
</script>
<template>
  <header>
    <RouterLink :to="link('/', $route.query.demo)" class="brand"
      >◒ AI 革新雷达</RouterLink
    >
    <nav>
      <RouterLink :to="link('/', $route.query.demo)">事件</RouterLink
      ><RouterLink :to="link('/ask', $route.query.demo)">问答</RouterLink
      ><RouterLink :to="link('/ingest', $route.query.demo)"
        >采集管理</RouterLink
      >
    </nav>
    <RouterLink v-if="!isDemo()" :to="$route.path + '?demo=1'" class="switch"
      >演示模式</RouterLink
    ><RouterLink v-else :to="$route.path" class="switch">连接服务</RouterLink>
  </header>
  <p v-if="isDemo()" class="demo" role="note">
    前端模拟：仅用于交互演示，不代表真实服务结果。
  </p>
  <p v-else-if="dataMode === 'fixture'" class="demo" role="note">
    后端合成数据：服务端返回的 fixture，不代表真实新闻或采集结果。
  </p>
  <main><RouterView :key="viewKey" /></main>
</template>
