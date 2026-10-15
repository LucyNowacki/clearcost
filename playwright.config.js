const { defineConfig } = require("@playwright/test");
module.exports = defineConfig({
  testDir: "./browser-tests",
  outputDir: "./output/browser-tests",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: process.env.DEMO_BASE_URL || "http://127.0.0.1:8879",
    browserName: "chromium",
    headless: true,
    launchOptions: process.env.CHROME_PATH
      ? { executablePath: process.env.CHROME_PATH }
      : {},
  },
});
