<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { dataMode } from "./api";
const route = useRoute();
const demoEnabled = computed(() => route.query.demo === "1");
const link = (path: string) => (demoEnabled.value ? `${path}?demo=1` : path);
const viewKey = computed(
  () => `${route.path}|${demoEnabled.value ? "demo" : "api"}`,
);
</script>
<template>
  <header>
    <RouterLink :to="link('/')" class="brand">◒ AI 革新雷达</RouterLink>
    <nav>
      <RouterLink :to="link('/')">事件</RouterLink
      ><RouterLink :to="link('/ask')">问答</RouterLink
      ><RouterLink :to="link('/ingest')">采集管理</RouterLink>
    </nav>
    <RouterLink v-if="!demoEnabled" :to="route.path + '?demo=1'" class="switch"
      >演示模式</RouterLink
    ><RouterLink v-else :to="route.path" class="switch">连接服务</RouterLink>
  </header>
  <p v-if="demoEnabled" class="demo" role="note">
    前端模拟：仅用于交互演示，不代表真实服务结果。
  </p>
  <p v-else-if="dataMode === 'fixture'" class="demo" role="note">
    后端合成数据：服务端返回的 fixture，不代表真实新闻或采集结果。
  </p>
  <main><RouterView :key="viewKey" /></main>
</template>
