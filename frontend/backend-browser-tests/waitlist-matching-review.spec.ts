import { expect as baseExpect, test } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 20000 });
test.setTimeout(240000);
test("native matching pins current version and policies, explains sources and pages whole active detection", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve", base = `/waitlist/institutes/${institute}`;
  async function post(path: string, data: unknown) { const response = await request.post(`${api}${path}`, { headers, data }); expect(response.status(), await response.text()).toBe(200); return response.json(); }
  const customer = await post(`/customers/institutes/${institute}`, { display_name: `Matching ${info.project.name}`, idempotency_key: `matching-customer-${info.project.name}` });
  const catalog = await (await request.get(`${api}/services/catalog`, { headers })).json();
  const service = catalog.find((s: any) => s.status === "active" && !s.requires_machine && Number.isSafeInteger(s.duration_min) && s.duration_min > 0);
  async function declare(n: string, unknown = false, day = "02") { return post(`${base}/originals`, { customer_id: customer.id, service_id: service.id, duration_minutes: service.duration_min,
    availability: [{ start: `2030-01-${day}T09:00:00Z`, end: `2030-01-${day}T11:00:00Z` }], allowed_employee_ids: [], constraints_review: unknown ? "unknown" : "confirmed",
    availability_evidence: "Disponibilité déclarée", constraints_evidence: unknown ? null : "Contraintes relues", reason: `Matching ${info.project.name} ${n}`, idempotency_key: `matching-demand-${info.project.name}-${n}` }); }
  let root: any, activation: any;
  for (let n = 0; n < 25; n++) {
    const original = await declare(String(n), n === 24);
    const event = await post(`${base}/lifecycle/originals`, { root_id: original.original.id, root_fingerprint: original.fingerprint,
      previous_id: null, previous_fingerprint: null, action: "activate", target_id: original.original.id, target_fingerprint: original.fingerprint,
      reason: "Activation explicite pour revue", idempotency_key: `matching-activation-${info.project.name}-${n}` });
    if (!n) { root = original; activation = event; }
  }
  const calls: { path: string; query: Record<string, string>; status: number }[] = []; let corrupt = false, waitlistWrites = 0;
  await page.route("**/waitlist/**", async route => {
    if (route.request().method() !== "GET") { waitlistWrites++; await route.continue(); return; }
    const url = new URL(route.request().url());
    if (!url.pathname.endsWith("/matching") && !url.pathname.endsWith("/detection")) { await route.continue(); return; }
    const response = await route.fetch(); calls.push({ path: url.pathname, query: Object.fromEntries(url.searchParams), status: response.status() });
    if (corrupt && response.ok()) { const value = await response.json(); value.action = "book_now"; await route.fulfill({ response, json: value }); }
    else await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  const panel = page.getByRole("region", { name: "Revue des créneaux de liste d’attente", exact: true });
  const history = page.getByRole("region", { name: "États de liste d’attente conservés", exact: true });
  await expect(panel).toBeVisible(); expect(calls).toHaveLength(0);
  await expect(panel.getByRole("button", { name: "Détecter les créneaux des listes actives", exact: true })).toBeDisabled();
  const active = info.project.name === "desktop" ? 25 : 50;
  async function chooseRoot() {
    await history.getByRole("button", { name: "Lire les états de liste d’attente", exact: true }).click();
    await expect(history.locator("article")).toHaveCount(20);
    let card = history.locator("article").filter({ has: page.getByRole("heading", { name: root.original.reason, exact: true }) });
    for (let n = 0; await card.count() === 0 && n < 3; n++) { await expect(history.getByRole("button", { name: "États suivants", exact: true })).toBeEnabled(); await history.getByRole("button", { name: "États suivants", exact: true }).click(); await expect(history).toContainText(`${20*(n+1)+1}–${Math.min(20*(n+2), active)} sur ${active}`); }
    await expect(card).toHaveCount(1); await card.getByRole("button", { name: "Examiner les créneaux actuels", exact: true }).click(); await expect(panel).toBeFocused();
  }
  await chooseRoot(); expect(calls).toHaveLength(0);
  await panel.getByLabel("Fin de l’horizon — date", { exact: true }).fill("2030-01-05"); await panel.getByLabel("Fin de l’horizon — heure", { exact: true }).fill("13:00");
  await panel.getByRole("combobox", { name: /^Canal de suivi/ }).selectOption("email"); await panel.getByRole("combobox", { name: /^Règle d’historique/ }).selectOption("review_only");
  await panel.getByRole("combobox", { name: /^Règle d’accord de suivi/ }).selectOption("review_only");
  const examine = panel.getByRole("button", { name: "Examiner la liste sélectionnée", exact: true }); await examine.click();
  await expect(panel.getByRole("heading", { name: "Options conditionnelles à relire", exact: true })).toBeVisible();
  expect(calls[0].query.expected_event_id).toBe(activation.original.id); expect(calls[0].query.expected_event_fingerprint).toBe(activation.fingerprint);
  expect(calls[0].query.horizon_end).toBe("2030-01-05T12:00:00.000Z");
  await expect(panel).toContainText("inconnu — aucune déclaration"); await expect(panel).toContainText("Horaires d’ouverture non vérifiés");
  await panel.locator("article").screenshot({ path: info.outputPath("native-matching-conditional-options.png") });
  await panel.getByRole("combobox", { name: /^Règle d’accord de suivi/ }).selectOption("recorded_grant_required"); await expect(panel.locator("article")).toHaveCount(0); await examine.click();
  await expect(panel).toContainText("Aucun accord actuel enregistré"); await expect(panel.getByRole("heading", { name: "Options conditionnelles à relire", exact: true })).toHaveCount(0);
  await panel.locator("article").screenshot({ path: info.outputPath("native-matching-permission-refusal.png") });
  const grant = await post(`/crm/institutes/${institute}/customers/${customer.id}/lifecycle-declarations`, { previous_id: null, reason: "Accord de suivi explicitement déclaré", idempotency_key: `matching-grant-${info.project.name}`,
    declaration: { institute_id: institute, customer_id: customer.id, birthday: null, birthday_evidence: null, communications: ["email", "sms"].flatMap(channel => ["service_follow_up", "marketing"].map(purpose => ({ channel, purpose,
      permission: channel === "email" && purpose === "service_follow_up" ? "granted" : "unknown", evidence: channel === "email" && purpose === "service_follow_up" ? "Accord de cliente enregistré" : null }))) } });
  await examine.click(); await expect(panel).toContainText("accord enregistré — déclaration du"); await expect(panel.getByRole("heading", { name: "Options conditionnelles à relire", exact: true })).toBeVisible();
  const replacement = await declare("replacement", false, "03");
  const peer = await post(`${base}/lifecycle/originals`, { root_id: root.original.id, root_fingerprint: root.fingerprint,
    previous_id: activation.original.id, previous_fingerprint: activation.fingerprint, action: "revise", target_id: replacement.original.id, target_fingerprint: replacement.fingerprint,
    reason: "Révision concurrente explicitement conservée", idempotency_key: `matching-peer-${info.project.name}` });
  await examine.click(); await expect(panel.locator("article")).toHaveCount(0); await expect(panel.getByRole("alert")).toContainText("version a changé"); expect(calls[calls.length - 1].status).toBe(400);
  await chooseRoot(); await examine.click(); await expect(panel.locator("article")).toContainText(replacement.original.reason); expect(calls[calls.length - 1].query.expected_event_id).toBe(peer.original.id);
  await post(`/crm/institutes/${institute}/customers/${customer.id}/lifecycle-declarations`, { previous_id: grant.id, reason: "Refus de suivi explicitement déclaré", idempotency_key: `matching-refuse-${info.project.name}`,
    declaration: { ...grant.declaration, communications: grant.declaration.communications.map((c: any) => c.channel === "email" && c.purpose === "service_follow_up" ? { ...c, permission: "refused", evidence: "Refus de cliente enregistré" } : c) } });
  await examine.click(); await expect(panel).toContainText("refus enregistré — déclaration du"); await expect(panel).toContainText("Aucun accord actuel enregistré");
  await panel.locator("article").screenshot({ path: info.outputPath("native-matching-recorded-refusal.png") });
  corrupt = true; await examine.click(); await expect(panel.locator("article")).toHaveCount(0); await expect(panel.getByRole("alert")).toBeVisible(); corrupt = false;
  await panel.getByRole("combobox", { name: /^Règle d’accord de suivi/ }).selectOption("review_only");
  await panel.getByRole("button", { name: "Détecter les créneaux des listes actives", exact: true }).click();
  await expect(panel).toContainText(`${active} actives`); await expect(panel.locator("article")).toHaveCount(20);
  const ids: string[] = [];
  for (let offset = 0; offset < active; offset += 20) {
    if (offset) { await panel.getByRole("button", { name: "Détections suivantes", exact: true }).click(); await expect(panel.getByRole("status")).toHaveCount(0); }
    await expect(panel.locator("article")).toHaveCount(Math.min(20, active - offset)); expect(calls[calls.length - 1].query.offset).toBe(String(offset));
    for (const article of await panel.locator("article").all()) ids.push((await article.getByRole("heading", { level: 3 }).textContent())!);
  }
  expect(new Set(ids).size).toBe(active); await expect(panel.getByRole("button", { name: "Détections suivantes", exact: true })).toBeDisabled();
  await panel.locator("article").first().screenshot({ path: info.outputPath("native-matching-detection-page.png") });
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  for (const control of await panel.locator("button,input,select,summary").all()) if (await control.isVisible()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false); expect(waitlistWrites).toBe(0);
});
