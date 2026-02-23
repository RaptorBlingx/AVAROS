import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
    global: "globalThis",
  },
  build: {
    sourcemap: false,
    outDir: "dist",
    emptyOutDir: false,
    cssCodeSplit: false,
    lib: {
      entry: "widget/index.tsx",
      name: "AvarosWidget",
      formats: ["iife"],
      fileName: () => "avaros-widget.js",
    },
    target: "esnext",
    minify: "esbuild",
    rollupOptions: {
      output: {
        intro:
          'var process = globalThis.process || { env: { NODE_ENV: "production" } }; globalThis.process = process;',
        inlineDynamicImports: true,
      },
    },
  },
});
