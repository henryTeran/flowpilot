import { expect, test } from "@playwright/test";
test.use({ actionTimeout: 15000 });
test("signed native current recipients refuse withdrawn push without replacing approval", async ({ page, request }, info) => {
  test.setTimeout(120000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token")), headers = { Authorization: `Bearer ${token}` };
  const api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve", prefix = info.project.name, base = `${api}/marketing/institutes/${institute}`;
  async function post(path: string, data: unknown) { const r = await request.post(path, { headers, data }); expect(r.status(), await r.text()).toBe(200); return r.json(); }
  const customer = await post(`${api}/customers/institutes/${institute}`, { display_name: `Recipients ${prefix}`, idempotency_key: `recipients-client-${prefix}` });
  const policies = `${api}/crm/institutes/${institute}/segment-policies`, prior = await (await request.get(policies + "/current", { headers })).json();
  await post(policies, { policy: { institute_id: institute, observation_us: 1209600000000, new_customer_us: 86400000000, at_risk_us: 172800000000,
    dormant_us: 604800000000, loyal_min_tickets: 2, vip_min_tickets: 3, vip_currency: "CHF", vip_gross_minor: "300" }, previous_policy_id: prior?.id || null,
    reason: "Explicit recipient source policy", idempotency_key: `recipients-policy-${prefix}` });
  const contactBase = `${base}/customers/${customer.id}/contact-declarations`;
  const first = await post(contactBase, { declaration: { institute_id: institute, customer_id: customer.id, purpose: "marketing",
    communications: ["email", "sms", "push"].map(channel => ({ channel, permission: channel === "push" ? "granted" : "unknown",
      permission_evidence: channel === "push" ? "Explicit push permission" : null, destination: channel === "push" ? { channel, email: null, phone: null,
        push_application: "fixture-app", push_token: `secret-${prefix}`, evidence: "Explicit destination" } : null })) }, previous_id: null,
    reason: "Explicit current contacts", idempotency_key: `recipients-contact-${prefix}` });
  const audience = await post(base + "/audience-captures", { segments: ["NEW"], channel: "push", permission_basis: "marketing_contact",
    reason: "Explicit push capture", idempotency_key: `recipients-audience-${prefix}` });
  const body = `Recipients ${prefix} literal push`;
  let campaign = await post(base + "/campaigns", { action: "create", campaign_id: null, expected_revision_id: null, content: { channel: "push", origin: "human",
    subject: null, body, audience_id: audience.id, template_original_id: null }, reason: "Explicit draft", idempotency_key: `recipients-draft-${prefix}` });
  for (const action of ["review", "approve"]) campaign = await post(base + "/campaigns", { action, campaign_id: campaign.revision.campaign_id,
    expected_revision_id: campaign.revision.id, content: null, reason: `Explicit ${action}`, idempotency_key: `recipients-${action}-${prefix}` });
  await page.getByRole("button", { name: "Marketing", exact: true }).click();
  await page.getByRole("button", { name: `${body} · Approuvée · push`, exact: true }).click();
  const panel = page.getByRole("region", { name: "Destinataires courants", exact: true });
  await panel.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  await expect(panel.locator("article")).toHaveCount(1); await expect(panel).toContainText("Accord et destination déclarés");
  await expect(panel).not.toContainText(`secret-${prefix}`);
  for (const button of await panel.locator("button").all()) expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await panel.screenshot({ path: info.outputPath("native-recipient-grant.png") });
  const declaration = structuredClone(first.declaration); declaration.communications[2].permission = "refused";
  declaration.communications[2].permission_evidence = "Explicit push withdrawal";
  await post(contactBase, { declaration, previous_id: first.id, reason: "Explicit withdrawal", idempotency_key: `recipients-withdraw-${prefix}` });
  await panel.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  await expect(panel).toContainText("Refus déclaré"); await expect(panel).toContainText("Non éligible");
  expect(await (await request.get(`${base}/campaigns/${campaign.revision.campaign_id}/current`, { headers })).json()).toEqual(campaign);
  expect(await (await request.get(contactBase + "/" + first.id, { headers })).json()).toEqual(first);
  await panel.screenshot({ path: info.outputPath("native-recipient-withdrawal.png") });
  await page.route("**/recipient-observations?**", async route => { const r = await route.fetch(), p = await r.json(); p.total++; await route.fulfill({ response: r, json: p }); });
  await panel.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  await expect(panel.getByRole("alert")).toBeVisible(); await expect(panel.locator("article")).toHaveCount(0);
  await page.unroute("**/recipient-observations?**");
  await panel.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  await expect(panel).toContainText("Refus déclaré"); await expect(panel.locator("article")).toHaveCount(1);
});
