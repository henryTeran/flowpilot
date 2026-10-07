import { expect, test } from "@playwright/test";
test.use({ timezoneId: "America/Los_Angeles" });

test("native employee profile reads original line attribution and separate closed invoice currencies", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  const setting = `${base}/gift-cards/institutes/${institute}/settings`;
  let settingReply = await request.get(setting, { headers });
  if (settingReply.status() === 400) {
    expect(await settingReply.text()).toContain("Configurer la devise des cartes cadeaux");
    expect((await request.put(setting, { headers, data: { currency: "CHF" } })).status()).toBe(200);
    settingReply = await request.get(setting, { headers });
  }
  expect(settingReply.status()).toBe(200); const originalSetting = await settingReply.json();
  const receipts: any[] = [];
  try {
    // Signed owned-fixture workflow supplies recorded performer/closed facts;
    // this test verifies native reading, not physical cash settlement.
    for (const currency of ["CHF", "EUR"]) {
      expect((await request.put(setting, { headers, data: { currency } })).status()).toBe(200);
      const created = await request.post(`${base}/tickets`, { headers, data: { institute_id: institute, service_id: "svc-aisselles" } });
      expect(created.status()).toBe(200); const ticket = await created.json();
      const started = await request.post(`${base}/planning/sessions/start`, { headers, data: { ticket_id: ticket.id, employee_id: "emp-angela", service_id: "svc-aisselles" } });
      expect(started.status(), await started.text()).toBe(200); const session = await started.json();
      expect((await request.patch(`${base}/planning/sessions/${session.id}/finish`, { headers })).status()).toBe(200);
      expect((await request.patch(`${base}/tickets/${ticket.id}/checkout/start`, { headers, data: { employee_id: "emp-assya" } })).status()).toBe(200);
      const paid = await request.patch(`${base}/tickets/${ticket.id}/checkout/pay`, { headers, data: { employee_id: "emp-assya", payment_method: "especes" } });
      expect(paid.status(), await paid.text()).toBe(200); const receipt = await paid.json(); expect(receipt.currency).toBe(currency); receipts.push(receipt);
    }
    await page.getByRole("button", { name: "Équipe", exact: true }).click();
    await page.getByRole("button", { name: "Calendrier individuel", exact: true }).click();
    const profile = page.getByRole("region", { name: "Profil et calendrier individuel" });
    await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-angela");
    const panel = profile.getByRole("region", { name: "CA brut facturé attribué" });
    await expect(panel).toContainText("CHF"); await expect(panel).toContainText("EUR");
    for (const receipt of receipts) await expect(panel).toContainText(receipt.ticket_number);
    await expect(panel).toContainText("exécutante enregistrée sur la ligne");
    const offset = new Intl.DateTimeFormat("en", { timeZone: "Europe/Zurich", timeZoneName: "longOffset" }).formatToParts(new Date(receipts[0].paid_at)).find(part => part.type === "timeZoneName")!.value.replace("GMT", "UTC");
    await expect(panel).toContainText(offset);
    await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-assya");
    await expect(panel).toContainText("Aucune ligne attribuée clôturée ce jour");
    for (const receipt of receipts) await expect(panel).not.toContainText(receipt.ticket_number);
    await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-angela");
    await expect(panel).toContainText(receipts[0].ticket_number);
    const path = "**/workforce/institutes/*/employees/*/revenue?**";
    const corrupt = async (route: any) => { const actual = await route.fetch(), value = await actual.json(); value.employee_id = "foreign"; await route.fulfill({ response: actual, json: value }); };
    await page.route(path, corrupt); await panel.getByRole("button", { name: "Actualiser le CA attribué" }).click();
    await expect(panel.getByRole("alert")).toContainText("à vérifier"); await expect(panel.locator("li")).toHaveCount(0);
    await page.unroute(path, corrupt); await panel.getByRole("button", { name: "Actualiser le CA attribué" }).click();
    await expect(panel).toContainText(receipts[0].ticket_number);
    await profile.getByRole("button", { name: "Consulter le CA attribué" }).click();
    await expect(panel.getByRole("heading", { name: "CA brut facturé attribué" })).toBeInViewport();
    await panel.locator("summary").first().click();
    await expect(panel.locator("details[open]")).toContainText("catégorie enregistrée");
    for (const summary of await panel.locator("summary").all()) expect((await summary.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    for (const control of await panel.locator("button").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth+1)).toBe(false);
    await page.screenshot({ path: info.outputPath("native-employee-revenue.png"), fullPage: true });
    await panel.screenshot({ path: info.outputPath("native-revenue-detail.png") });
  } finally {
    expect((await request.put(setting, { headers, data: { currency: originalSetting.currency } })).status()).toBe(200);
  }
});
