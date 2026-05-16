import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    testTimeout: 60000,
    hookTimeout: 60000,
    include: ["tests/sdk_typescript/**/*.test.ts"],
    setupFiles: ["tests/sdk_typescript/setup.ts"],
    pool: "forks",
    fileParallelism: false,
  },
});
