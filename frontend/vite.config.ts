import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "/app/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8080",
      "/login": "http://localhost:8080",
      "/login-required": "http://localhost:8080"
    }
  },
  build: {
    outDir: "../src/mm_post_bot/web/static/spa",
    emptyOutDir: true
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts"
  }
});
