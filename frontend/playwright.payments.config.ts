import { defineConfig } from "@playwright/test";
import backend from "./playwright.backend.config";

export default defineConfig({
  ...backend,
  testDir: "./payment-browser-tests",
  webServer: (backend.webServer as Array<{ command: string }>).map((server, index) =>
    index === 0 ? { ...server, command: server.command + " --simulate-payments" } : server),
});
