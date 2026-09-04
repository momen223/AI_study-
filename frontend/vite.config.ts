import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API is served from http://127.0.0.1:5001 (see api/app.py).
// The UI proxies /api/* to that Flask server during development so the
// browser talks to a single origin, avoiding CORS friction.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5001",
        changeOrigin: true,
      },
    },
  },
});
