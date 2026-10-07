import { expect, test } from "@playwright/test";
test.use({ timezoneId: "America/Los_Angeles" });
test("signed native audience capture recovers lost POST and retains explicit marketing permissions", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  const created = await request.post(`${base}/customers/institutes/${institute}`, { headers, data: { display_name: `Audience ${info.project.name}`, idempotency_key: `audience-${info.project.name}` } });
  expect(created.status()).toBe(200); const customer = await created.json();
  if (info.project.name === "desktop") for (let index = 0; index < 54; index++) {
    const extra = await request.post(`${base}/customers/institutes/${institute}`, { headers, data: { display_name: `Audience cohort ${index}`, idempotency_key: `audience-cohort-${index}` } });
    expect(extra.status()).toBe(200);
  }
  const policies = `${base}/crm/institutes/${institute}/segment-policies`;
  const previousReply = await request.get(policies + "/current", { headers }); expect(previousReply.status()).toBe(200); const previous = await previousReply.json();
  const policy = await request.post(policies, { headers, data: { policy: { institute_id: institute, observation_us: 1209600000000,
    new_customer_us: 86400000000, at_risk_us: 172800000000, dormant_us: 604800000000, loyal_min_tickets: 2, vip_min_tickets: 3,
    vip_currency: "CHF", vip_gross_minor: "300" }, previous_policy_id: previous?.id || null, reason: "Explicit native marketing segments", idempotency_key: `marketing-policy-${info.project.name}` } });
  expect(policy.status(), await policy.text()).toBe(200);
  const communications = ["email", "sms"].flatMap(channel => ["service_follow_up", "marketing"].map(purpose => ({ channel, purpose,
    permission: channel === "email" && purpose === "marketing" ? "granted" : "unknown", evidence: channel === "email" && purpose === "marketing" ? "Explicit native marketing permission" : null })));
  const declaration = await request.post(`${base}/crm/institutes/${institute}/customers/${customer.id}/lifecycle-declarations`, { headers,
    data: { declaration: { institute_id: institute, customer_id: customer.id, birthday: null, birthday_evidence: null, communications }, previous_id: null,
      reason: "Explicit native audience permission", idempotency_key: `marketing-permission-${info.project.name}` } });
  expect(declaration.status(), await declaration.text()).toBe(200);
  async function open() { await page.getByRole("button", { name: "Marketing", exact: true }).click(); }
  await open(); const panel = page.getByRole("region", { name: "Capturer une audience", exact: true });
  await expect(panel.getByLabel("Nouvelles", { exact: true })).not.toBeChecked(); await expect(panel.getByLabel("Canal de l’audience")).toHaveValue("");
  await panel.getByLabel("Nouvelles", { exact: true }).check(); await panel.getByLabel("Canal de l’audience").selectOption("email");
  await panel.getByLabel("Motif de capture").fill("Explicit native retained audience");
  let posts = 0, first: any;
  await page.route("**/audience-captures", async route => {
    if (route.request().method() !== "POST") return route.continue();
    posts++; const response = await route.fetch(); expect(response.status()).toBe(200); first = await response.json();
    if (posts === 1) return route.abort("failed"); return route.fulfill({ response });
  });
  await panel.getByRole("button", { name: "Conserver l’audience", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Reprendre la capture conservée", exact: true })).toBeEnabled();
  await page.reload(); await open(); await panel.getByRole("button", { name: "Reprendre la capture conservée", exact: true }).click();
  await expect(panel).toContainText("Capture originale vérifiée"); expect(posts).toBe(1);
  expect(first.request.segments).toEqual(["NEW"]); expect(first.request.channel).toBe("email"); expect(first.actor_id).toBe("browser-manager");
  expect(await page.evaluate(() => Object.keys(sessionStorage).some(k => k.startsWith("flowpilot.marketing-audience-request:")))).toBe(false);
  const retained = await request.get(`${base}/marketing/institutes/${institute}/audience-captures/${first.id}`, { headers }); expect(await retained.json()).toEqual(first);
  let member: any; for (let i = 0; i < first.summary.page_count; i++) {
    const reply = await request.get(`${base}/marketing/institutes/${institute}/audience-captures/${first.id}/pages/${i}`, { headers }); expect(reply.status()).toBe(200);
    const data = await reply.json(); member ||= data.observation.items.find((item: any) => item.customer_id === customer.id);
  }
  expect(member.selected_segment).toBe(true); expect(member.marketing_permission).toBe("granted"); expect(member.eligible_by_recorded_permission).toBe(true); expect(member.delivery_authorized).toBe(false);
  await page.getByRole("button", { name: "Consulter les audiences retenues", exact: true }).click();
  const catalog = page.getByRole("region", { name: "Audiences retenues", exact: true });
  await catalog.getByRole("button", { name: /Explicit native retained audience/ }).first().click();
  const retainedPanel = page.getByRole("region", { name: "Détail de l’audience retenue", exact: true });
  await expect(retainedPanel.locator("article")).toHaveCount(50); await expect(retainedPanel).toContainText(first.id);
  await retainedPanel.getByRole("button", { name: "Clientes suivantes", exact: true }).click();
  await expect(retainedPanel.locator("article")).toHaveCount(first.summary.customer_count - 50); await expect(retainedPanel).toContainText("Page 2 sur 2");
  await page.route("**/audience-captures/*/pages/1", async route => {
    const response = await route.fetch(); const data = await response.json();
    data.observation.items[0].selected_segment = !data.observation.items[0].selected_segment;
    await route.fulfill({ response, json: data });
  });
  await retainedPanel.getByRole("button", { name: "Actualiser la page retenue", exact: true }).click();
  await expect(retainedPanel).toContainText("Page retenue à vérifier"); await expect(retainedPanel.locator("article")).toHaveCount(0);
  await page.unroute("**/audience-captures/*/pages/1");
  await retainedPanel.getByRole("button", { name: "Actualiser la page retenue", exact: true }).click();
  await expect(retainedPanel.locator("article")).toHaveCount(first.summary.customer_count - 50);
  await retainedPanel.getByRole("button", { name: "Clientes précédentes", exact: true }).click(); await expect(retainedPanel.locator("article")).toHaveCount(50);
  await retainedPanel.getByRole("button", { name: "Clientes suivantes", exact: true }).click(); await expect(retainedPanel.locator("article")).toHaveCount(first.summary.customer_count - 50);
  for (const control of await panel.locator("button,input,select").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await panel.screenshot({ path: info.outputPath("native-audience.png") });
  await retainedPanel.screenshot({ path: info.outputPath("native-retained-audience.png") });
});
