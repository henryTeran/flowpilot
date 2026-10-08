import { expect as baseExpect, test } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(180000);

test("native lifecycle history retains revised/cancelled chains and pages active administrative states", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  async function post(path: string, data: unknown) { const response = await request.post(`${api}${path}`, { headers, data }); expect(response.status(), await response.text()).toBe(200); return response.json(); }
  const customer = await post(`/customers/institutes/${institute}`, { display_name: `Chaînes ${info.project.name}`, idempotency_key: `lifecycle-customer-${info.project.name}` });
  const catalog = await (await request.get(`${api}/services/catalog`, { headers })).json();
  const service = catalog.find((s: any) => s.status === "active" && Number.isSafeInteger(s.duration_min) && s.duration_min > 0);
  const base = `/waitlist/institutes/${institute}`;
  async function declare(key: string, reason: string, unknown = false, day = "02") {
    return post(`${base}/originals`, { customer_id: customer.id, service_id: service.id, duration_minutes: service.duration_min,
      availability: [{ start: `2030-01-${day}T09:00:00Z`, end: `2030-01-${day}T11:00:00Z` }], allowed_employee_ids: [],
      constraints_review: unknown ? "unknown" : "confirmed", availability_evidence: "Disponibilité déclarée 🧪",
      constraints_evidence: unknown ? null : "Contraintes relues avec cliente", reason, idempotency_key: key });
  }
  let cancelled: any;
  for (let n = 0; n < 25; n++) {
    const root = await declare(`lifecycle-root-${info.project.name}-${n}`, `Chaîne ${info.project.name} ${n}`, n === 24);
    const activate = await post(`${base}/lifecycle/originals`, { root_id: root.original.id, root_fingerprint: root.fingerprint,
      previous_id: null, previous_fingerprint: null, action: "activate", target_id: root.original.id, target_fingerprint: root.fingerprint,
      reason: "Activation relue", idempotency_key: `lifecycle-activate-${info.project.name}-${n}` });
    if (n === 0) {
      const replacement = await declare(`lifecycle-replacement-${info.project.name}`, `Déclaration révisée ${info.project.name}`, false, "03");
      const revise = await post(`${base}/lifecycle/originals`, { root_id: root.original.id, root_fingerprint: root.fingerprint,
        previous_id: activate.original.id, previous_fingerprint: activate.fingerprint, action: "revise", target_id: replacement.original.id, target_fingerprint: replacement.fingerprint,
        reason: "Révision relue avec cliente", idempotency_key: `lifecycle-revise-${info.project.name}` });
      cancelled = await post(`${base}/lifecycle/originals`, { root_id: root.original.id, root_fingerprint: root.fingerprint,
        previous_id: revise.original.id, previous_fingerprint: revise.fingerprint, action: "cancel", target_id: replacement.original.id, target_fingerprint: replacement.fingerprint,
        reason: "Annulation demandée par cliente", idempotency_key: `lifecycle-cancel-${info.project.name}` });
    }
  }
  await declare(`lifecycle-unactivated-${info.project.name}`, `Déclaration sans activation ${info.project.name}`);
  let reads = 0, corrupt = false;
  await page.route("**/waitlist/institutes/**/lifecycle?**", async route => {
    reads++; expect(route.request().method()).toBe("GET"); const response = await route.fetch(), value = await response.json();
    if (corrupt && value.states.length) value.states[0].state = value.states[0].state === "active" ? "cancelled" : "active";
    await route.fulfill({ response, json: value });
  });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  const panel = page.getByRole("region", { name: "États de liste d’attente conservés", exact: true });
  const read = panel.getByRole("button", { name: "Lire les états de liste d’attente", exact: true });
  await expect(panel).toBeVisible(); expect(reads).toBe(0);
  const total = info.project.name === "desktop" ? 25 : 50, cancelledCount = info.project.name === "desktop" ? 1 : 2;
  await read.click(); await expect(panel).toContainText(`${total} listes conservées · ${total-cancelledCount} actives · ${cancelledCount} annulées`);
  const rootIds = new Set<string>();
  for (let offset = 0; offset < total; offset += 20) {
    await expect(read).toBeEnabled(); await expect(panel).toContainText(`${offset+1}–${Math.min(offset+20, total)} sur ${total}`);
    await expect(panel.locator("article")).toHaveCount(Math.min(20, total-offset));
    const content = await panel.locator("article").allTextContents();
    for (const text of content) { const id = text.match(/Racine (waitlist_demand_[a-z0-9]+)/)![1]; expect(rootIds.has(id)).toBe(false); rootIds.add(id); }
    if (offset+20 < total) await panel.getByRole("button", { name: "États suivants", exact: true }).click();
  }
  expect(rootIds.size).toBe(total);
  async function find(reason: string) {
    await read.click();
    for (let n = 0; n < 4; n++) {
      await expect(read).toBeEnabled();
      const card = panel.locator("article").filter({ has: page.getByRole("heading", { name: reason, exact: true }) });
      if (await card.count()) return card;
      await panel.getByRole("button", { name: "États suivants", exact: true }).click();
    }
    throw new Error("Expected retained root was not paged");
  }
  const closed = await find(`Chaîne ${info.project.name} 0`);
  await expect(closed).toContainText("annulée : chaîne fermée"); await expect(closed).toContainText(`Déclaration révisée ${info.project.name}`);
  await closed.getByText("Voir les actions et leurs preuves", { exact: true }).click();
  await expect(closed.locator("h4")).toHaveText(["Activation", "Révision", "Annulation"]);
  await expect(closed).toContainText(cancelled.fingerprint); await expect(closed).toContainText("aucune nouvelle capture d’éligibilité");
  await closed.screenshot({ path: info.outputPath("native-waitlist-cancelled-chain.png") });
  const active = await find(`Chaîne ${info.project.name} 24`);
  await expect(active).toContainText("active administrativement"); await expect(active).toContainText("Contraintes inconnues");
  await active.getByText("Voir les déclarations racine et courante", { exact: true }).click();
  await expect(active).toContainText("no_booking_or_contact"); await expect(active).toContainText("browser-manager");
  await active.screenshot({ path: info.outputPath("native-waitlist-active-unknown.png") });
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  for (const control of await panel.locator("button,summary").all()) { if (await control.isVisible()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44); }
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false);
  corrupt = true; await read.click(); await expect(panel.getByRole("alert")).toBeVisible(); await expect(panel.locator("article")).toHaveCount(0);
  corrupt = false; await read.click(); await expect(panel.locator("article")).toHaveCount(20);
  const after = await (await request.get(`${api}${base}/lifecycle`, { headers })).json();
  expect(after.total).toBe(total); expect(after.active).toBe(total-cancelledCount); expect(after.cancelled).toBe(cancelledCount);
});
