import { expect as baseExpect, test } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(180000);

test("native lifecycle activation/revision recovery and stale-version cancellation require explicit rereview", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve", base = `/waitlist/institutes/${institute}`;
  async function post(path: string, data: unknown) { const response = await request.post(`${api}${path}`, { headers, data }); expect(response.status(), await response.text()).toBe(200); return response.json(); }
  const customer = await post(`/customers/institutes/${institute}`, { display_name: `Cycle ${info.project.name}`, idempotency_key: `cycle-customer-${info.project.name}` });
  const catalog = await (await request.get(`${api}/services/catalog`, { headers })).json();
  const service = catalog.find((s: any) => s.status === "active" && Number.isSafeInteger(s.duration_min) && s.duration_min > 0);
  async function declare(name: string, day: string) { return post(`${base}/originals`, { customer_id: customer.id, service_id: service.id, duration_minutes: service.duration_min,
    availability: [{ start: `2030-01-${day}T09:00:00Z`, end: `2030-01-${day}T11:00:00Z` }], allowed_employee_ids: [], constraints_review: "confirmed",
    availability_evidence: "Disponibilités déclarées par cliente 🧪", constraints_evidence: "Contraintes relues", reason: `${name} ${info.project.name}`, idempotency_key: `cycle-${name}-${info.project.name}` }); }
  const root = await declare("Racine native", "02"), replacement = await declare("Remplacement natif", "03"), concurrent = await declare("Remplacement concurrent", "04");
  const writes: any[] = []; let loseRevision = true, reads = 0, revisionReceipt: any;
  await page.route("**/waitlist/**", async route => {
    if (route.request().method() !== "POST") { reads++; await route.continue(); return; }
    const body = route.request().postDataJSON(); writes.push(body);
    const saved = await page.evaluate(() => Object.keys(sessionStorage).filter(key => key.startsWith("flowpilot.waitlist-lifecycle.v1:")).map(key => JSON.parse(sessionStorage.getItem(key)!)));
    expect(saved).toHaveLength(1); expect(saved[0].terms.request).toEqual(body); expect(saved[0].terms.root.fingerprint).toBe(root.fingerprint);
    if (body.action === "revise" && loseRevision) {
      loseRevision = false; const response = await route.fetch(); expect(response.status(), await response.text()).toBe(200); revisionReceipt = await response.json(); await route.abort("connectionfailed");
    } else await route.continue();
  });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  const writer = page.getByRole("region", { name: "Gérer une liste d’attente", exact: true });
  const originals = page.getByRole("region", { name: "Demandes de liste d’attente conservées", exact: true });
  const lifecycle = page.getByRole("region", { name: "États de liste d’attente conservés", exact: true });
  await expect(writer).toBeVisible(); expect(reads).toBe(0); expect(writes).toHaveLength(0);
  await originals.getByRole("button", { name: "Lire les demandes conservées", exact: true }).click();
  const rootCard = originals.locator("article").filter({ has: page.getByRole("heading", { name: root.original.reason, exact: true }) });
  await rootCard.getByRole("button", { name: "Relire pour gérer cette demande", exact: true }).click();
  await expect(writer.getByRole("button", { name: "Activer cette demande", exact: true })).toBeEnabled();
  await expect(writer).toBeFocused();
  await writer.getByRole("textbox", { name: "Motif de l’action de liste d’attente", exact: true }).fill(`Activation native ${info.project.name}`);
  await writer.getByRole("button", { name: "Activer cette demande", exact: true }).click();
  await expect(writer.getByRole("heading", { name: "Action conservée et relue", exact: true })).toBeVisible(); expect(writes).toHaveLength(1);
  await expect(originals.locator("article")).toHaveCount(0); await expect(lifecycle.locator("article")).toHaveCount(0);
  await originals.getByRole("button", { name: "Lire les demandes conservées", exact: true }).click();
  const targetCard = originals.locator("article").filter({ has: page.getByRole("heading", { name: replacement.original.reason, exact: true }) });
  await targetCard.getByRole("button", { name: "Choisir pour réviser la liste sélectionnée", exact: true }).click();
  await expect(writer).toContainText("Déclaration de remplacement relue");
  await expect(writer).toBeFocused();
  await writer.getByRole("textbox", { name: "Motif de l’action de liste d’attente", exact: true }).fill(`Révision native ${info.project.name}`);
  await writer.getByRole("button", { name: "Réviser avec la déclaration sélectionnée", exact: true }).click();
  await expect(writer.getByRole("heading", { name: "Décision figée à reprendre", exact: true })).toBeVisible();
  await expect(writer.getByRole("alert")).toContainText("Conservation à vérifier"); expect(writes).toHaveLength(2);
  expect(writes[1].target_id).toBe(replacement.original.id); expect(writes[1].previous_id).not.toBeNull();
  const frozen = writer.locator("article").filter({ has: page.getByRole("heading", { name: "Décision figée à reprendre", exact: true }) });
  await frozen.screenshot({ path: info.outputPath("native-lifecycle-frozen-revision.png") });
  await page.reload(); await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  await expect(writer.getByRole("heading", { name: "Décision figée à reprendre", exact: true })).toBeVisible();
  const beforeRecovery = reads; await writer.getByRole("button", { name: "Reprendre l’action par clé", exact: true }).click();
  await expect(writer.getByRole("heading", { name: "Action conservée et relue", exact: true })).toBeVisible();
  expect(writes).toHaveLength(2); expect(reads-beforeRecovery).toBe(4);
  const recovered = writer.locator("article").filter({ has: page.getByRole("heading", { name: "Action conservée et relue", exact: true }) });
  await recovered.locator("summary").click(); await expect(recovered).toContainText(revisionReceipt.fingerprint);
  await recovered.screenshot({ path: info.outputPath("native-lifecycle-recovered-revision.png") });
  // A second authenticated client advances the same root after the UI's read.
  const peer = await post(`${base}/lifecycle/originals`, { root_id: root.original.id, root_fingerprint: root.fingerprint,
    previous_id: revisionReceipt.original.id, previous_fingerprint: revisionReceipt.fingerprint, action: "revise", target_id: concurrent.original.id, target_fingerprint: concurrent.fingerprint,
    reason: "Révision concurrente explicite", idempotency_key: `cycle-peer-${info.project.name}` });
  await writer.getByRole("textbox", { name: "Motif de l’action de liste d’attente", exact: true }).fill("Annuler la version précédemment relue");
  await writer.getByRole("button", { name: "Annuler cette liste d’attente", exact: true }).click();
  await expect(writer.getByRole("heading", { name: "Décision figée à reprendre", exact: true })).toBeVisible(); expect(writes).toHaveLength(3);
  expect(writes[2].previous_id).toBe(revisionReceipt.original.id);
  await writer.getByRole("button", { name: "Vérifier la clé avant de relire la décision", exact: true }).click();
  await expect(writer.locator("article")).toHaveCount(0); await expect(writer.getByRole("button", { name: "Annuler cette liste d’attente", exact: true })).toHaveCount(0);
  await lifecycle.getByRole("button", { name: "Lire les états de liste d’attente", exact: true }).click();
  const stateCard = lifecycle.locator("article").filter({ has: page.getByRole("heading", { name: root.original.reason, exact: true }) });
  await stateCard.getByRole("button", { name: "Relire pour gérer cette liste", exact: true }).click();
  await expect(writer).toContainText(concurrent.original.reason);
  const reason = writer.getByRole("textbox", { name: "Motif de l’action de liste d’attente", exact: true }); await expect(reason).toHaveValue("");
  await reason.fill(`Annulation après relecture ${info.project.name}`); await writer.getByRole("button", { name: "Annuler cette liste d’attente", exact: true }).click();
  await expect(writer).toContainText("annulée, aucune nouvelle transition possible"); expect(writes).toHaveLength(4);
  expect(writes[3].previous_id).toBe(peer.original.id); expect(writes[3].idempotency_key).not.toBe(writes[2].idempotency_key);
  const final = writer.locator("article").filter({ has: page.getByRole("heading", { name: "Action conservée et relue", exact: true }) });
  await final.locator("summary").click(); await expect(final).toContainText("waitlist_state_only_no_booking_or_contact"); await expect(final).toContainText('"activation_source": null');
  await expect(writer.getByRole("textbox")).toHaveCount(0); await expect(writer.getByRole("button", { name: "Activer cette demande", exact: true })).toHaveCount(0);
  expect((await writer.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  for (const control of await writer.locator("button,summary").all()) { if (await control.isVisible()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44); }
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false);
  await final.screenshot({ path: info.outputPath("native-lifecycle-cancelled-receipt.png") });
  expect(await page.evaluate(() => Object.keys(sessionStorage).some(key => key.startsWith("flowpilot.waitlist-lifecycle.v1:")))).toBe(false);
  const state = await (await request.get(`${api}${base}/lifecycle/states/${root.original.id}`, { headers })).json();
  expect(state.state).toBe("cancelled"); expect(state.events).toHaveLength(4); expect(state.current_demand.original.id).toBe(concurrent.original.id);
});
