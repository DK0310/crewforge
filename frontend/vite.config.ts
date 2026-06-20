import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The FastAPI backend (CORS already open). Proxy keeps the SSE stream on the
// same origin in dev so EventSource and fetch share cookies/headers cleanly.
const BACKEND = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/agents": BACKEND,
      "/crews": BACKEND,
      "/runs": BACKEND,
      "/health": BACKEND,
    },
  },
});
