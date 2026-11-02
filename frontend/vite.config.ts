import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev only: Django is reached through this server so everything is one origin.
const django = "http://app:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": django,
      "/admin": django,
      "/static": django,
    },
  },
});
