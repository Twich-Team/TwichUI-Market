import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  fullyParallel: false,
  timeout: 30000,
  use: {
    baseURL: process.env.BASE_URL || "http://proxy",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  outputDir: "../artifacts/web-e2e",
  reporter: "list",
});
