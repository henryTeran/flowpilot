import { expect, test } from "@playwright/test";
test.use({ timezoneId: "America/Los_Angeles" });
test("signed native customer search reads current CRM and refuses a forged classification", async ({ page, request }, info) => {
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  const name = `CRM ${info.project.name}`;
  const created = await request.post(`${base}/customers/institutes/${institute}`, { headers,
    data: { display_name: name, idempotency_key: `crm-${info.project.name}` } });
  expect(created.status(), await created.text()).toBe(200); const customer = await created.json();
  const path = `${base}/crm/institutes/${institute}/segment-policies`;
  const before = await request.get(path+"/current", { headers }); expect(before.status()).toBe(200);
  const previous = await before.json();
  const configured = await request.post(path, { headers, data: { previous_policy_id: previous?.id || null,
    reason: "Owned browser profile fixture", idempotency_key: `crm-policy-${info.project.name}`,
    policy: { institute_id: institute, observation_us: 86400000000, new_customer_us: 86400000000,
      at_risk_us: 7200000000, dormant_us: 14400000000, loyal_min_tickets: 2, vip_min_tickets: 3,
      vip_currency: "CHF", vip_gross_minor: "300" } } });
  expect(configured.status(), await configured.text()).toBe(200);
  const careTickets: string[] = [];
  for (let i=0; i<2; i++) {
    const ticketReply = await request.post(`${base}/tickets`, { headers, data: { institute_id: institute, service_id: "svc-aisselles", customer_id: customer.id } });
    expect(ticketReply.status(), await ticketReply.text()).toBe(200); const ticket = await ticketReply.json(); careTickets.push(ticket.id);
    const started = await request.post(`${base}/planning/sessions/start`, { headers, data: { ticket_id: ticket.id, employee_id: "emp-angela", service_id: "svc-aisselles" } });
    expect(started.status(), await started.text()).toBe(200); const session = await started.json();
    const finished = await request.patch(`${base}/planning/sessions/${session.id}/finish`, { headers });
    expect(finished.status(), await finished.text()).toBe(200);
  }
  await expect(page.getByRole("combobox", { name: /Choisir.*institut/ })).toHaveValue(institute);
  await page.getByRole("button", { name: "Clientes", exact: true }).click();
  const directory = page.getByRole("region", { name: "Clientes et CRM", exact: true });
  await directory.getByLabel("Nom ou téléphone").fill(name);
  await directory.getByRole("button", { name: "Rechercher", exact: true }).click();
  await directory.getByRole("button", { name, exact: true }).click();
  const panel = directory.getByRole("region", { name: "Profil CRM", exact: true });
  const cycle = panel.getByRole("region", { name: "Cycle de retour observé", exact: true });
  await expect(cycle).toContainText("Épisodes de soins enregistrés : 2");
  await expect(cycle).toContainText("Intervalles connus : 1");
  for (const id of careTickets) await expect(cycle).toContainText(id);
  await expect(cycle).toContainText("jours (arrondi)");
  const returnPath = `**/crm/institutes/${institute}/customers/${customer.id}/return-cycle?*`;
  const corruptCycle = async (route: any) => { const actual = await route.fetch(), value = await actual.json(); value.summary.average_return_gap_us.numerator = "999999999999999999999"; await route.fulfill({ response: actual, json: value }); };
  await page.route(returnPath, corruptCycle); await cycle.getByRole("button", { name: "Actualiser le cycle", exact: true }).click();
  await expect(cycle.getByRole("alert")).toContainText("à vérifier"); await expect(cycle).not.toContainText("Épisodes de soins enregistrés");
  await page.unroute(returnPath, corruptCycle); await cycle.getByRole("button", { name: "Actualiser le cycle", exact: true }).click();
  await expect(cycle).toContainText("Épisodes de soins enregistrés : 2");
  await expect(panel).toContainText("Nouvelle cliente"); await expect(panel).toContainText("Tickets payés sur la période : 0");
  const profilePath = `**/crm/institutes/${institute}/customers/${customer.id}/segment`;
  const corrupt = async (route: any) => { const actual = await route.fetch(), value = await actual.json(); value.segment.state = "VIP"; await route.fulfill({ response: actual, json: value }); };
  await page.route(profilePath, corrupt); await panel.getByRole("button", { name: "Actualiser le profil", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("à vérifier"); await expect(panel).not.toContainText("Nouvelle cliente");
  await page.unroute(profilePath, corrupt); await panel.getByRole("button", { name: "Actualiser le profil", exact: true }).click();
  await expect(panel).toContainText("Nouvelle cliente");
  for (const control of await directory.locator("button,input,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth+1)).toBe(false);
  await directory.screenshot({ path: info.outputPath("native-customer-crm.png") });
});
