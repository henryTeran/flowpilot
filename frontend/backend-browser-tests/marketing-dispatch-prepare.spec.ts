import { expect, test } from "@playwright/test";

test("signed native preparation paginates accounts loses reply and recovers intent after reload", async ({ page, request }, info) => {
  test.skip(process.env.FLOWPILOT_BROWSER_MARKETING_FIXTURE !== "1", "Explicit owned marketing fixture profile required");
  test.setTimeout(120000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1";
  const institute = "demo-institute-geneve", prefix = info.project.name + "-prepare", base = `${api}/marketing/institutes/${institute}`;
  const customerReply = await request.post(`${api}/customers/institutes/${institute}`, { headers, data: { display_name: `SEND ${prefix}`, idempotency_key: `send-customer-${prefix}` } });
  expect(customerReply.status()).toBe(200); const customer = await customerReply.json();
  const policies = `${api}/crm/institutes/${institute}/segment-policies`;
  const previous = await (await request.get(policies + "/current", { headers })).json();
  const policy = await request.post(policies, { headers, data: { policy: { institute_id: institute, observation_us: 1209600000000, new_customer_us: 86400000000,
    at_risk_us: 172800000000, dormant_us: 604800000000, loyal_min_tickets: 2, vip_min_tickets: 3, vip_currency: "CHF", vip_gross_minor: "300" },
    previous_policy_id: previous?.id || null, reason: "Explicit SEND segments", idempotency_key: `send-policy-${prefix}` } }); expect(policy.status()).toBe(200);
  const communications = ["email", "sms"].flatMap(channel => ["service_follow_up", "marketing"].map(purpose => ({ channel, purpose,
    permission: channel === "email" && purpose === "marketing" ? "granted" : "unknown", evidence: channel === "email" && purpose === "marketing" ? "Explicit SEND fixture" : null })));
  const declared = await request.post(`${api}/crm/institutes/${institute}/customers/${customer.id}/lifecycle-declarations`, { headers, data: {
    declaration: { institute_id: institute, customer_id: customer.id, birthday: null, birthday_evidence: null, communications }, previous_id: null,
    reason: "Explicit SEND permission", idempotency_key: `send-permission-${prefix}` } }); expect(declared.status()).toBe(200);
  const captureReply = await request.post(base + "/audience-captures", { headers, data: { segments: ["NEW"], channel: "email", reason: "SEND retained source", idempotency_key: `send-audience-${prefix}` } });
  expect(captureReply.status()).toBe(200); const capture = await captureReply.json(), subject = `SEND subject ${prefix}`;
  let original: any;
  for (const action of ["create", "review", "approve"]) {
    const response = await request.post(base + "/campaigns", { headers, data: { action, campaign_id: original?.revision.campaign_id || null,
      expected_revision_id: original?.revision.id || null,
      content: action === "create" ? { channel: "email", origin: "ai", subject, body: "Explicit approved literal SEND content", audience_id: capture.id, template_original_id: null } : null,
      reason: `Explicit ${action} fixture`, idempotency_key: `send-${action}-${prefix}` } });
    expect(response.status()).toBe(200); original = await response.json();
  }
  const approval = original;
  async function open() {
    await page.getByRole("button", { name: "Marketing", exact: true }).click();
    const marketing = page.getByRole("region", { name: "Marketing", exact: true });
    const catalog = await (await request.get(base + "/campaigns?limit=1", { headers })).json();
    const selected = page.getByRole("button", { name: `${subject} · ${original.revision.state === "SEND" ? "Envoi autorisé" : "Approuvée"} · email`, exact: true });
    for (let offset = 0; offset < catalog.total; offset += 20) {
      await expect(marketing).toContainText(`${offset + 1}–${Math.min(offset + 20, catalog.total)} sur ${catalog.total} campagnes`);
      if (await selected.count()) { await selected.click(); return; }
      await marketing.getByRole("button", { name: "Campagnes suivantes", exact: true }).click();
    }
    throw new Error("Expected retained campaign absent from bounded native catalog");
  }
  await open();
  const actions = page.getByRole("region", { name: "Validation de campagne", exact: true });
  const history = page.getByRole("region", { name: "Historique de campagne", exact: true });
  await expect(actions.getByRole("button", { name: "Autoriser l’envoi", exact: true })).toBeEnabled();
  let posts = 0; let markLost!: () => void; const lost = new Promise<void>(resolve => { markLost = resolve; });
  await page.route("**/campaigns", async route => {
    if (route.request().method() !== "POST") return route.continue();
    posts++; expect(route.request().postDataJSON().action).toBe("send");
    const response = await route.fetch(); expect(response.status()).toBe(200); original = await response.json();
    await route.abort("failed"); markLost();
  });
  await actions.getByLabel("Motif de validation").fill("Explicit native SEND authorization");
  await actions.getByRole("button", { name: "Autoriser l’envoi", exact: true }).click(); await lost;
  await expect(actions.getByRole("button", { name: "Reprendre la validation conservée", exact: true })).toBeEnabled();
  await page.reload(); await open();
  await page.route(`**/campaigns/${approval.revision.id}`, async route => {
    const response = await route.fetch(); const value = await response.json(); value.revision.actor_id = "forged"; value.revision.state = "REVIEW";
    await route.fulfill({ response, json: value });
  });
  await actions.getByRole("button", { name: "Reprendre la validation conservée", exact: true }).click();
  await expect(actions).toContainText("Approbation d’origine à vérifier"); expect(posts).toBe(1);
  expect(await page.evaluate(() => Object.keys(sessionStorage).some(key => key.startsWith("flowpilot.marketing-campaign-request:")))).toBe(true);
  await page.unroute(`**/campaigns/${approval.revision.id}`);
  await actions.getByRole("button", { name: "Reprendre la validation conservée", exact: true }).click();
  await expect(actions).toContainText("Original vérifié"); await expect(history.locator("article")).toHaveCount(4); expect(posts).toBe(1);
  await expect(actions.getByRole("button", { name: "Autoriser l’envoi", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Préparer une correction de campagne", exact: true })).toBeDisabled();
  expect(original.revision.previous_id).toBe(approval.revision.id); expect(original.revision.content).toEqual(approval.revision.content);
  expect(original.revision.approved_digest).toBe(approval.revision.approved_digest);
  expect(original.revision.external_message_sent).toBe(false); expect(original.revision.delivery_authorized).toBe(false);
  expect(await (await request.get(`${base}/campaigns/${approval.revision.id}`, { headers })).json()).toEqual(approval);
  expect(await page.evaluate(() => Object.keys(sessionStorage).some(key => key.startsWith("flowpilot.marketing-campaign-request:")))).toBe(false);
  const contactPath = `${base}/customers/${customer.id}/contact-declarations`;
  const declaration = { institute_id: institute, customer_id: customer.id, purpose: "marketing", communications: ["email", "sms", "push"].map(channel => ({
    channel, permission: channel === "email" ? "granted" : "unknown", permission_evidence: channel === "email" ? "Explicit current SEND permission" : null,
    destination: channel === "email" ? { channel, email: "recipient@example.com", phone: null, push_application: null, push_token: null, evidence: "Explicit SEND endpoint" } : null })) };
  const contactReply = await request.post(contactPath, { headers, data: { declaration, previous_id: null, reason: "Explicit SEND recipient", idempotency_key: `send-contact-${prefix}` } });
  expect(contactReply.status()).toBe(200); const contact = await contactReply.json();
  const recipients = page.getByRole("region", { name: "Destinataires courants", exact: true });
  await recipients.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  const own = recipients.locator("article").filter({ hasText: `Cliente ${customer.id}` });
  await expect(own).toContainText("Accord et destination déclarés");
  await expect(own).toContainText("Éligible selon la déclaration lue");
  let intentPosts = 0, intent: any; let markIntentLost!: () => void;
  const intentLost = new Promise<void>(resolve => { markIntentLost = resolve; });
  await page.route("**/dispatch-intents", async route => {
    if (route.request().method() !== "POST") return route.continue(); intentPosts++;
    const response = await route.fetch(); expect(response.status(), await response.text()).toBe(200); intent = await response.json();
    await route.abort("failed"); markIntentLost();
  });
  const preparation = own.getByRole("region", { name: "Préparation de destinataire", exact: true });
  await preparation.getByRole("button", { name: "Choisir un compte autorisé", exact: true }).click();
  await expect(preparation).toContainText("25 comptes · page à partir de 1");
  await expect(preparation.getByLabel("Compte de préparation").locator("option")).toHaveCount(21);
  await preparation.getByRole("button", { name: "Comptes suivants", exact: true }).click();
  await expect(preparation).toContainText("25 comptes · page à partir de 21");
  await expect(preparation.getByLabel("Compte de préparation").locator("option")).toHaveCount(6);
  await preparation.getByLabel("Compte de préparation").selectOption("browser-test-account");
  await preparation.getByLabel("Motif de préparation").fill("Explicit native post-SEND preparation");
  for (const control of await preparation.locator("button,input,select").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await preparation.screenshot({ path: info.outputPath("native-preparation-selection.png") });
  await preparation.getByRole("button", { name: "Conserver l’intention", exact: true }).click(); await intentLost;
  await expect(preparation.getByRole("button", { name: "Reprendre la préparation conservée", exact: true })).toBeEnabled();
  expect(intentPosts).toBe(1);
  const pending = await page.evaluate(() => Object.entries(sessionStorage).filter(([key]) => key.startsWith("flowpilot.marketing-dispatch-request:")));
  expect(pending).toHaveLength(1); expect(Object.keys(JSON.parse(pending[0][1])).sort()).toEqual(["account", "request"]);
  const withdrawn = structuredClone(declaration); withdrawn.communications[0].permission = "refused";
  const withdrawalReply = await request.post(contactPath, { headers, data: { declaration: withdrawn, previous_id: contact.id, reason: "Explicit withdrawal before intent recovery", idempotency_key: `send-withdraw-${prefix}` } });
  expect(withdrawalReply.status()).toBe(200);
  await page.reload(); await open();
  await recipients.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  await expect(own).toContainText("Refus déclaré");
  await page.route(`**/dispatch-intents/${intent.id}`, async route => {
    const response = await route.fetch(); const value = await response.json(); value.request_fingerprint = "0".repeat(64);
    await route.fulfill({ response, json: value });
  });
  await preparation.getByRole("button", { name: "Reprendre la préparation conservée", exact: true }).click();
  await expect(preparation).toContainText("Originaux de préparation à vérifier"); expect(intentPosts).toBe(1);
  await page.unroute(`**/dispatch-intents/${intent.id}`);
  await preparation.getByRole("button", { name: "Reprendre la préparation conservée", exact: true }).click();
  await expect(preparation).toContainText("Intention originale vérifiée"); expect(intentPosts).toBe(1);
  expect(intent.submission.actor_id).toBe("browser-manager"); expect(intent.submission.account.mode).toBe("test");
  expect(intent.request.expected_revision_id).toBe(approval.revision.id); expect(intent.submission.eligibility.campaign).toEqual(approval.revision);
  expect(intent.submission.eligibility.original).toEqual(contact);
  expect(await page.evaluate(() => Object.keys(sessionStorage).some(key => key.startsWith("flowpilot.marketing-dispatch-request:")))).toBe(false);
  for (const control of await preparation.locator("button,input,select").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await history.screenshot({ path: info.outputPath("native-preparation-recovered.png") });
  await recipients.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  await expect(own).toContainText("Refus déclaré"); await expect(own).toContainText("Non éligible");
  expect(await (await request.get(contactPath + `/${contact.id}`, { headers })).json()).toEqual(contact);
  expect(await (await request.get(`${base}/dispatch-intents/${intent.id}`, { headers })).json()).toEqual(intent);
  expect(await (await request.get(`${base}/campaigns/${original.revision.campaign_id}/current`, { headers })).json()).toEqual(original);
  await page.route("**/recipient-observations?**", async route => {
    const response = await route.fetch(); const value = await response.json();
    value.items.find((item: any) => item.customer.customer_id === customer.id).eligible_by_current_declaration = true;
    await route.fulfill({ response, json: value });
  });
  await recipients.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  await expect(recipients).toContainText("Destinataires à vérifier"); await expect(recipients.locator("article")).toHaveCount(0);
  await page.unroute("**/recipient-observations?**");
  await recipients.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  await expect(own).toContainText("Non éligible");
  for (const button of await actions.locator("button,input").all()) expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await history.screenshot({ path: info.outputPath("native-preparation-withdrawn.png") });

  const retained = history.getByRole("region", { name: "Intentions conservées", exact: true });
  await retained.getByRole("button", { name: "Vérifier les intentions conservées", exact: true }).click();
  await expect(retained).toContainText(intent.id);
  await expect(retained).toContainText("1 sur 1 intentions");
  const outcomes = retained.getByRole("region", { name: "Résultats conservés", exact: true });
  await outcomes.getByRole("button", { name: "Vérifier les résultats conservés", exact: true }).click();
  await expect(outcomes).toContainText("Aucun résultat conservé. Aucun envoi prouvé.");
  await page.route(`**/dispatch-intents/${intent.id}`, async route => {
    const response = await route.fetch(); const value = await response.json(); value.request_fingerprint = "0".repeat(64);
    await route.fulfill({ response, json: value });
  });
  await retained.getByRole("button", { name: "Vérifier les intentions conservées", exact: true }).click();
  await expect(retained).toContainText("Intentions conservées à vérifier");
  await expect(retained.locator("article")).toHaveCount(0);
  await page.unroute(`**/dispatch-intents/${intent.id}`);
  await retained.getByRole("button", { name: "Vérifier les intentions conservées", exact: true }).click();
  await expect(retained).toContainText(intent.id); expect(intentPosts).toBe(1);
  for (const control of await retained.locator("button").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await retained.screenshot({ path: info.outputPath("native-retained-intents.png") });

});
