import { expect, test } from "@playwright/test";
test("signed native campaign sources draft recovery review approval and immutable audit", async ({ page, request }, info) => {
  test.setTimeout(120000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token")), headers = { Authorization: `Bearer ${token}` };
  const api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve", prefix = info.project.name;
  const customerReply = await request.post(`${api}/customers/institutes/${institute}`, { headers, data: { display_name: `Campaign ${prefix}`, idempotency_key: `campaign-client-${prefix}` } });
  expect(customerReply.status()).toBe(200); const customer = await customerReply.json();
  const policies = `${api}/crm/institutes/${institute}/segment-policies`, before = await request.get(policies + "/current", { headers }), previous = await before.json();
  const policy = await request.post(policies, { headers, data: { policy: { institute_id: institute, observation_us: 1209600000000, new_customer_us: 86400000000,
    at_risk_us: 172800000000, dormant_us: 604800000000, loyal_min_tickets: 2, vip_min_tickets: 3, vip_currency: "CHF", vip_gross_minor: "300" },
    previous_policy_id: previous?.id || null, reason: "Explicit campaign source segments", idempotency_key: `campaign-policy-${prefix}` } }); expect(policy.status()).toBe(200);
  const communications = ["email", "sms"].flatMap(channel => ["service_follow_up", "marketing"].map(purpose => ({ channel, purpose,
    permission: channel === "email" && purpose === "marketing" ? "granted" : "unknown", evidence: channel === "email" && purpose === "marketing" ? "Explicit campaign fixture permission" : null })));
  const declared = await request.post(`${api}/crm/institutes/${institute}/customers/${customer.id}/lifecycle-declarations`, { headers, data: {
    declaration: { institute_id: institute, customer_id: customer.id, birthday: null, birthday_evidence: null, communications }, previous_id: null,
    reason: "Explicit campaign permission", idempotency_key: `campaign-permission-${prefix}` } }); expect(declared.status()).toBe(200);
  const base = `${api}/marketing/institutes/${institute}`;
  const captureReply = await request.post(base + "/audience-captures", { headers, data: { segments: ["NEW"], channel: "email", reason: `Source ${prefix}`, idempotency_key: `campaign-audience-${prefix}` } });
  expect(captureReply.status()).toBe(200); const capture = await captureReply.json();
  const subject = `Campaign subject ${prefix}`, body = " Bonjour {customer_name}\n🙂 literal ";
  const templateReply = await request.post(base + "/templates", { headers, data: { template_id: null, previous_id: null,
    content: { name: `Source template ${prefix}`, channel: "email", origin: "ai", subject, body }, reason: "Explicit retained template", idempotency_key: `campaign-template-${prefix}` } });
  expect(templateReply.status()).toBe(200); const template = await templateReply.json();
  async function open() { await page.getByRole("button", { name: "Marketing", exact: true }).click(); }
  await open(); const creator = page.getByRole("region", { name: "Créer une campagne", exact: true });
  await creator.getByRole("button", { name: "Préparer une campagne", exact: true }).click(); await creator.getByLabel("Canal de campagne").selectOption("email");
  await creator.getByRole("button", { name: "Choisir une audience source", exact: true }).click();
  await creator.getByRole("button", { name: new RegExp(`Source ${prefix} · email`) }).click(); await expect(creator).toContainText(capture.id);
  await creator.getByLabel("Source du texte").selectOption("template"); await creator.getByRole("button", { name: "Choisir un template source", exact: true }).click();
  await creator.getByRole("button", { name: `Source template ${prefix} · email`, exact: true }).click();
  await expect(creator.getByLabel("Texte de campagne")).toHaveValue(body); await expect(creator.getByLabel("Texte de campagne")).toBeDisabled();
  await creator.getByLabel("Motif du brouillon").fill("Explicit source-bound draft");
  for (const control of await creator.locator("button,input,select,textarea").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await creator.screenshot({ path: info.outputPath("native-campaign-draft.png") });
  let posts = 0, draft: any, edited: any;
  let markLost!: () => void, markEditLost!: () => void;
  const firstLost = new Promise<void>(resolve => { markLost = resolve; }), editLost = new Promise<void>(resolve => { markEditLost = resolve; });
  await page.route("**/campaigns", async route => {
    if (route.request().method() !== "POST") return route.continue(); posts++;
    const response = await route.fetch(); expect(response.status()).toBe(200); const data = await response.json();
    if (posts === 1) { draft = data; await route.abort("failed"); markLost(); return; }
    if (posts === 4) { edited = data; await route.abort("failed"); markEditLost(); return; }
    return route.fulfill({ response });
  });
  await creator.getByRole("button", { name: "Enregistrer le brouillon", exact: true }).click(); await firstLost;
  await expect(creator.getByRole("button", { name: "Reprendre le brouillon conservé", exact: true })).toBeEnabled();
  await page.reload(); await open(); await creator.getByRole("button", { name: "Reprendre le brouillon conservé", exact: true }).click();
  await expect(creator).toContainText("Brouillon original vérifié"); expect(posts).toBe(1);
  expect(draft.revision.content.audience.id).toBe(capture.id); expect(draft.revision.content.template_original_id).toBe(template.id); expect(draft.revision.content.body).toBe(body);
  await page.getByRole("button", { name: `${subject} · Brouillon · email`, exact: true }).click();
  const history = page.getByRole("region", { name: "Historique de campagne", exact: true }), actions = page.getByRole("region", { name: "Validation de campagne", exact: true });
  await expect(actions.getByRole("button", { name: "Soumettre en revue", exact: true })).toBeEnabled();
  await expect(actions.getByRole("button", { name: "Approuver le contenu et l’audience", exact: true })).toBeDisabled();
  await actions.getByLabel("Motif de validation").fill("Explicit native review"); await actions.getByRole("button", { name: "Soumettre en revue", exact: true }).click();
  await expect(actions.getByRole("button", { name: "Approuver le contenu et l’audience", exact: true })).toBeEnabled();
  await actions.getByLabel("Motif de validation").fill("Explicit native approval"); await actions.getByRole("button", { name: "Approuver le contenu et l’audience", exact: true }).click();
  await expect(history.locator("article")).toHaveCount(3); await expect(history).toContainText("Approuvée"); expect(posts).toBe(3);
  const old = await request.get(`${base}/campaigns/${draft.revision.id}`, { headers }); expect(await old.json()).toEqual(draft);
  const headReply = await request.get(`${base}/campaigns/${draft.revision.campaign_id}/current`, { headers }); const head = await headReply.json();
  expect(head.revision.state).toBe("APPROVE"); expect(head.revision.approved_digest).toBe(head.revision.reviewed_digest); expect(head.revision.external_message_sent).toBe(false);
  expect(await page.evaluate(() => Object.keys(sessionStorage).some(k => k.startsWith("flowpilot.marketing-campaign-create-request:") || k.startsWith("flowpilot.marketing-campaign-request:")))).toBe(false);
  await history.screenshot({ path: info.outputPath("native-campaign-approved.png") });
  const editor = page.getByRole("region", { name: "Modifier la campagne", exact: true });
  await editor.getByRole("button", { name: "Préparer une correction de campagne", exact: true }).click();
  await expect(editor.getByLabel("Texte de campagne")).toHaveValue(body); await expect(editor.getByLabel("Source du texte")).toHaveValue("template");
  await editor.getByLabel("Source du texte").selectOption("literal"); await editor.getByLabel("Origine de campagne").selectOption("human");
  await editor.getByLabel("Texte de campagne").fill("Explicit edited content {customer_name}"); await editor.getByLabel("Motif du brouillon").fill("Explicit approved campaign correction");
  for (const control of await editor.locator("button,input,select,textarea").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await editor.screenshot({ path: info.outputPath("native-campaign-edit.png") });
  await editor.getByRole("button", { name: "Enregistrer la correction de campagne", exact: true }).click(); await editLost;
  await expect(editor.getByRole("button", { name: "Reprendre la correction conservée", exact: true })).toBeEnabled();
  await page.reload(); await open(); await page.getByRole("button", { name: `${subject} · Brouillon · email`, exact: true }).click();
  await editor.getByRole("button", { name: "Reprendre la correction conservée", exact: true }).click();
  await expect(editor).toContainText("Brouillon original vérifié"); await expect(history.locator("article")).toHaveCount(4); expect(posts).toBe(4);
  expect(edited.request.action).toBe("edit"); expect(edited.revision.previous_id).toBe(head.revision.id);
  expect(edited.revision.state).toBe("DRAFT"); expect(edited.revision.reviewed_digest).toBeNull(); expect(edited.revision.approved_digest).toBeNull();
  expect(edited.revision.content.template_original_id).toBeNull(); expect(edited.revision.content.origin).toBe("human");
  await expect(actions.getByRole("button", { name: "Approuver le contenu et l’audience", exact: true })).toBeDisabled();
  await expect(actions.getByRole("button", { name: "Soumettre en revue", exact: true })).toBeEnabled();
  const oldApproval = await request.get(`${base}/campaigns/${head.revision.id}`, { headers }); expect(await oldApproval.json()).toEqual(head);
  expect(await page.evaluate(() => Object.keys(sessionStorage).some(k => k.startsWith("flowpilot.marketing-campaign-edit-request:")))).toBe(false);
  await history.screenshot({ path: info.outputPath("native-campaign-edit-reset.png") });
  let latest = edited;
  for (let index = 0; index < 20; index++) {
    const response = await request.post(base + "/campaigns", { headers, data: { action: "edit", campaign_id: latest.revision.campaign_id,
      expected_revision_id: latest.revision.id, content: { channel: "email", origin: "human", subject, body: `Expanded edit ${index}`, audience_id: capture.id,
        template_original_id: null }, reason: `Explicit expanded revision ${index}`, idempotency_key: `expanded-edit-${prefix}-${index}` } });
    expect(response.status(), await response.text()).toBe(200); latest = await response.json();
  }
  await history.getByRole("button", { name: "Actualiser l’historique", exact: true }).click(); await expect(history.locator("article")).toHaveCount(20);
  await history.getByRole("button", { name: "Révisions suivantes", exact: true }).click(); await expect(history.locator("article")).toHaveCount(4);
  await expect(history).toContainText("21–24 sur 24 révisions");
  await page.route("**/campaigns/*/audit?**", async route => {
    const response = await route.fetch(); const data = await response.json(); data.total++;
    await route.fulfill({ response, json: data });
  });
  await history.getByRole("button", { name: "Actualiser l’historique", exact: true }).click();
  await expect(history).toContainText("Historique à vérifier"); await expect(history.locator("article")).toHaveCount(0);
  await expect(editor.getByRole("button", { name: "Préparer une correction de campagne", exact: true })).toBeDisabled();
  await page.unroute("**/campaigns/*/audit?**");
  await history.getByRole("button", { name: "Actualiser l’historique", exact: true }).click(); await expect(history.locator("article")).toHaveCount(4);
  await history.getByRole("button", { name: "Révisions précédentes", exact: true }).click(); await expect(history.locator("article")).toHaveCount(20);
  await history.getByRole("button", { name: "Révisions suivantes", exact: true }).click(); await expect(history.locator("article")).toHaveCount(4);
  await history.screenshot({ path: info.outputPath("native-campaign-audit-page.png") });
  const catalogBefore = await request.get(base + "/campaigns?limit=1", { headers }); const existing = await catalogBefore.json();
  const catalogTotal = Math.max(existing.total, 24);
  for (let index = existing.total; index < catalogTotal; index++) {
    const response = await request.post(base + "/campaigns", { headers, data: { action: "create", campaign_id: null, expected_revision_id: null,
      content: { channel: "email", origin: "human", subject: `Catalog ${prefix} ${index}`, body: "Explicit catalog draft", audience_id: capture.id,
        template_original_id: null }, reason: "Explicit catalog fixture", idempotency_key: `catalog-campaign-${prefix}-${index}` } }); expect(response.status()).toBe(200);
  }
  const marketing = page.getByRole("region", { name: "Marketing", exact: true });
  await marketing.getByRole("button", { name: "Actualiser les campagnes", exact: true }).click(); await expect(marketing).toContainText(`1–20 sur ${catalogTotal} campagnes`);
  await marketing.getByRole("button", { name: "Campagnes suivantes", exact: true }).click(); await expect(marketing).toContainText(`21–${catalogTotal} sur ${catalogTotal} campagnes`);
  await page.route("**/campaigns?**", async route => { const response = await route.fetch(); const data = await response.json(); data.total++; await route.fulfill({ response, json: data }); });
  await marketing.getByRole("button", { name: "Actualiser les campagnes", exact: true }).click(); await expect(marketing).toContainText("Catalogue à vérifier");
  await expect(marketing.getByRole("button", { name: "Campagnes suivantes", exact: true })).toHaveCount(0);
  await page.unroute("**/campaigns?**"); await marketing.getByRole("button", { name: "Actualiser les campagnes", exact: true }).click();
  await expect(marketing).toContainText(`21–${catalogTotal} sur ${catalogTotal} campagnes`);
  await marketing.getByRole("button", { name: "Campagnes précédentes", exact: true }).click(); await expect(marketing).toContainText(`1–20 sur ${catalogTotal} campagnes`);
});
