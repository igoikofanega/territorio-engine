import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// El navegador llama a /api/* (mismo origen) y Vite lo reenvía al contenedor `api`
// por la red interna de Docker. Así el front no depende del puerto del host de la API
// (evita choques) y no hace falta CORS. PROXY_TARGET permite usarlo fuera de Docker.
const target = process.env.PROXY_TARGET ?? "http://api:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
