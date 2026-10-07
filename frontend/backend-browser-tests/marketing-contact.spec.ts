import { expect, test } from "@playwright/test";
test.use({ actionTimeout: 15000 });

test("signed native contact declaration verifies canonical email, recovers lost reply and retains withdrawal history", async ({ page, request }, info) => {
  test.setTimeout(120000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token")), headers = { Authorization: `Bearer ${token}` };
  const api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve", name = `Contacts ${info.project.name}`;
  const response = await request.post(`${api}/customers/institutes/${institute}`, { headers, data: { display_name: name, idempotency_key: `contacts-client-${info.project.name}` } });
  expect(response.status()).toBe(200); const customer = await response.json();
  async function select() {
    await page.getByRole("button", { name: "Clientes", exact: true }).click();
    const directory = page.getByRole("region", { name: "Clientes et CRM", exact: true });
    await directory.getByLabel("Nom ou téléphone").fill(name); await directory.getByRole("button", { name: "Rechercher", exact: true }).click();
    await directory.getByRole("button", { name, exact: true }).click();
  }
  await select(); const editor = page.getByRole("region", { name: "Contacts marketing", exact: true });
  await editor.getByRole("button", { name: "Préparer les contacts marketing", exact: true }).click();
  for (const channel of ["Email", "SMS", "Push"]) {
    await editor.getByRole("combobox", { name: `Permission marketing ${channel}`, exact: true }).selectOption("granted");
    await editor.getByLabel(`Preuve de permission ${channel}`, { exact: true }).fill(`Explicit ${channel} marketing permission`);
    await editor.getByLabel(`Déclarer une destination ${channel}`, { exact: true }).check();
    await editor.getByLabel(`Destination ${channel}`, { exact: true }).fill(channel === "Email" ? "customer@EXAMPLE.COM" : channel === "SMS" ? "+41791234567" : `device-${info.project.name}`);
    await editor.getByLabel(`Preuve de destination ${channel}`, { exact: true }).fill(`Explicit ${channel} destination`);
  }
  await editor.getByLabel("Application Push", { exact: true }).fill("fixture-app");
  await editor.getByLabel("Motif des contacts", { exact: true }).fill("Explicit native three-channel contacts");
  for (const control of await editor.locator("button,input,select").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await editor.screenshot({ path: info.outputPath("native-contact-form.png") });
  let posts = 0, previews = 0, first: any;
  let markLost!: () => void; const lost = new Promise<void>(resolve => { markLost = resolve; });
  await page.route("**/contact-declarations/validate", async route => { previews++; await route.continue(); });
  await page.route("**/contact-declarations", async route => {
    if (route.request().method() !== "POST") return route.continue(); posts++;
    const result = await route.fetch(); expect(result.status()).toBe(200); const value = await result.json();
    if (posts === 1) { first = value; await route.abort("failed"); markLost(); return; }
    await route.fulfill({ response: result });
  });
  await editor.getByRole("button", { name: "Vérifier la déclaration de contacts", exact: true }).click();
  await expect(editor).toContainText("Déclaration vérifiée"); await expect(editor).toContainText("customer@example.com");
  expect(posts).toBe(0); expect(previews).toBe(1);
  const base = `${api}/marketing/institutes/${institute}/customers/${customer.id}/contact-declarations`;
  expect(await (await request.get(base + "/current", { headers })).json()).toBeNull();
  await editor.screenshot({ path: info.outputPath("native-contact-confirm.png") });
  await editor.getByRole("button", { name: "Conserver la déclaration vérifiée", exact: true }).click(); await lost;
  await expect(editor.getByRole("button", { name: "Reprendre les contacts conservés", exact: true })).toBeEnabled();
  await page.reload(); await select(); await editor.getByRole("button", { name: "Reprendre les contacts conservés", exact: true }).click();
  await expect(editor).toContainText("Contacts originaux vérifiés"); expect(posts).toBe(1); expect(previews).toBe(1);
  expect(first.declaration.communications.map((c: any) => c.channel)).toEqual(["email", "sms", "push"]);
  expect(first.declaration.communications[0].destination.email).toBe("customer@example.com");
  expect(first.declaration.communications[2].destination.push_token).toBe(`device-${info.project.name}`);
  expect(await page.evaluate(() => Object.keys(sessionStorage).some(k => k.startsWith("flowpilot.marketing-contact-request:")))).toBe(false);
  // Only customer/segment-policy setup uses the API; every marketing action below uses native controls.
  const marketing = `${api}/marketing/institutes/${institute}`, policies = `${api}/crm/institutes/${institute}/segment-policies`;
  const prior = await (await request.get(policies + "/current", { headers })).json();
  const policy = await request.post(policies, { headers, data: { policy: { institute_id: institute, observation_us: 1209600000000,
    new_customer_us: 86400000000, at_risk_us: 172800000000, dormant_us: 604800000000, loyal_min_tickets: 2, vip_min_tickets: 3,
    vip_currency: "CHF", vip_gross_minor: "300" }, previous_policy_id: prior?.id || null, reason: "Explicit native chain segments",
    idempotency_key: `contact-chain-policy-${info.project.name}` } });
  expect(policy.status(), await policy.text()).toBe(200);
  let capture: any, approval: any, campaignPosts = 0, capturePosts = 0;
  await page.route("**/audience-captures", async route => {
    if (route.request().method() !== "POST") return route.continue(); capturePosts++;
    const response = await route.fetch(); expect(response.status()).toBe(200); capture = await response.json(); await route.fulfill({ response });
  });
  await page.route("**/campaigns", async route => {
    if (route.request().method() !== "POST") return route.continue(); campaignPosts++;
    const response = await route.fetch(); expect(response.status()).toBe(200); approval = await response.json(); await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Marketing", exact: true }).click();
  const audiencePanel = page.getByRole("region", { name: "Capturer une audience", exact: true }), captureReason = `Native complete push ${info.project.name}`;
  await audiencePanel.getByLabel("Nouvelles", { exact: true }).check();
  await audiencePanel.getByLabel("Canal de l’audience").selectOption("push");
  await audiencePanel.getByLabel("Source des permissions").selectOption("marketing_contact");
  await audiencePanel.getByLabel("Motif de capture").fill(captureReason);
  await audiencePanel.getByRole("button", { name: "Conserver l’audience", exact: true }).click();
  await expect(audiencePanel).toContainText("Capture originale vérifiée"); expect(capturePosts).toBe(1);
  expect(capture.request.permission_basis).toBe("marketing_contact"); expect(capture.summary.eligible_count).toBeGreaterThan(0);
  const retained = await (await request.get(`${marketing}/audience-captures/${capture.id}/pages/0`, { headers })).json();
  expect(retained.observation.items.find((i: any) => i.customer_id === customer.id).declaration).toEqual(first);
  const creator = page.getByRole("region", { name: "Créer une campagne", exact: true }), body = `Native contacts push ${info.project.name}`;
  await creator.getByRole("button", { name: "Préparer une campagne", exact: true }).click();
  await creator.getByLabel("Canal de campagne").selectOption("push");
  await creator.getByRole("button", { name: "Choisir une audience source", exact: true }).click();
  await creator.getByRole("button", { name: new RegExp(captureReason) }).click();
  await creator.getByLabel("Source du texte").selectOption("literal"); await creator.getByLabel("Origine de campagne").selectOption("ai");
  await creator.getByLabel("Texte de campagne").fill(body); await creator.getByLabel("Motif du brouillon").fill("Explicit native AI draft");
  await creator.getByRole("button", { name: "Enregistrer le brouillon", exact: true }).click();
  await expect(creator).toContainText("Brouillon original vérifié"); expect(campaignPosts).toBe(1);
  await page.getByRole("button", { name: `${body} · Brouillon · push`, exact: true }).click();
  const history = page.getByRole("region", { name: "Historique de campagne", exact: true }), actions = history.getByRole("region", { name: "Validation de campagne", exact: true });
  await actions.getByLabel("Motif de validation").fill("Explicit native review");
  await actions.getByRole("button", { name: "Soumettre en revue", exact: true }).click();
  await expect(actions.getByRole("button", { name: "Approuver le contenu et l’audience", exact: true })).toBeEnabled();
  await actions.getByLabel("Motif de validation").fill("Explicit native approval");
  await actions.getByRole("button", { name: "Approuver le contenu et l’audience", exact: true }).click();
  await expect(history).toContainText("Approuvée"); expect(campaignPosts).toBe(3);
  expect(approval.revision.state).toBe("APPROVE"); expect(approval.revision.content.origin).toBe("ai");
  expect(approval.revision.content.audience.customer_ids).toContain(customer.id);
  expect(approval.revision.approved_digest).toBe(approval.revision.reviewed_digest);
  const recipients = history.getByRole("region", { name: "Destinataires courants", exact: true });
  await recipients.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  const member = recipients.locator("article").filter({ hasText: customer.id });
  await expect(member).toContainText("Accord et destination déclarés");
  await recipients.screenshot({ path: info.outputPath("native-contact-chain-approved.png") });
  await select();
  await editor.getByRole("button", { name: "Préparer les contacts marketing", exact: true }).click();
  await expect(editor.getByLabel("Destination Email", { exact: true })).toHaveValue("customer@example.com");
  await expect(editor.getByLabel("Destination Push", { exact: true })).toHaveValue(`device-${info.project.name}`);
  await editor.getByRole("combobox", { name: "Permission marketing Push", exact: true }).selectOption("refused");
  await editor.getByLabel("Preuve de permission Push", { exact: true }).fill("Explicit customer push withdrawal");
  await editor.getByLabel("Motif des contacts", { exact: true }).fill("Explicit native push withdrawal");
  await editor.getByRole("button", { name: "Vérifier la déclaration de contacts", exact: true }).click();
  await expect(editor).toContainText("Push : Refus déclaré"); expect(posts).toBe(1); expect(previews).toBe(2);
  await editor.getByRole("button", { name: "Conserver la déclaration vérifiée", exact: true }).click();
  await expect(editor).toContainText("Contacts originaux vérifiés"); expect(posts).toBe(2);
  const current = await (await request.get(base + "/current", { headers })).json();
  expect(current.previous_id).toBe(first.id); expect(current.declaration.communications[2].permission).toBe("refused");
  expect(current.declaration.communications[0]).toEqual(first.declaration.communications[0]);
  expect(await (await request.get(base + "/" + first.id, { headers })).json()).toEqual(first);
  await editor.screenshot({ path: info.outputPath("native-contact-withdrawal.png") });
  await page.getByRole("button", { name: "Marketing", exact: true }).click();
  await page.getByRole("button", { name: `${body} · Approuvée · push`, exact: true }).click();
  await recipients.getByRole("button", { name: "Vérifier les destinataires courants", exact: true }).click();
  await expect(member).toContainText("Refus déclaré"); await expect(member).toContainText("Non éligible");
  expect(await (await request.get(`${marketing}/campaigns/${approval.revision.campaign_id}/current`, { headers })).json()).toEqual(approval);
  expect(await (await request.get(`${marketing}/audience-captures/${capture.id}/pages/0`, { headers })).json()).toEqual(retained);
  expect(campaignPosts).toBe(3); expect(capturePosts).toBe(1);
  await recipients.screenshot({ path: info.outputPath("native-contact-chain-withdrawn.png") });
});
