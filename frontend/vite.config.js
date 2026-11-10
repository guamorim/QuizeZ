import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = "http://127.0.0.1:8000";

export default defineConfig(({ command, mode }) => {
  const useVercelRouting = mode === "vercel";

  return {
    base: command === "build" && !useVercelRouting ? "/static/react/" : "/",
    plugins: [react()],
    build: {
      outDir: useVercelRouting ? "dist" : "../static/react",
      emptyOutDir: true,
    },
    server: useVercelRouting ? undefined : {
      proxy: {
        "/rooms": backend,
        "/ws": { target: backend, ws: true },
        "/static": backend,
      },
    },
  };
});
