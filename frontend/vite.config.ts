import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev only: Django is reached through this server so everything is one origin.
// Keep the browser's Host header: ALLOWED_HOSTS and the CSRF origin check use it.
const django = { target: "http://app:8000", changeOrigin: false };

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Vite's default host check stays on: only localhost (reached over SSH).
    proxy: {
      "/api": django,
      "/admin": django,
      "/static": django,
    },
  },
});
