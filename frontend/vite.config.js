import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Vite server forwards /api/* to the FastAPI backend, so the browser
// talks to a single origin (no CORS setup needed locally). In production the frontend is
// either served by the same domain (Vercel rewrites / FastAPI static files) or configured
// with VITE_API_BASE_URL to call a separately hosted API.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_DEV_API_PROXY || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.js"],
  },
});
