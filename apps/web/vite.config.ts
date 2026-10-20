import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    watch: { usePolling: true, interval: 500 },
    headers: { "Cache-Control": "no-store" },
  },
  preview: { host: "0.0.0.0", port: 3000 },
  build: {
    // Rollup's default tree-shaking is pathologically slow on this Windows/OneDrive workspace.
    // The console is an internal application, so a slightly larger deterministic bundle is preferred.
    rollupOptions: { treeshake: false },
  },
});
