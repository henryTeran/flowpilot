import { defineConfig } from "@playwright/test";
import common from "./playwright.config";

const python = process.platform === "win32" ? "..\\.venv\\Scripts\\python.exe" : "../.venv/bin/python";
export default defineConfig({
  ...common,
  testDir: "./backend-browser-tests",
  use: { ...common.use, baseURL: "http://127.0.0.1:4199", timezoneId: "Europe/Zurich" },
  webServer: [
    { command: `${python} browser-tests/backend_server.py`, url: "http://127.0.0.1:4198/ready", reuseExistingServer: false, timeout: 60000 },
    { command: "npm run build && npm run preview -- --host 127.0.0.1 --port 4199 --strictPort",
      env: { VITE_API_URL: "http://127.0.0.1:4198/api/v1", VITE_WS_URL: "ws://127.0.0.1:4198/ws" },
      url: "http://127.0.0.1:4199", reuseExistingServer: false, timeout: 60000 },
  ],
});
