import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    projects: [
      "packages/core/vitest.config.ts",
      "packages/react/vitest.config.ts",
      "packages/testing/vitest.config.ts",
      "examples/medusa-agent/frontend/vitest.config.ts",
    ],
  },
});
