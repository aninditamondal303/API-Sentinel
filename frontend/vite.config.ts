import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The browser only ever talks to its own origin. /api and /actuator/health are forwarded to the
// Spring Boot backend (by this dev server locally, by nginx in Docker), so no CORS is needed and the
// analyzer is never reachable from the browser.
const backend = process.env.APISENTINEL_BACKEND_URL ?? "http://127.0.0.1:8080";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: false },
      // Health only (exact path or its groups), matching the nginx rules.
      "^/actuator/health(/.*)?$": { target: backend, changeOrigin: false },
    },
  },
  // assetsInlineLimit 0: no data: URIs, so fonts and images satisfy the CSP (font-src 'self').
  build: { sourcemap: false, chunkSizeWarningLimit: 900, assetsInlineLimit: 0 },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
