import { readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
function discover(directory) {
  return readdirSync(join(root, directory), { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return discover(path);
    return entry.isFile() && /\.test\.(?:js|ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}
const files = [...discover("src"), ...discover("tests")].sort();
if (!files.length) throw new Error("No frontend test files discovered");
const result = spawnSync(process.execPath, ["--import", "tsx", "--test", "--test-timeout=60000", ...files], {
  cwd: root, stdio: "inherit",
});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
