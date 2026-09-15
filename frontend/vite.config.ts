import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
const target = process.env.RADAR_API_TARGET || "http://127.0.0.1:8000";
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      "/api": { target, changeOrigin: true, configure(proxy) {
        proxy.on("proxyReq", (outgoing, incoming) => {
          // This Vite listener is the edge: client-supplied forwarding headers are untrusted.
          for (const header of ["forwarded", "x-forwarded-for", "x-forwarded-proto", "x-real-ip", "x-forwarded-host"]) outgoing.removeHeader(header);
          if (incoming.socket.remoteAddress) outgoing.setHeader("x-forwarded-for", incoming.socket.remoteAddress);
          outgoing.setHeader("x-forwarded-proto", "http");
        });
      } },
      "/health": { target, changeOrigin: true },
    },
  },
});
