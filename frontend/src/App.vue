<script setup lang="ts">
import { dataMode, isDemo } from "./api";
const link = (path: string, demo: unknown) =>
  demo ? path + "?demo=" + encodeURIComponent(String(demo)) : path;
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
  <p v-if="isDemo() || dataMode === 'fixture'" class="demo" role="note">
    演示数据：仅用于界面体验，不代表真实新闻、回答或采集记录。
  </p>
  <main><RouterView /></main>
</template>
