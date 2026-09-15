import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import "./style.css";
import "./home-timeline.css";
import "./compact-controls.css";
import "./themes.css";
import "./timeline-preview.css";
import { initTheme } from "./themes";
initTheme();
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/type-preview", component: () => import("./TypePreview.vue") },
    { path: "/timeline-preview", component: () => import("./HomePage.vue") },
    { path: "/brand-preview", component: () => import("./BrandPreview.vue") },
    { path: "/", component: () => import("./HomePage.vue") },
    { path: "/events/:id", component: () => import("./DetailPage.vue") },
    { path: "/ask", component: () => import("./AskPage.vue") },
    { path: "/preview", component: () => import("./preview/PreviewHome.vue") },
    { path: "/preview/ask", component: () => import("./AskPage.vue"), props: { streamlined: true } },
    { path: "/ingest", component: () => import("./IngestPage.vue") },
  ],
});
createApp(App).use(router).mount("#app");
