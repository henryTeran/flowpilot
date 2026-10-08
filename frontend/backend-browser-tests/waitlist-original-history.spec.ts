import { expect as baseExpect, test } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(180000);
test("native retained waitlist history verifies original proof and real paging without activating requests", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  const registered = await request.post(`${api}/customers/institutes/${institute}`, { headers,
    data: { display_name: `Liste ${info.project.name}`, idempotency_key: `history-customer-${info.project.name}` } });
  expect(registered.status()).toBe(200); const customer = await registered.json();
  const catalog = await (await request.get(`${api}/services/catalog`, { headers })).json();
  const service = catalog.find((s: any) => s.status === "active" && Number.isInteger(s.duration_min) && s.duration_min > 0 && s.duration_min <= 1440);
  expect(service).toBeTruthy();
  let original: any;
  for (let n = 0; n < 25; n++) {
    const response = await request.post(`${api}/waitlist/institutes/${institute}/originals`, { headers, data: {
      customer_id: customer.id, service_id: service.id, duration_minutes: service.duration_min,
      availability: [{ start: "2030-01-02T09:00:00Z", end: "2030-01-02T11:00:00Z" }], allowed_employee_ids: [],
      constraints_review: n === 24 ? "unknown" : "confirmed", availability_evidence: "Déclaration cliente 🧪",
      constraints_evidence: n === 24 ? null : "Contraintes relues avec cliente", reason: `Demande ${info.project.name} ${n}`,
      idempotency_key: `history-demand-${info.project.name}-${n}` } });
    expect(response.status(), await response.text()).toBe(200); original = await response.json();
  }
  let reads = 0, corrupt = false;
  await page.route("**/waitlist/institutes/**/originals?**", async route => {
    reads++; expect(route.request().method()).toBe("GET"); const response = await route.fetch();
    const value = await response.json(); if (corrupt) value.basis = "active_waitlist";
    await route.fulfill({ response, json: value });
  });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  const panel = page.getByRole("region", { name: "Demandes de liste d’attente conservées", exact: true });
  const read = panel.getByRole("button", { name: "Lire les demandes conservées", exact: true });
  await expect(panel).toBeVisible(); expect(reads).toBe(0); await read.click();
  await expect(panel).toContainText(info.project.name === "desktop" ? "1–20 sur 25" : "1–20 sur 50");
  const reason = `Demande ${info.project.name} 24`;
  for (let n = 0; n < 5; n++) {
    await expect(read).toBeEnabled(); await expect(panel.getByRole("status")).toHaveCount(0);
    if (await panel.getByRole("heading", { name: reason, exact: true }).count()) break;
    await panel.getByRole("button", { name: "Demandes suivantes", exact: true }).click();
  }
  const card = panel.locator("article").filter({ has: page.getByRole("heading", { name: reason, exact: true }) });
  await expect(card).toContainText("Contraintes inconnues"); await card.locator("summary").click();
  await expect(card).toContainText(original.fingerprint); await expect(card).toContainText("no_booking_or_contact");
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  for (const control of await panel.locator("button,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false);
  await card.screenshot({ path: info.outputPath("native-waitlist-original.png") });
  corrupt = true; await read.click(); await expect(panel.getByRole("alert")).toBeVisible(); await expect(panel.locator("article")).toHaveCount(0);
  corrupt = false; await read.click(); await expect(panel.locator("article")).toHaveCount(20);
  const lifecycle = await (await request.get(`${api}/waitlist/institutes/${institute}/lifecycle`, { headers })).json();
  expect(lifecycle.active).toBe(0); expect(lifecycle.total).toBe(0);
});
