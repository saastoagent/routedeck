import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const agentApiProxyTarget =
  process.env.VITE_AGENT_API_PROXY_TARGET ?? "http://127.0.0.1:8098";
const usePolling = process.env.VITE_USE_POLLING === "true";

export default defineConfig({
  plugins: [react()],
  server: {
    ...(usePolling
      ? { watch: { usePolling: true, interval: 250 } }
      : {}),
    proxy: {
      "/api/medusa-agent": agentApiProxyTarget,
      "/api/routedeck": agentApiProxyTarget,
    },
  },
});
