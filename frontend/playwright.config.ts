import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./browser-tests", workers: 1, retries: 0,
  use: { baseURL: "http://127.0.0.1:4197", channel: process.env.FLOWPILOT_BROWSER_CHANNEL || (process.platform === "win32" ? "msedge" : undefined), trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "tablet-landscape", use: { viewport: { width: 1024, height: 768 }, hasTouch: true } },
  ],
  webServer: { command: "npm run build && npm run preview -- --host 127.0.0.1 --port 4197 --strictPort", url: "http://127.0.0.1:4197", reuseExistingServer: false, timeout: 60000 },
});
