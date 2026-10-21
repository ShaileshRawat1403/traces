import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const api = process.env.TRACES_API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { host: "127.0.0.1", port: 5173, proxy: { "/api": api } },
  preview: { host: "127.0.0.1", proxy: { "/api": api } },
  build: { outDir: "dist", sourcemap: true },
});
