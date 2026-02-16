import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const envDir = new URL(".", import.meta.url).pathname;
  const env = loadEnv(mode, envDir, "");
  const target = env.VITE_API_PROXY_TARGET || "http://localhost:8080";

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
