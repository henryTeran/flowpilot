import { expect as baseExpect, test } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(180000);

test("native demand authoring retains frozen terms and recovers committed lost acknowledgement", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  const catalog = await (await request.get(`${api}/services/catalog`, { headers })).json();
  const service = catalog.find((s: any) => s.status === "active" && Number.isSafeInteger(s.duration_min) && s.duration_min > 0);
  let posts = 0, reads = 0, retained: any, terms: any;
  await page.route("**/waitlist/**", async route => {
    if (route.request().method() !== "POST") { reads++; await route.continue(); return; }
    posts++; terms = route.request().postDataJSON();
    const saved = await page.evaluate(() => Object.keys(sessionStorage).filter(key => key.startsWith("flowpilot.waitlist-demand.v1:")).map(key => JSON.parse(sessionStorage.getItem(key)!)));
    expect(saved).toHaveLength(1); expect(saved[0].terms).toEqual(terms);
    const response = await route.fetch(); expect(response.status(), await response.text()).toBe(200); retained = await response.json();
    await route.abort("connectionfailed");
  });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  const panel = page.getByRole("region", { name: "Déclarer une demande de liste d’attente", exact: true });
  const history = page.getByRole("region", { name: "Demandes de liste d’attente conservées", exact: true });
  await expect(panel).toBeVisible(); expect(posts).toBe(0); expect(reads).toBe(0);
  await history.getByRole("button", { name: "Lire les demandes conservées", exact: true }).click();
  await expect(history.getByRole("status")).toHaveCount(0);
  const priorReads = reads;
  await panel.getByRole("button", { name: "Conserver la demande et capturer les sources", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("Demande non envoyée"); expect(reads).toBe(priorReads); expect(posts).toBe(0);
  await panel.getByRole("button", { name: "Nouvelle cliente", exact: true }).click();
  await panel.getByLabel("Nom de la cliente", { exact: true }).fill(`Attente native ${info.project.name}`);
  await panel.getByRole("button", { name: "Enregistrer la cliente", exact: true }).click();
  await expect(panel).toContainText(`Attente native ${info.project.name}`);
  await expect(panel.getByLabel("Nom de la cliente", { exact: true })).toHaveCount(0);
  await panel.getByRole("combobox", { name: /^Prestation demandée/ }).selectOption(service.id);
  for (const [n, day] of [[1, "2030-01-02"], [2, "2030-01-03"]] as const) {
    if (n === 2) await panel.getByRole("button", { name: "Ajouter une disponibilité", exact: true }).click();
    await panel.getByLabel(`Début disponibilité ${n} — date`, { exact: true }).fill(day);
    await panel.getByLabel(`Début disponibilité ${n} — heure`, { exact: true }).fill("10:00");
    await panel.getByLabel(`Fin disponibilité ${n} — date`, { exact: true }).fill(day);
    await panel.getByLabel(`Fin disponibilité ${n} — heure`, { exact: true }).fill("12:00");
  }
  await panel.getByLabel("Preuve des disponibilités", { exact: true }).fill("Disponibilités confirmées par la cliente 🧪");
  await panel.getByRole("combobox", { name: /^Restriction de collaboratrices/ }).selectOption("none");
  await panel.getByRole("combobox", { name: /^Relecture des contraintes/ }).selectOption("confirmed");
  await panel.getByLabel("Preuve de relecture des contraintes", { exact: true }).fill("Contraintes relues avec la cliente");
  await panel.getByLabel("Motif de la demande", { exact: true }).fill(`Demande native ${info.project.name}`);
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  for (const control of await panel.locator("button,input,select,textarea").all()) {
    if (await control.isVisible()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false);
  await panel.screenshot({ path: info.outputPath("native-waitlist-form.png") });
  await panel.getByRole("button", { name: "Conserver la demande et capturer les sources", exact: true }).click();
  await expect(panel.getByRole("heading", { name: "Demande figée à reprendre", exact: true })).toBeVisible();
  await expect(panel.getByRole("alert")).toContainText("Conservation à vérifier"); expect(posts).toBe(1);
  expect(terms.availability).toEqual([{ start: "2030-01-02T09:00:00.000Z", end: "2030-01-02T11:00:00.000Z" }, { start: "2030-01-03T09:00:00.000Z", end: "2030-01-03T11:00:00.000Z" }]);
  expect(terms.duration_minutes).toBe(service.duration_min); expect(terms.allowed_employee_ids).toEqual([]);
  await expect(panel.getByRole("textbox", { name: "Motif de la demande", exact: true })).toBeDisabled();
  await panel.locator("article summary").click();
  await panel.locator("article").screenshot({ path: info.outputPath("native-waitlist-frozen.png") });
  await page.reload(); await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  await expect(panel.getByRole("heading", { name: "Demande figée à reprendre", exact: true })).toBeVisible();
  const recoveryReads = reads;
  await panel.getByRole("button", { name: "Reprendre la demande par clé", exact: true }).click();
  await expect(panel.getByRole("heading", { name: "Demande conservée et relue", exact: true })).toBeVisible();
  expect(posts).toBe(1); expect(reads-recoveryReads).toBe(3);
  await expect(panel.getByRole("alert")).toHaveCount(0); await expect(history.locator("article")).toHaveCount(0);
  expect(await page.evaluate(() => Object.keys(sessionStorage).some(key => key.startsWith("flowpilot.waitlist-demand.v1:")))).toBe(false);
  await panel.locator("article summary").click(); await expect(panel.locator("article")).toContainText(retained.fingerprint);
  await expect(panel.locator("article")).toContainText("declared_only"); await expect(panel.locator("article")).toContainText("no_booking_or_contact");
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  for (const control of await panel.locator("button,summary").all()) {
    if (await control.isVisible()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false);
  await panel.locator("article").screenshot({ path: info.outputPath("native-waitlist-receipt.png") });
  await history.getByRole("button", { name: "Lire les demandes conservées", exact: true }).click();
  await expect(history).toContainText(`Demande native ${info.project.name}`);
  const lifecycle = await (await request.get(`${api}/waitlist/institutes/${institute}/lifecycle`, { headers })).json();
  expect(lifecycle.active).toBe(0); expect(lifecycle.total).toBe(0);
  await panel.getByRole("button", { name: "Déclarer une autre demande", exact: true }).click();
  await expect(panel.getByRole("combobox", { name: /^Prestation demandée/ })).toHaveValue("");
  await expect(panel.getByLabel("Début disponibilité 1 — date", { exact: true })).toHaveValue("");
  await expect(panel.getByLabel("Motif de la demande", { exact: true })).toHaveValue("");
});
