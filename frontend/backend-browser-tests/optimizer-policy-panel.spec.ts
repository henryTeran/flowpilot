import { expect as baseExpect, test } from "@playwright/test";
import { optimizerFactors } from "../src/optimizer-policy-utils";
import { optimizerLabels } from "../src/components/OptimizerPolicyPanel";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(180000);
test("signed native policy authoring, lost acknowledgement recovery and verified history", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1/optimizer/institutes/demo-institute-geneve";
  const before = await (await request.get(`${api}/policy-originals`, { headers })).json();
  let posts = 0, reads = 0, terms: any, receipt: any, corrupt = false;
  await page.route("**/optimizer/**", async route => {
    if (route.request().method() !== "POST") {
      reads++;
      if (corrupt && route.request().url().includes("/policy-originals?")) { const response = await route.fetch(); const value = await response.json(); await route.fulfill({ response, json: { ...value, basis: "active_default" } }); }
      else await route.continue();
      return;
    }
    posts++; terms = route.request().postDataJSON();
    const saved = await page.evaluate(() => Object.keys(sessionStorage).filter(k => k.startsWith("flowpilot.optimizer-policy.v1:")).map(k => JSON.parse(sessionStorage.getItem(k)!)));
    expect(saved).toHaveLength(1); expect(saved[0].terms).toEqual(terms);
    const response = await route.fetch(); expect(response.status(), await response.text()).toBe(200); receipt = await response.json(); await route.abort("connectionfailed");
  });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  const panel = page.getByRole("region", { name: "Politique de scoring des créneaux", exact: true });
  await expect(panel).toBeVisible(); expect(posts).toBe(0); expect(reads).toBe(0);
  await panel.getByText("Créer une politique explicite", { exact: true }).click();
  await panel.getByRole("button", { name: "Conserver la politique et relire l’original", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("Politique non envoyée"); expect(reads).toBe(0); expect(posts).toBe(0);
  for (const f of optimizerFactors) {
    await panel.getByRole("combobox", { name: `Statut — ${optimizerLabels[f]}`, exact: true }).selectOption(f === "utilization_score" ? "enabled" : "disabled");
    await panel.getByLabel(`Motif — ${optimizerLabels[f]}`, { exact: true }).fill("Choix explicite relu avec responsable");
  }
  await panel.getByLabel(`Numérateur du poids — ${optimizerLabels.utilization_score}`, { exact: true }).fill("1");
  await panel.getByLabel(`Dénominateur du poids — ${optimizerLabels.utilization_score}`, { exact: true }).fill("1");
  await panel.getByLabel("Motif de la politique", { exact: true }).fill(`Politique native ${info.project.name}`);
  for (const control of await panel.locator("button,input,select,textarea,summary").all()) if (await control.isVisible()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false);
  await panel.locator("fieldset").filter({ has: page.getByRole("combobox", { name: `Statut — ${optimizerLabels.utilization_score}`, exact: true }) }).last().screenshot({ path: info.outputPath("native-optimizer-rule.png") });
  await panel.getByRole("button", { name: "Conserver la politique et relire l’original", exact: true }).click();
  await expect(panel.getByRole("heading", { name: "Politique figée à reprendre", exact: true })).toBeVisible();
  await expect(panel.getByRole("alert")).toContainText("Conservation à vérifier"); expect(posts).toBe(1);
  await panel.locator("article").screenshot({ path: info.outputPath("native-optimizer-frozen.png") });
  await page.reload(); await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  const count = reads; await panel.getByRole("button", { name: "Reprendre la politique par clé", exact: true }).click();
  await expect(panel.getByRole("heading", { name: "Politique conservée et relue", exact: true })).toBeVisible(); expect(posts).toBe(1); expect(reads-count).toBe(3);
  expect(await page.evaluate(() => Object.keys(sessionStorage).filter(k => k.startsWith("flowpilot.optimizer-policy.v1:")))).toHaveLength(0);
  await panel.getByRole("button", { name: "Choisir cette politique pour la revue", exact: true }).click();
  await expect(panel.getByRole("status")).toContainText("Politique choisie");
  await panel.locator("article").screenshot({ path: info.outputPath("native-optimizer-retained.png") });
  for (let i = 0; i < 24; i++) { const response = await request.post(`${api}/policy-originals`, { headers, data: { ...terms, reason: `Historique ${info.project.name} ${i}`, idempotency_key: `native-${info.project.name}-${i}` } }); expect(response.status()).toBe(200); }
  await panel.getByRole("button", { name: "Préparer une autre politique", exact: true }).click();
  const total = before.total+25;
  await panel.getByRole("button", { name: "Lire les politiques conservées", exact: true }).click();
  await expect(panel).toContainText(`1–20 sur ${total} politiques`);
  const ids: string[] = [];
  for (let offset = 0; offset < total; offset += 20) {
    const cards = panel.locator("article"); await expect(cards).toHaveCount(Math.min(20, total-offset));
    for (const card of await cards.all()) { const text = await card.locator("pre").textContent(); ids.push(JSON.parse(text!).id); }
    if (offset+20 < total) { await panel.getByRole("button", { name: "Politiques suivantes", exact: true }).click(); await expect(panel).toContainText(`${offset+21}–${Math.min(offset+40, total)} sur ${total} politiques`); }
  }
  expect(new Set(ids).size).toBe(total); expect(ids).toContain(receipt.original.id);
  await panel.locator("article").first().screenshot({ path: info.outputPath("native-optimizer-history.png") });
  corrupt = true; await panel.getByRole("button", { name: "Lire les politiques conservées", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("Politiques conservées à vérifier"); await expect(panel.locator("article")).toHaveCount(0);
  corrupt = false; await panel.getByRole("button", { name: "Lire les politiques conservées", exact: true }).click(); await expect(panel.locator("article")).toHaveCount(20);
  expect(posts).toBe(1);
});
