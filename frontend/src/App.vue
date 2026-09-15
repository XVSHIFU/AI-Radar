<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { dataMode } from "./api";
import AssistantPanel from "./AssistantPanel.vue";
import RadarMark from "./RadarMark.vue";
import BrandCandidate from "./BrandCandidate.vue";
import TimelinePreviewBar from "./TimelinePreviewBar.vue";
import { previewBrand } from "./brand-preview";
import ThemeWheel from "./ThemeWheel.vue";
import "./preview/preview.css";
import { t } from "./locale";
const route = useRoute();
const demoEnabled = computed(() => route.query.demo === "1");
const previewEnabled = computed(() => route.path.startsWith("/preview"));
const fusionEnabled = computed(() => ["/", "/timeline-preview"].includes(route.path));
const brandEnabled = computed(() => route.path === "/brand-preview");
const adminEnabled = computed(() => route.path === "/ingest");
const link = (path: string) => (demoEnabled.value ? `${path}?demo=1` : path);
const viewKey = computed(
  () => `${route.path}|${demoEnabled.value ? "demo" : "api"}`,
);
</script>
<template>
  <div v-if="previewEnabled" class="preview-shell">
    <header class="preview-shell-header">
      <RouterLink :to="link('/preview')" class="preview-shell-brand"><RadarMark /> AI 革新雷达 <span>预览版</span></RouterLink>
      <nav class="preview-shell-nav" aria-label="预览导航">
        <RouterLink :to="link('/preview')">AI 动态</RouterLink>
        <RouterLink :to="link('/preview/ask')">{{ t("ask") }}</RouterLink>
      </nav>
      <RouterLink :to="link('/')" class="preview-shell-return">返回原版</RouterLink>
    </header>
    <p v-if="demoEnabled && !adminEnabled" class="demo" role="note">{{ t("simulation") }}</p>
    <p v-else-if="dataMode === 'fixture' && !adminEnabled" class="demo" role="note">{{ t("fixture") }}</p>
    <main class="preview-shell-main"><RouterView :key="viewKey" /></main>
    <footer class="preview-shell-footer"><RouterLink :to="'/ingest'">{{ t("maintenance") }}</RouterLink></footer>
  </div>
  <div v-else class="app-shell" :class="{ 'fusion-preview': fusionEnabled }">
    <header class="app-rail">
      <RouterLink :to="link('/')" class="brand"
        ><BrandCandidate v-if="brandEnabled" :name="previewBrand" /><RadarMark v-else />AI 革新雷达</RouterLink
      >
      <nav>
        <RouterLink :to="link('/')"
          ><svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 5h14v14H5zM8 9h8M8 13h5" /></svg
          >{{ t("events") }}</RouterLink
        >
        <RouterLink :to="link('/ask')"
          ><svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 5h14v10H9l-4 4z" /></svg
          >{{ t("ask") }}</RouterLink
        >
        <RouterLink :to="'/ingest'"
          ><svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="6" y="10" width="12" height="10" rx="1" /><path d="M9 10V7a3 3 0 0 1 6 0v3M12 14v2" /></svg
          >{{ t("admin") }}</RouterLink
        >
      </nav>
      <div class="rail-footer">
      <ThemeWheel />
      <RouterLink
        v-if="!demoEnabled && !adminEnabled"
        :to="route.path + '?demo=1'"
        class="switch"
        >{{ t("demo") }}</RouterLink
      >
      <RouterLink v-else-if="!adminEnabled" :to="route.path" class="switch">{{ t("service") }}</RouterLink>
      <div id="assistant-mobile-slot" aria-label="研究助手入口"></div>
      </div>

    </header>

    <div class="app-content">
      <p v-if="demoEnabled && !adminEnabled" class="demo" role="note">
        {{ t("simulation") }}
      </p>
      <p v-else-if="dataMode === 'fixture' && !adminEnabled" class="demo" role="note">
        {{ t("fixture") }}
      </p>
      <main><TimelinePreviewBar v-if="route.path === '/timeline-preview'" /><RouterView :key="viewKey" /></main>
    </div>
  </div>
  <AssistantPanel />
</template>
