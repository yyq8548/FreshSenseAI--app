import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("@azure/msal")) return "identity";
          if (id.includes("@fluentui") || id.includes("@griffel")) return "fluent";
          if (id.includes("node_modules/react")) return "react";
          return undefined;
        },
      },
    },
  },
  server: {
    // Microsoft Entra permits HTTP callbacks for localhost during local
    // development, but rejects the equivalent 127.0.0.1 SPA redirect URI.
    host: "localhost",
    port: 5173,
  },
  preview: {
    host: "localhost",
    port: 4173,
  },
});
