import { expect, test } from "@playwright/test";

test("signed channel replacement pins SMS sources and requires renewed approval; unsupported push refuses", async ({ page, request }, info) => {
  test.setTimeout(120000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token")), headers = { Authorization: `Bearer ${token}` };
  const api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve", prefix = info.project.name;
  const base = `${api}/marketing/institutes/${institute}`;
  async function post(path: string, data: unknown) {
    const response = await request.post(path, { headers, data }); expect(response.status(), await response.text()).toBe(200); return response.json();
  }
  const customer = await post(`${api}/customers/institutes/${institute}`, { display_name: `Channels ${prefix}`, idempotency_key: `channels-client-${prefix}` });
  const policies = `${api}/crm/institutes/${institute}/segment-policies`, prior = await (await request.get(policies + "/current", { headers })).json();
  await post(policies, { policy: { institute_id: institute, observation_us: 1209600000000, new_customer_us: 86400000000,
    at_risk_us: 172800000000, dormant_us: 604800000000, loyal_min_tickets: 2, vip_min_tickets: 3, vip_currency: "CHF", vip_gross_minor: "300" },
    previous_policy_id: prior?.id || null, reason: "Explicit channel source segments", idempotency_key: `channels-policy-${prefix}` });
  await post(`${api}/crm/institutes/${institute}/customers/${customer.id}/lifecycle-declarations`, { declaration: { institute_id: institute, customer_id: customer.id,
    birthday: null, birthday_evidence: null, communications: ["email", "sms"].flatMap(channel => ["service_follow_up", "marketing"].map(purpose => ({ channel, purpose,
      permission: purpose === "marketing" ? "granted" : "unknown", evidence: purpose === "marketing" ? `Explicit ${channel} marketing fixture` : null }))) },
    previous_id: null, reason: "Explicit two-channel permissions", idempotency_key: `channels-permission-${prefix}` });
  const captures: Record<string, any> = {};
  for (const channel of ["email", "sms", "push"]) captures[channel] = await post(base + "/audience-captures", {
    segments: ["NEW"], channel, reason: `Channels ${prefix} ${channel}`, idempotency_key: `channels-audience-${prefix}-${channel}` });
  expect(captures.email.summary.eligible_count).toBeGreaterThan(0); expect(captures.sms.summary.eligible_count).toBeGreaterThan(0);
  expect(captures.push.summary.eligible_count).toBe(0);
  const templates: Record<string, any> = {};
  for (const channel of ["email", "sms", "push"]) templates[channel] = await post(base + "/templates", { template_id: null, previous_id: null,
    content: { name: `Channels template ${prefix} ${channel}`, channel, origin: "ai", subject: channel === "email" ? `Channels subject ${prefix}` : null,
      body: `Literal ${channel} {customer_name} 🙂` }, reason: "Explicit channel template", idempotency_key: `channels-template-${prefix}-${channel}` });
  let posts = 0;
  await page.route("**/campaigns", async route => { if (route.request().method() === "POST") posts++; await route.continue(); });
  await page.getByRole("button", { name: "Marketing", exact: true }).click();
  const creator = page.getByRole("region", { name: "Créer une campagne", exact: true });
  await creator.getByRole("button", { name: "Préparer une campagne", exact: true }).click();
  await creator.getByLabel("Canal de campagne").selectOption("push"); await creator.getByRole("button", { name: "Choisir une audience source", exact: true }).click();
  await expect(creator.getByRole("button", { name: new RegExp(`Channels ${prefix} push · push`) })).toBeDisabled();
  await expect(creator.getByRole("button", { name: "Enregistrer le brouillon", exact: true })).toBeDisabled(); expect(posts).toBe(0);
  const refused = await request.post(base + "/campaigns", { headers, data: { action: "create", campaign_id: null, expected_revision_id: null,
    content: { channel: "push", origin: "ai", subject: null, body: templates.push.content.body, audience_id: captures.push.id, template_original_id: templates.push.id },
    reason: "Unsupported push must refuse", idempotency_key: `channels-push-refusal-${prefix}` } });
  expect(refused.status()).toBe(400);
  expect(await (await request.get(`${base}/campaigns/original/channels-push-refusal-${prefix}`, { headers })).json()).toBeNull();
  await creator.getByLabel("Canal de campagne").selectOption("email"); await creator.getByRole("button", { name: "Choisir une audience source", exact: true }).click();
  await expect(creator.getByRole("button", { name: new RegExp(`Channels ${prefix} sms · sms`) })).toBeDisabled();
  await creator.getByRole("button", { name: new RegExp(`Channels ${prefix} email · email`) }).click();
  await creator.getByLabel("Source du texte").selectOption("template"); await creator.getByRole("button", { name: "Choisir un template source", exact: true }).click();
  await expect(creator.getByRole("button", { name: `Channels template ${prefix} sms · sms`, exact: true })).toBeDisabled();
  await creator.getByRole("button", { name: `Channels template ${prefix} email · email`, exact: true }).click();
  await creator.getByLabel("Motif du brouillon").fill("Explicit email source draft"); await creator.getByRole("button", { name: "Enregistrer le brouillon", exact: true }).click();
  await expect(creator).toContainText("Brouillon original vérifié"); expect(posts).toBe(1);
  const subject = templates.email.content.subject;
  await page.getByRole("button", { name: `${subject} · Brouillon · email`, exact: true }).click();
  const history = page.getByRole("region", { name: "Historique de campagne", exact: true }), actions = history.getByRole("region", { name: "Validation de campagne", exact: true });
  async function approve() {
    await expect(actions.getByRole("button", { name: "Soumettre en revue", exact: true })).toBeEnabled();
    await actions.getByLabel("Motif de validation").fill("Explicit channel review"); await actions.getByRole("button", { name: "Soumettre en revue", exact: true }).click();
    await expect(actions.getByRole("button", { name: "Approuver le contenu et l’audience", exact: true })).toBeEnabled();
    await actions.getByLabel("Motif de validation").fill("Explicit channel approval"); await actions.getByRole("button", { name: "Approuver le contenu et l’audience", exact: true }).click();
    await expect(history).toContainText("Approuvée"); await expect(actions.getByRole("button", { name: "Approuver le contenu et l’audience", exact: true })).toBeDisabled();
  }
  await approve(); await expect(history.locator("article")).toHaveCount(3); expect(posts).toBe(3);
  const firstCatalog = await (await request.get(base + "/campaigns", { headers })).json();
  const emailApproval = firstCatalog.items.find((o: any) => o.revision.content.subject === subject), root = emailApproval.revision.campaign_id;
  const editor = history.getByRole("region", { name: "Modifier la campagne", exact: true });
  await editor.getByRole("button", { name: "Préparer une correction de campagne", exact: true }).click();
  await expect(editor.getByLabel("Texte de campagne")).toHaveValue(templates.email.content.body);
  await editor.getByLabel("Canal de campagne").selectOption("sms"); await expect(editor.getByLabel("Objet de campagne")).toHaveCount(0);
  await expect(editor.getByRole("button", { name: "Enregistrer la correction de campagne", exact: true })).toBeDisabled();
  await editor.getByRole("button", { name: "Choisir une audience source", exact: true }).click();
  await expect(editor.getByRole("button", { name: new RegExp(`Channels ${prefix} email · email`) })).toBeDisabled();
  await editor.getByRole("button", { name: new RegExp(`Channels ${prefix} sms · sms`) }).click();
  await editor.getByRole("button", { name: "Choisir un template source", exact: true }).click();
  await expect(editor.getByRole("button", { name: `Channels template ${prefix} email · email`, exact: true })).toBeDisabled();
  await page.route(`**/templates/${templates.sms.id}`, async route => { const response = await route.fetch(), data = await response.json();
    data.content.body += " forged"; data.request.content.body += " forged"; await route.fulfill({ response, json: data }); });
  await editor.getByRole("button", { name: `Channels template ${prefix} sms · sms`, exact: true }).click();
  await expect(editor).toContainText("Template source à vérifier"); await expect(editor.getByRole("button", { name: "Enregistrer la correction de campagne", exact: true })).toBeDisabled();
  expect(posts).toBe(3); await page.unroute(`**/templates/${templates.sms.id}`);
  await editor.getByRole("button", { name: `Channels template ${prefix} sms · sms`, exact: true }).click();
  await expect(editor.getByLabel("Texte de campagne")).toHaveValue(templates.sms.content.body); await expect(editor.getByLabel("Texte de campagne")).toBeDisabled();
  await editor.getByLabel("Motif du brouillon").fill("Explicit replacement with SMS sources");
  for (const control of await editor.locator("button,input,select,textarea").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await editor.screenshot({ path: info.outputPath("native-campaign-sms-source.png") });
  await editor.getByRole("button", { name: "Enregistrer la correction de campagne", exact: true }).click();
  await expect(history.locator("article")).toHaveCount(4); expect(posts).toBe(4);
  const smsDraft = await (await request.get(`${base}/campaigns/${root}/current`, { headers })).json();
  expect(smsDraft.revision.previous_id).toBe(emailApproval.revision.id); expect(smsDraft.revision.content.channel).toBe("sms");
  expect(smsDraft.revision.content.subject).toBeNull(); expect(smsDraft.revision.content.audience.id).toBe(captures.sms.id);
  expect(smsDraft.revision.content.template_original_id).toBe(templates.sms.id); expect(smsDraft.revision.content.body).toBe(templates.sms.content.body);
  expect(smsDraft.revision.reviewed_digest).toBeNull(); expect(smsDraft.revision.approved_digest).toBeNull();
  await expect(actions.getByRole("button", { name: "Approuver le contenu et l’audience", exact: true })).toBeDisabled();
  await approve(); await expect(history.locator("article")).toHaveCount(6); expect(posts).toBe(6);
  const smsApproval = await (await request.get(`${base}/campaigns/${root}/current`, { headers })).json();
  expect(smsApproval.revision.state).toBe("APPROVE"); expect(smsApproval.revision.approved_digest).toBe(smsApproval.revision.reviewed_digest);
  expect(smsApproval.revision.approved_digest).not.toBe(emailApproval.revision.approved_digest);
  expect(smsApproval.revision.external_message_sent).toBe(false); expect(smsApproval.revision.delivery_authorized).toBe(false);
  expect(await (await request.get(`${base}/campaigns/${emailApproval.revision.id}`, { headers })).json()).toEqual(emailApproval);
  const correctedTemplate = await post(base + "/templates", { template_id: templates.sms.template_id, previous_id: templates.sms.id,
    content: { ...templates.sms.content, body: "New template body cannot replace an approved campaign" }, reason: "Explicit later template correction",
    idempotency_key: `channels-later-template-${prefix}` }); expect(correctedTemplate.id).not.toBe(templates.sms.id);
  await history.getByRole("button", { name: "Actualiser l’historique", exact: true }).click(); await expect(history.locator("article")).toHaveCount(6);
  expect(await (await request.get(`${base}/campaigns/${root}/current`, { headers })).json()).toEqual(smsApproval);
  await history.screenshot({ path: info.outputPath("native-campaign-sms-approved.png") });
});
