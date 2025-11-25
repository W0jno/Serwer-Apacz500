import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      // ⚠️ KLUCZOWA ZMIANA: To wymusza sprawdzanie zmian w plikach
      usePolling: true,
    },
    host: true, // Potrzebne dla Dockera
    strictPort: true,
    port: 5173,
  },
});
