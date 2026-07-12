import { defineProject } from "vitest/config";

export default defineProject({
  test: {
    name: "@routedeck/react",
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
