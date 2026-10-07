import { expect, test } from "@playwright/test";

test("signed native SEND loses acknowledgement and recovers approved original without resubmission", async ({ page, request }, info) => {
  test.setTimeout(120000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1";
  const institute = "demo-institute-geneve", prefix = info.project.name, base = `${api}/marketing/institutes/${institute}`;
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
  for (const button of await actions.locator("button,input").all()) expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await history.screenshot({ path: info.outputPath("native-send-recovered.png") });
});
