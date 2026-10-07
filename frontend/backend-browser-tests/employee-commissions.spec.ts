import { expect, test } from "@playwright/test";
test.use({ timezoneId: "America/Los_Angeles" });
test("native recorded commission profile preserves currencies, source originals and cancellation history", async ({ page, request }, info) => {
  test.setTimeout(90000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve", workforce = `${base}/workforce/institutes/${institute}`;
  const setting = `${base}/gift-cards/institutes/${institute}/settings`;
  let settingReply = await request.get(setting, { headers });
  if (settingReply.status() === 400) { expect((await request.put(setting, { headers, data: { currency: "CHF" } })).status()).toBe(200); settingReply = await request.get(setting, { headers }); }
  expect(settingReply.status()).toBe(200); const originalSetting = await settingReply.json();
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Zurich" }).format(new Date()), originals: any[] = [];
  for (const currency of ["CHF", "EUR"]) {
    expect((await request.put(setting, { headers, data: { currency } })).status()).toBe(200);
    const created = await request.post(`${base}/tickets`, { headers, data: { institute_id: institute, service_id: "svc-aisselles" } });
    expect(created.status()).toBe(200); const ticket = await created.json();
    const started = await request.post(`${base}/planning/sessions/start`, { headers, data: { ticket_id: ticket.id, employee_id: "emp-angela", service_id: "svc-aisselles" } });
    expect(started.status(), await started.text()).toBe(200); const session = await started.json();
    expect((await request.patch(`${base}/planning/sessions/${session.id}/finish`, { headers })).status()).toBe(200);
    expect((await request.patch(`${base}/tickets/${ticket.id}/checkout/start`, { headers, data: { employee_id: "emp-assya" } })).status()).toBe(200);
    const paid = await request.patch(`${base}/tickets/${ticket.id}/checkout/pay`, { headers, data: { employee_id: "emp-assya", payment_method: "especes" } });
    expect(paid.status(), await paid.text()).toBe(200); const receipt = await paid.json(); expect(receipt.currency).toBe(currency);
    const configured = await request.post(`${workforce}/commission-rules`, { headers, data: { employee_id: "emp-angela", title: `Explicit ${currency} ${info.project.name}`, basis: "closed_attributed_line_gross",
      currency, category: "care", service_id: null, rate_basis_points: 1025, rounding: "half_even", first_day: day, last_day: day, reason: "Owned explicit profile rule", idempotency_key: `profile-rule-${currency}-${info.project.name}` } });
    expect(configured.status(), await configured.text()).toBe(200); const rule = await configured.json();
    const credited = await request.post(`${workforce}/commissions`, { headers, data: { rule_id: rule.id, line_id: receipt.lines[0].id, reason: "Owned explicit profile credit", idempotency_key: `profile-credit-${currency}-${info.project.name}` } });
    expect(credited.status(), await credited.text()).toBe(200); const original = await credited.json(); expect(original.employee_id).toBe("emp-angela");
    originals.push(original);
  }
  expect((await request.put(setting, { headers, data: { currency: originalSetting.currency } })).status()).toBe(200);
  const cancelled = await request.post(`${workforce}/commissions/${originals[0].id}/cancel`, { headers, data: { reason: "Explicit profile correction", idempotency_key: `profile-cancel-${info.project.name}` } });
  expect(cancelled.status(), await cancelled.text()).toBe(200); const cancellation = await cancelled.json();
  await expect(page.getByRole("combobox", { name: /Choisir.*institut/ })).toHaveValue(institute);
  await page.getByRole("button", { name: "Équipe", exact: true }).click();
  await expect(page.getByRole("button", { name: "Actualiser les compétences", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Calendrier individuel", exact: true }).click();
  const profile = page.getByRole("region", { name: "Profil et calendrier individuel", exact: true });
  await profile.getByRole("combobox", { name: "Collaboratrice du calendrier", exact: true }).selectOption("emp-angela");
  const panel = profile.getByRole("region", { name: "Commissions enregistrées", exact: true });
  for (const original of originals) await expect(panel).toContainText(original.id);
  await expect(panel).toContainText("total à payer restent inconnus"); await expect(panel.getByRole("region", { name: "Montants enregistrés en CHF" })).toBeVisible();
  await expect(panel.getByRole("region", { name: "Montants enregistrés en EUR" })).toBeVisible();
  await profile.getByRole("button", { name: "Consulter les commissions", exact: true }).click(); await expect(panel.getByRole("heading", { name: "Commissions enregistrées", exact: true })).toBeInViewport();
  const card = panel.locator("li").filter({ hasText: originals[0].id }); await card.locator("summary").click();
  await expect(card).toContainText(cancellation.id); await expect(card).toContainText(originals[0].calculation.source.captured_at);
  await expect(card).toContainText("Collaboratrice attribuée : emp-angela"); await expect(card).toContainText("quantité : 1, déjà incluse");
  const path = "**/workforce/institutes/*/employees/*/commission-day?**";
  const corrupt = async (route: any) => { const actual = await route.fetch(), value = await actual.json(); value.currencies[0].amounts_minor.recorded = String(BigInt(value.currencies[0].amounts_minor.recorded)+1n); await route.fulfill({ response: actual, json: value }); };
  await page.route(path, corrupt); await panel.getByRole("button", { name: "Actualiser les commissions", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("à vérifier"); await expect(panel.locator("li")).toHaveCount(0);
  await page.unroute(path, corrupt); await panel.getByRole("button", { name: "Actualiser les commissions", exact: true }).click();
  await expect(panel).toContainText(originals[0].id); await panel.locator("li").filter({ hasText: originals[0].id }).locator("summary").click();
  for (const control of await panel.locator("button,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth+1)).toBe(false);
  await panel.screenshot({ path: info.outputPath("native-employee-commissions.png") });
  await profile.getByRole("combobox", { name: "Collaboratrice du calendrier", exact: true }).selectOption("emp-assya");
  await expect(panel).toContainText("Aucune commission enregistrée ce jour"); for (const original of originals) await expect(panel).not.toContainText(original.id);
  // Owned fixture records are removed by the isolated launcher; no physical payment settlement is asserted.
});
