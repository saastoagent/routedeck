import { defineProject } from "vitest/config";

export default defineProject({
  test: {
    name: "@routedeck/medusa-agent",
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    pool: "threads",
  },
});
