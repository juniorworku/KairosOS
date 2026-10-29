import { defineConfig } from "vitest/config";
import { fileURLToPath, URL } from "node:url";
import { VitePWA } from "vite-plugin-pwa";
import react from "@vitejs/plugin-react";
const target = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
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
        background_color: "#f7f4ef",
        theme_color: "#f7f4ef",
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
        clientsClaim: true,
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/healthz/, /^\/readyz/],
        globPatterns: ["**/*.{js,css,html,png,svg,ico,woff2}"],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  server: {
    strictPort: true,
    proxy: { "/healthz": target, "/readyz": target, "/api": target },
  },
  preview: {
    strictPort: true,
    headers: {
      "Content-Security-Policy":
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "same-origin",
      "X-Frame-Options": "DENY",
    },
  },
  test: {
    // Bound jsdom/IndexedDB contention on development and small CI hosts.
    maxWorkers: 2,
    exclude: ["e2e/**", "node_modules/**"],
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
  },
});
