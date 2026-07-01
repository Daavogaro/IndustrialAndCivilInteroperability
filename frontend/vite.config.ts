import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev-only proxy target. Defaults to the host backend; override with
// VITE_API_TARGET (e.g. http://backend:8000) when running the dev server
// inside a container. Production is served by nginx, not this proxy.
const apiTarget = process.env.VITE_API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
