<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { dataMode } from "./api";
import "./preview/preview.css";
const route = useRoute();
const demoEnabled = computed(() => route.query.demo === "1");
const previewEnabled = computed(() => route.path.startsWith("/preview"));
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
        <RouterLink :to="link('/preview/ask')">问答</RouterLink>
        <RouterLink :to="link('/ingest')">维护入口</RouterLink>
      </nav>
      <RouterLink :to="link('/')" class="preview-shell-return">返回原版</RouterLink>
    </header>
    <p v-if="demoEnabled" class="demo" role="note">前端模拟：仅用于交互演示，不代表真实服务结果。</p>
    <p v-else-if="dataMode === 'fixture'" class="demo" role="note">后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。</p>
    <main class="preview-shell-main"><RouterView :key="viewKey" /></main>
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
          >问答</RouterLink
        >
        <RouterLink :to="link('/ingest')"
          ><svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 5h12v14H6zM9 9h6M9 13h6" /></svg
          >采集管理</RouterLink
        >
      </nav>
      <RouterLink
        v-if="!demoEnabled"
        :to="route.path + '?demo=1'"
        class="switch"
        >演示模式</RouterLink
      >
      <RouterLink v-else :to="route.path" class="switch">连接服务</RouterLink>
    </header>
    <div class="app-content">
      <p v-if="demoEnabled" class="demo" role="note">
        前端模拟：仅用于交互演示，不代表真实服务结果。
      </p>
      <p v-else-if="dataMode === 'fixture'" class="demo" role="note">
        后端合成数据：仅用于界面展示，不代表真实新闻或采集结果。
      </p>
      <main><RouterView :key="viewKey" /></main>
    </div>
  </div>
</template>
