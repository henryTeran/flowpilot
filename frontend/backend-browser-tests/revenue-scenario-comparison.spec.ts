import { expect as baseExpect, test } from "@playwright/test";
import { spawnSync } from "node:child_process";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(180000);
test("native explicit selection spans real audit pages and verifies known negative/zero and unavailable comparisons", async ({ page, request }, info) => {
  const python = process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python";
  const seeded = spawnSync(python, ["browser-tests/revenue_scenario_fixture.py", info.project.name], { encoding: "utf8", env: process.env });
  expect(seeded.status, seeded.stderr + seeded.stdout).toBe(0);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com"); await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click(); await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token")), headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1/revenue/institutes/demo-institute-geneve/scenarios";
  for (let n = 0; n < 25; n++) {
    const response = await request.post(base+"/originals", { headers, data: { assumptions: { model: "constant_recorded_gross_rate_v1",
      observed_start: "2026-01-01T00:00:00Z", observed_end: "2026-01-03T00:00:00Z", projected_start: "2030-01-01T00:00:00Z", projected_end: "2030-01-04T00:00:00Z",
      currency: n === 24 ? "EUR" : "CHF", activity_fraction: { numerator: n === 20 ? "0" : "1", denominator: "3" } }, reason: `Comparaison ${info.project.name} ${n}`, idempotency_key: `comparison-${info.project.name}-${n}` } });
    expect(response.status()).toBe(200);
  }
  let posts = 0, corrupt = false, sent: any, actual: any;
  await page.route("**/scenarios/comparison", async route => { posts++; sent = route.request().postDataJSON(); const response = await route.fetch(); expect(response.status()).toBe(200); actual = await response.json();
    const value = structuredClone(actual); if (corrupt) value.causal_effect_confirmed = true; await route.fulfill({ response, json: value }); });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click(); const history = page.getByRole("region", { name: "Scénarios conservés", exact: true }), panel = history.getByRole("region", { name: "Comparer les scénarios", exact: true });
  await expect(panel).toBeVisible(); expect(posts).toBe(0); await expect(panel.getByRole("button", { name: "Comparer la sélection", exact: true })).toBeDisabled();
  await history.getByRole("button", { name: "Lire l’historique des scénarios", exact: true }).click(); await expect(history).toContainText("1–20 sur");
  await history.getByRole("button", { name: /^Choisir comme référence / }).first().click();
  await history.getByRole("button", { name: "Scénarios suivants", exact: true }).click(); await expect(history).toContainText("21–");
  await history.getByRole("button", { name: /^Ajouter comme variante / }).first().click();
  await history.getByRole("button", { name: /^Ajouter comme variante / }).nth(4).click();
  const compare = panel.getByRole("button", { name: "Comparer la sélection", exact: true }); await compare.click();
  await expect(panel).toContainText("Comparaison vérifiée"); await expect(panel).toContainText("Écart à la référence : -101 / 2 centimes CHF");
  await expect(panel).toContainText("Projection conditionnelle : 0 / 1 centimes CHF"); await expect(panel).toContainText("Devises différentes");
  await expect(panel).toContainText("CHF : 2 sélectionnés, 2 projections chiffrées, 0 indisponibles"); await expect(panel).toContainText("EUR : 1 sélectionnés, 0 projections chiffrées, 1 indisponibles");
  expect(posts).toBe(1); expect(sent.alternatives).toHaveLength(2); expect(actual.summed_projected_gross_minor).toBeNull();
  for (const [i, reference] of [sent.baseline, ...sent.alternatives].entries()) { expect(actual.variants[i].original.original.id).toBe(reference.original_id); expect(actual.variants[i].original.fingerprint).toBe(reference.fingerprint); }
  corrupt = true; await compare.click(); await expect(panel.getByRole("alert")).toBeVisible(); await expect(panel).not.toContainText("Comparaison vérifiée");
  corrupt = false; await compare.click(); await expect(panel).toContainText("Comparaison vérifiée"); expect(posts).toBe(3);
  await panel.locator("summary").first().click(); await expect(panel).toContainText(sent.baseline.fingerprint);
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  for (const control of await panel.locator("button,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false);
  await panel.screenshot({ path: info.outputPath("native-scenario-comparison.png") });
  await panel.getByRole("button", { name: /^Retirer la variante / }).first().click(); await expect(panel).not.toContainText("Comparaison vérifiée"); expect(posts).toBe(3);
});
