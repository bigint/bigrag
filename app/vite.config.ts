import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    tanstackRouter({
      autoCodeSplitting: true,
      enableRouteGeneration: false,
      quoteStyle: "double",
      routeTreeFileHeader: ["// @ts-nocheck"],
      semicolons: true,
      target: "react",
    }),
    react(),
  ],
  resolve: {
    alias: {
      "@": new URL("./src", import.meta.url).pathname,
    },
    dedupe: ["@base-ui/react", "lucide-react", "react", "react-dom"],
  },
  build: {
    target: "es2022",
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: "react",
              test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/,
              priority: 30,
            },
            {
              name: "tanstack",
              test: /node_modules[\\/]@tanstack[\\/]/,
              priority: 25,
            },
            {
              name: "base-ui",
              test: /node_modules[\\/]@base-ui[\\/]/,
              priority: 20,
            },
            {
              name: "lucide",
              test: /node_modules[\\/]lucide-react[\\/]/,
              priority: 15,
            },
            {
              name: "date-fns",
              test: /node_modules[\\/]date-fns[\\/]/,
              priority: 10,
            },
          ],
        },
      },
    },
  },
  server: {
    port: 3000,
    strictPort: true,
  },
  preview: {
    port: 3000,
    strictPort: true,
  },
});
