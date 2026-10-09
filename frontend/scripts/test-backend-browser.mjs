import { mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, basename, join } from "node:path";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const voiceFixture = process.argv[2] === "--voice-fixture";
const simulatePayments = process.argv[2] === "--payment-simulator";
const conversionFixture = process.argv[2] === "--conversion-fixture";
const crmHistoryFixture = process.argv[2] === "--crm-history-fixture";
const planningFixture = process.argv[2] === "--planning-fixture";
const revenueFixture = process.argv[2] === "--revenue-fixture";
const marketingFixture = process.argv[2] === "--marketing-fixture" || conversionFixture;
const config = simulatePayments ? "playwright.payments.config.ts" : "playwright.backend.config.ts";
const temporaryRoot = realpathSync(tmpdir());
const directory = realpathSync(mkdtempSync(join(temporaryRoot, "flowpilot-browser-")));
writeFileSync(join(directory, ".flowpilot-browser-owner"), "isolated browser fixture\n");
let status = 1;
try {
  const cli = createRequire(import.meta.url).resolve("@playwright/test/cli");
  const result = spawnSync(process.execPath, [cli, "test", "--config", config, ...process.argv.slice(voiceFixture || simulatePayments || marketingFixture || crmHistoryFixture || planningFixture || revenueFixture ? 3 : 2)], {
    cwd: root, stdio: "inherit", env: { ...process.env, FLOWPILOT_BROWSER_DIRECTORY: directory, FLOWPILOT_BROWSER_VOICE_FIXTURE: voiceFixture ? "1" : "0", FLOWPILOT_BROWSER_MARKETING_FIXTURE: marketingFixture ? "1" : "0",
      FLOWPILOT_BROWSER_CONVERSION_FIXTURE: conversionFixture ? "1" : "0", FLOWPILOT_BROWSER_CRM_HISTORY_FIXTURE: crmHistoryFixture ? "1" : "0",
      FLOWPILOT_BROWSER_PLANNING_FIXTURE: planningFixture ? "1" : "0", FLOWPILOT_BROWSER_REVENUE_FIXTURE: revenueFixture ? "1" : "0" },
  });
  if (result.error) throw result.error;
  status = result.status ?? 1;
} finally {
  // Only the exact directory created by this invocation can be deleted.
  if (dirname(directory) !== temporaryRoot || !basename(directory).startsWith("flowpilot-browser-")) {
    throw new Error("Refusing cleanup outside the owned browser fixture directory");
  }
  rmSync(directory, { recursive: true, force: false, maxRetries: 10, retryDelay: 100 });
  process.stdout.write("Owned browser fixture directory removed.\n");
}
process.exit(status);
