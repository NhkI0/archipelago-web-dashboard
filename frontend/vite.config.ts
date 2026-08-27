import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Set VITE_API_TARGET=https://archipelago.nguengant.fr (or another host)
// to proxy /api and /ws to a remote backend instead of localhost. Without
// it, dev mode talks to a local backend on :8080.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const httpTarget = env.VITE_API_TARGET || "http://localhost:8080";
  const wsTarget = httpTarget.replace(/^http/, "ws");
  const remote = httpTarget.startsWith("https://");

  return {
    // Relative, not absolute: this same build is served both at "/"
    // (self-hosted) and at "/<uuid>/" (hosted rooms, prefix stripped by
    // Caddy before proxying) -- absolute asset paths break the latter
    // (verified on the real VPS 2026-08-26: index.html loaded fine at
    // /<uuid>/ but its <script>/<link> tags requested /assets/... at the
    // domain root instead of /<uuid>/assets/..., 404ing against the
    // supervisor instead of the room).
    base: "./",
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: httpTarget,
          changeOrigin: remote,
          secure: remote,
        },
        "/ws": {
          target: wsTarget,
          ws: true,
          changeOrigin: remote,
          secure: remote,
        },
      },
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
  };
});
