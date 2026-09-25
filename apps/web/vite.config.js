import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy so the frontend can call /api/* without CORS friction; on
// staging the API Gateway (BRD/PRD Section 18.6) performs this role instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },
});
