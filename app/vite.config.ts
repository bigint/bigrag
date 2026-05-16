import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const stripRouteTreeComments = () => {
  const run = () =>
    execFileSync(
      process.execPath,
      [
        resolve("..", "scripts", "strip-route-tree-comments.mjs"),
        resolve("src", "routeTree.gen.ts"),
      ],
      { stdio: "ignore" },
    );

  return {
    name: "bigrag-route-tree-comments",
    buildStart: run,
    buildEnd: run,
    closeBundle: run,
    configureServer(server: { watcher: { on: (event: string, handler: (path: string) => void) => void } }) {
      setTimeout(run, 0);
      server.watcher.on("change", (path) => {
        if (path.endsWith("routeTree.gen.ts")) setTimeout(run, 0);
      });
    },
  };
};

export default defineConfig({
  plugins: [
    tanstackRouter({
      autoCodeSplitting: true,
      quoteStyle: "double",
      routeTreeFileHeader: ["// @ts-nocheck"],
      semicolons: true,
      target: "react",
    }),
    stripRouteTreeComments(),
    react(),
  ],
  resolve: {
    alias: {
      "@": new URL("./src", import.meta.url).pathname,
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
