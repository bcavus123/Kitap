import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build çıktısı FastAPI'nin StaticFiles ile sunduğu app/web'e gider; /app/ altında servis edilir.
export default defineConfig({
  plugins: [react()],
  base: "/app/",
  build: {
    outDir: "../app/web",
    emptyOutDir: true,
  },
  server: {
    // Dev modunda (npm run dev) API çağrılarını backend'e yönlendir
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
