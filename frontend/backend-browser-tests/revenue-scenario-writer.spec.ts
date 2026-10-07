import { expect as baseExpect, test } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(120000);
test("native declaration recovers a real committed original after lost acknowledgement and reload", async ({ page }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible(); let posts = 0, reads = 0, retained: any;
  await page.route("**/scenarios/originals", async route => {
    if (route.request().method() !== "POST") { await route.continue(); return; }
    posts++; const response = await route.fetch(); expect(response.status()).toBe(200); retained = await response.json();
    if (posts === 1) await route.abort("failed"); else await route.fulfill({ response });
  });
  await page.route("**/scenarios/original-by-key?**", async route => { reads++; await route.continue(); });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  const panel = page.getByRole("region", { name: "Conserver un scénario", exact: true }); await expect(panel).toBeVisible(); expect(posts).toBe(0); expect(reads).toBe(0);
  const fill = async (reason: string) => {
    for (const [label, value] of [["Début observé", "2020-01-01"], ["Fin observée exclue", "2020-01-05"], ["Début projeté", "2030-01-01"], ["Fin projetée exclue", "2030-01-02"]]) await panel.getByLabel(label, { exact: true }).fill(value);
    await panel.getByLabel("Devise du scénario").selectOption("CHF"); await panel.getByLabel("Numérateur d’activité").fill("1"); await panel.getByLabel("Dénominateur d’activité").fill("3"); await panel.getByLabel("Motif du scénario").fill(reason);
  };
  const reason = `Déclaration native ${info.project.name} 🧪\nHypothèse explicite`;
  await fill(reason); await panel.getByRole("button", { name: "Conserver ces hypothèses et capturer les sources", exact: true }).click();
  await expect(panel.getByRole("alert")).toBeVisible(); expect(posts).toBe(1); expect(reads).toBe(1);
  const key = retained.original.idempotency_key; expect(retained.original.actor_id).toBe("browser-manager"); expect(retained.original.reason).toBe(reason);
  expect(retained.original.assumptions.observed_start).toBe("2019-12-31T23:00:00Z"); expect(retained.original.evidence.ticket_count).toBeGreaterThanOrEqual(6);
  expect(retained.original.projected_gross_minor).toBeNull(); await expect(panel.getByLabel("Motif du scénario")).toBeDisabled();
  await page.reload(); await expect(page.locator(".flow-session-exit")).toBeVisible(); await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  await expect(panel).toContainText(key); expect(posts).toBe(1); expect(reads).toBe(1);
  await panel.getByRole("button", { name: "Reprendre la conservation par clé", exact: true }).click();
  await expect(panel).toContainText("Scénario conservé et relu"); expect(posts).toBe(1); expect(reads).toBe(3);
  await expect(panel).toContainText(retained.fingerprint); await expect(panel).toContainText(reason); await expect(panel).toContainText("Projection conditionnelle : indisponible");
  expect(await page.evaluate(() => Object.keys(sessionStorage).filter(k => k.startsWith("flowpilot.revenue-scenario.v1:")).length)).toBe(0);
  const history = page.getByRole("region", { name: "Scénarios conservés", exact: true }); await expect(history).not.toContainText(key);
  await history.getByRole("button", { name: "Lire l’historique des scénarios", exact: true }).click(); await expect(history).toContainText(reason);
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  for (const control of await panel.locator("button,input,select").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false);
  await panel.screenshot({ path: info.outputPath("native-scenario-writer.png") });
  await panel.getByRole("button", { name: "Déclarer un autre scénario", exact: true }).click(); await fill(reason + " variante");
  await panel.getByRole("button", { name: "Conserver ces hypothèses et capturer les sources", exact: true }).click();
  await expect(panel).toContainText("Scénario conservé et relu"); expect(posts).toBe(2); expect(retained.original.idempotency_key).not.toBe(key);
  await expect(history).not.toContainText(reason); // A successful declaration invalidates previously displayed audit.
});
