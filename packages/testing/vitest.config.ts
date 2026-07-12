import { defineProject } from "vitest/config";

export default defineProject({
  test: {
    name: "@routedeck/testing",
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
