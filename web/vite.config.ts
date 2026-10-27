import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";
import react from "@vitejs/plugin-react";
const target = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "prompt",
      injectRegister: false,
      manifest: {
        name: "Kairos",
        short_name: "Kairos",
        start_url: "/today",
        display: "standalone",
        background_color: "#f7f8f5",
        theme_color: "#345d45",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/icon-maskable.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/healthz/, /^\/readyz/],
        globPatterns: ["**/*.{js,css,html,png,svg,ico}"],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  server: {
    strictPort: true,
    proxy: { "/healthz": target, "/readyz": target, "/api": target },
  },
  test: {
    exclude: ["e2e/**", "node_modules/**"],
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
  },
});
