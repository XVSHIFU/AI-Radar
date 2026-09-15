<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { dataMode } from "./api";
import AssistantPanel from "./AssistantPanel.vue";
import ThemeWheel from "./ThemeWheel.vue";
import "./preview/preview.css";
const route = useRoute();
const demoEnabled = computed(() => route.query.demo === "1");
const previewEnabled = computed(() => route.path.startsWith("/preview"));
const adminEnabled = computed(() => route.path === "/ingest");
const link = (path: string) => (demoEnabled.value ? `${path}?demo=1` : path);
const viewKey = computed(
  () => `${route.path}|${demoEnabled.value ? "demo" : "api"}`,
);
</script>
<template>
  <div v-if="previewEnabled" class="preview-shell">
    <header class="preview-shell-header">
      <RouterLink :to="link('/preview')" class="preview-shell-brand">AI 革新雷达 <span>预览版</span></RouterLink>
      <nav class="preview-shell-nav" aria-label="预览导航">
        <RouterLink :to="link('/preview')">AI 动态</RouterLink>
        <RouterLink :to="link('/preview/ask')">统计与问答</RouterLink>
      </nav>
      <RouterLink :to="link('/')" class="preview-shell-return">返回原版</RouterLink>
    </header>
    <p v-if="demoEnabled && !adminEnabled" class="demo" role="note">前端模拟：仅用于交互演示，不代表真实服务结果。</p>
    <p v-else-if="dataMode === 'fixture'" class="demo" role="note">后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。</p>
    <main class="preview-shell-main"><RouterView :key="viewKey" /></main>
    <footer class="preview-shell-footer"><RouterLink :to="'/ingest'">维护入口</RouterLink></footer>
  </div>
  <div v-else class="app-shell">
    <header class="app-rail">
      <RouterLink :to="link('/')" class="brand"
        ><svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 12h16M12 4v16" /></svg
        >AI 革新雷达</RouterLink
      >
      <nav>
        <RouterLink :to="link('/')"
          ><svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 5h14v14H5zM8 9h8M8 13h5" /></svg
          >事件</RouterLink
        >
        <RouterLink :to="link('/ask')"
          ><svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 5h14v10H9l-4 4z" /></svg
          >统计与问答</RouterLink
        >
        <RouterLink :to="'/ingest'"
          ><svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="6" y="10" width="12" height="10" rx="1" /><path d="M9 10V7a3 3 0 0 1 6 0v3M12 14v2" /></svg
          >管理员后台</RouterLink
        >
      </nav>
      <div class="rail-footer">
      <ThemeWheel />
      <RouterLink
        v-if="!demoEnabled && !adminEnabled"
        :to="route.path + '?demo=1'"
        class="switch"
        >演示模式</RouterLink
      >
      <RouterLink v-else-if="!adminEnabled" :to="route.path" class="switch">连接服务</RouterLink>
      <div v-if="route.path !== '/ingest'" id="assistant-mobile-slot" aria-label="研究助手入口"></div>
      </div>

    </header>

    <div class="app-content">
      <p v-if="demoEnabled && !adminEnabled" class="demo" role="note">
        前端模拟：仅用于交互演示，不代表真实服务结果。
      </p>
      <p v-else-if="dataMode === 'fixture'" class="demo" role="note">
        后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。
      </p>
      <main><RouterView :key="viewKey" /></main><AssistantPanel v-if="route.path !== '/ingest'" />
    </div>
  </div>
</template>
