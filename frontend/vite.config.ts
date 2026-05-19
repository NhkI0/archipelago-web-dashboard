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
