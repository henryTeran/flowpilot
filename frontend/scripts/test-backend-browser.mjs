import { mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, basename, join } from "node:path";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const temporaryRoot = realpathSync(tmpdir());
const directory = realpathSync(mkdtempSync(join(temporaryRoot, "flowpilot-browser-")));
writeFileSync(join(directory, ".flowpilot-browser-owner"), "isolated browser fixture\n");
let status = 1;
try {
  const cli = createRequire(import.meta.url).resolve("@playwright/test/cli");
  const result = spawnSync(process.execPath, [cli, "test", "--config", "playwright.backend.config.ts", ...process.argv.slice(2)], {
    cwd: root, stdio: "inherit", env: { ...process.env, FLOWPILOT_BROWSER_DIRECTORY: directory },
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
