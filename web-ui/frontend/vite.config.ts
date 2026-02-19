import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const envDir = new URL(".", import.meta.url).pathname;
  const env = loadEnv(mode, envDir, "");
  // 8080 is commonly occupied by Keycloak in local stacks.
  // AVAROS dev override exposes web-ui on 8081 by default.
  const target = env.VITE_API_PROXY_TARGET || "http://localhost:8081";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        util: "util/",
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": target,
        "/health": target,
      },
    },
    test: {
      environment: "node",
      include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    },
  };
});
