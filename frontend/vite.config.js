import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = "http://127.0.0.1:8000";

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/react/" : "/",
  plugins: [react()],
  build: {
    outDir: "../static/react",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/rooms": backend,
      "/ws": { target: backend, ws: true },
      "/static": backend,
    },
  },
}));
