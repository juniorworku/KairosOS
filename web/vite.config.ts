import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
const target = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
export default defineConfig({
  plugins: [react()],
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
