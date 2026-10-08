import { expect as baseExpect, test } from "@playwright/test";
import { optimizerFactors, optimizerBases } from "../src/optimizer-policy-utils";
const expect = baseExpect.configure({ timeout: 20000 });
test.setTimeout(240000);
test.use({ actionTimeout: 20000 });
test("signed current score review binds source and policy, preserves unknowns/refusals and rejects stale or corrupt reports", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  const waitlist = `/waitlist/institutes/${institute}`, optimizer = `/optimizer/institutes/${institute}`;
  async function post(path: string, data: unknown) { const response = await request.post(`${api}${path}`, { headers, data }); expect(response.status(), await response.text()).toBe(200); return response.json(); }
  const customer = await post(`/customers/institutes/${institute}`, { display_name: `Scores ${info.project.name}`, idempotency_key: `score-customer-${info.project.name}` });
  const services = await (await request.get(`${api}/services/catalog`, { headers })).json();
  const service = services.find((s: any) => s.status === "active" && !s.requires_machine && s.duration_min > 0);
  async function declare(day: string) { return post(`${waitlist}/originals`, { customer_id: customer.id, service_id: service.id, duration_minutes: service.duration_min,
    availability: [{ start: `2030-01-${day}T09:00:00Z`, end: `2030-01-${day}T11:00:00Z` }], allowed_employee_ids: [], constraints_review: "confirmed",
    availability_evidence: "Disponibilité déclarée", constraints_evidence: "Contraintes relues", reason: `Scores ${info.project.name} ${day}`, idempotency_key: `score-demand-${info.project.name}-${day}` }); }
  const root = await declare("02");
  const activated = await post(`${waitlist}/lifecycle/originals`, { root_id: root.original.id, root_fingerprint: root.fingerprint,
    previous_id: null, previous_fingerprint: null, action: "activate", target_id: root.original.id, target_fingerprint: root.fingerprint,
    reason: "Activation pour revue des scores", idempotency_key: `score-activate-${info.project.name}` });
  async function createPolicy(factor: string) { return post(`${optimizer}/policy-originals`, { reason: `Politique ${factor} ${info.project.name}`, idempotency_key: `score-policy-${factor}-${info.project.name}`,
    terms: { normalization: "exact_unit_interval_explicit_ceiling_saturation", rules: optimizerFactors.map(f => ({ factor: f, weight: { numerator: f === factor ? "1" : "0", denominator: "1" },
      basis: f === factor ? optimizerBases[f] : "disabled", ceiling: f === factor && f === "revenue_score" ? "10000" : null,
      currency: f === factor && f === "revenue_score" ? "CHF" : null, price_mode: f === factor && f === "revenue_score" ? "member" : null, reason: "Hypothèse de scoring relue" })) } }); }
  const known = await createPolicy("utilization_score"), unknown = await createPolicy("revenue_score");
  const calls: { body: any; status: number; result: any }[] = []; let corrupt = false, writes = 0;
  await page.route("**/optimizer/**", async route => {
    if (!route.request().url().endsWith("/reviews/current")) { if (route.request().method() !== "GET") writes++; await route.continue(); return; }
    const response = await route.fetch(), value = await response.json(); calls.push({ body: route.request().postDataJSON(), status: response.status(), result: structuredClone(value) });
    if (corrupt && response.ok()) { value.review.options[0].score.numerator = "999"; await route.fulfill({ response, json: value }); }
    else await route.fulfill({ response });
  });
  await page.route("**/waitlist/**", async route => { if (route.request().method() !== "GET") writes++; await route.continue(); });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  const matching = page.getByRole("region", { name: "Revue des créneaux de liste d’attente", exact: true });
  const history = page.getByRole("region", { name: "États de liste d’attente conservés", exact: true });
  const policies = page.getByRole("region", { name: "Politique de scoring des créneaux", exact: true });
  const score = page.getByRole("region", { name: "Scores des créneaux sous hypothèses", exact: true });
  const calculate = score.getByRole("button", { name: "Relire les sources et calculer les scores", exact: true });
  await expect(calculate).toBeDisabled(); expect(calls).toHaveLength(0);
  async function choosePolicy(receipt: any) {
    await policies.getByRole("button", { name: "Lire les politiques conservées", exact: true }).click();
    await policies.locator("article").filter({ has: page.getByRole("heading", { name: receipt.original.reason, exact: true }) }).getByRole("button", { name: "Choisir cette politique pour la revue", exact: true }).click();
  }
  async function chooseRoot() {
    await history.getByRole("button", { name: "Lire les états de liste d’attente", exact: true }).click();
    await history.locator("article").filter({ has: page.getByRole("heading", { name: root.original.reason, exact: true }) }).getByRole("button", { name: "Examiner les créneaux actuels", exact: true }).click();
  }
  await choosePolicy(known); await chooseRoot();
  await matching.getByLabel("Fin de l’horizon — date", { exact: true }).fill("2030-01-03"); await matching.getByLabel("Fin de l’horizon — heure", { exact: true }).fill("12:00");
  await matching.getByRole("combobox", { name: /^Canal de suivi/ }).selectOption("email");
  await matching.getByRole("combobox", { name: /^Règle d’historique/ }).selectOption("review_only");
  await matching.getByRole("combobox", { name: /^Règle d’accord de suivi/ }).selectOption("review_only");
  const examine = matching.getByRole("button", { name: "Examiner la liste sélectionnée", exact: true });
  await examine.click(); await expect(calculate).toBeEnabled(); expect(calls).toHaveLength(0);
  await calculate.click(); await expect(score).toContainText("Classement complet");
  const first = calls[0]; expect(first.status).toBe(200); expect(first.body.policy_id).toBe(known.original.id); expect(first.body.policy_fingerprint).toBe(known.fingerprint);
  expect(first.body.expected_event_id).toBe(activated.original.id); expect(first.body.expected_event_fingerprint).toBe(activated.fingerprint);
  expect(Object.keys(first.body).sort()).toEqual(["expected_event_fingerprint", "expected_event_id", "horizon_end", "matching_policy", "policy_fingerprint", "policy_id", "root_id"]);
  const actual = first.result.review.options[0].score; await expect(score.locator("article").first()).toContainText(`Score exact : ${actual.numerator}/${actual.denominator}`);
  await expect(score).toContainText("Ressources distinctes compatibles"); await score.locator("article").first().screenshot({ path: info.outputPath("native-optimizer-score.png") });
  for (const control of await score.locator("button,summary").all()) if (await control.isVisible()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect((await score.boundingBox())!.width).toBeGreaterThanOrEqual(600); expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false);
  corrupt = true; await calculate.click(); await expect(score.getByRole("alert")).toBeVisible(); await expect(score.locator("article")).toHaveCount(0);
  corrupt = false; await calculate.click(); await expect(score).toContainText("Classement complet");
  await choosePolicy(unknown); await expect(score.locator("article")).toHaveCount(0); await expect(calculate).toBeEnabled(); await calculate.click();
  await expect(score).toContainText("Classement indisponible"); await expect(score).toContainText("Score indisponible"); await score.locator("article").first().screenshot({ path: info.outputPath("native-optimizer-unknown.png") });
  await choosePolicy(known); await matching.getByRole("combobox", { name: /^Règle d’accord de suivi/ }).selectOption("recorded_grant_required");
  await expect(calculate).toBeDisabled(); await expect(score.locator("article")).toHaveCount(0); await examine.click(); await expect(calculate).toBeEnabled(); await calculate.click();
  await expect(score).toContainText("Accord de suivi insuffisant"); await expect(score.locator("article")).toHaveCount(0); await score.screenshot({ path: info.outputPath("native-optimizer-refusal.png") });
  await matching.getByRole("combobox", { name: /^Règle d’accord de suivi/ }).selectOption("review_only"); await examine.click(); await expect(calculate).toBeEnabled();
  const replacement = await declare("03");
  const peer = await post(`${waitlist}/lifecycle/originals`, { root_id: root.original.id, root_fingerprint: root.fingerprint, previous_id: activated.original.id, previous_fingerprint: activated.fingerprint,
    action: "revise", target_id: replacement.original.id, target_fingerprint: replacement.fingerprint, reason: "Révision concurrente relue", idempotency_key: `score-peer-${info.project.name}` });
  await calculate.click(); await expect(score.getByRole("alert")).toContainText("version a changé"); expect(calls.at(-1)!.status).toBe(400); await expect(score.locator("article")).toHaveCount(0);
  await chooseRoot(); await examine.click(); await expect(calculate).toBeEnabled(); const before = calls.length; await calculate.click(); await expect(score).toContainText("Classement complet");
  expect(calls.length).toBe(before+1); expect(calls.at(-1)!.body.expected_event_id).toBe(peer.original.id); expect(calls.at(-1)!.body.expected_event_fingerprint).toBe(peer.fingerprint);
  await matching.getByLabel("Fin de l’horizon — heure", { exact: true }).fill("13:00"); await expect(calculate).toBeDisabled(); await expect(score.locator("article")).toHaveCount(0); expect(writes).toBe(0);
});
