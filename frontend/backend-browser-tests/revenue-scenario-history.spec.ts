import { expect as baseExpect, test } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(90000);
test("native scenario history verifies real retained originals and hides corrupt audit", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const base = "http://127.0.0.1:4198/api/v1/revenue/institutes/demo-institute-geneve/scenarios", headers = { Authorization: `Bearer ${token}` };
  const reason = `Scénario conservé ${info.project.name} 🧪\nMotif explicite 2026-10-07T12:00:00Z`;
  const created = await request.post(base+"/originals", { headers, data: { assumptions: { model: "constant_recorded_gross_rate_v1",
    observed_start: "2020-01-01T00:00:00Z", observed_end: "2020-01-05T00:00:00Z", projected_start: "2030-01-01T00:00:00Z", projected_end: "2030-01-02T00:00:00Z",
    currency: "CHF", activity_fraction: { numerator: "1", denominator: "3" } }, reason, idempotency_key: `history-${info.project.name}` } });
  expect(created.status()).toBe(200); const original = await created.json(); expect(original.original.evidence.ticket_count).toBeGreaterThanOrEqual(2); let reads = 0, corrupt = false;
  await page.route("**/scenarios/originals?**", async route => {
    reads++; const response = await route.fetch(), value = await response.json(); expect(response.status()).toBe(200);
    if (corrupt) value.full_original_cohort_verified = 1;
    await route.fulfill({ response, json: value });
  });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click(); const panel = page.getByRole("region", { name: "Scénarios conservés", exact: true });
  await expect(panel).toBeVisible(); expect(reads).toBe(0);
  const button = panel.getByRole("button", { name: "Lire l’historique des scénarios", exact: true }); await button.click();
  await expect(panel).toContainText(reason); await expect(panel).toContainText("Projection conditionnelle : indisponible");
  await expect(panel).toContainText("Une devise enregistrée est inconnue");
  const card = panel.locator("article").filter({ hasText: reason }); await card.locator("summary").click(); await expect(card).toContainText(original.fingerprint);
  await expect(card).toContainText("370.35 CHF"); await expect(card).toContainText("Devise inconnue");
  await expect(card).toContainText("Devise sélectionnée : CHF");
  corrupt = true; await button.click(); await expect(panel.getByRole("alert")).toBeVisible(); await expect(panel).not.toContainText(reason);
  corrupt = false; await button.click(); await expect(panel).toContainText(reason); await card.locator("summary").click();
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  for (const control of await panel.locator("button,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false);
  await panel.screenshot({ path: info.outputPath("native-scenario-history.png") });
});
