import { expect, test } from "@playwright/test";
test.use({ timezoneId: "America/Los_Angeles" });
test("native recorded rebooking keeps signed source provenance, failed-read isolation and cancelled booking diagnostics", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  const workforce = `${base}/workforce/institutes/${institute}`;
  const customerReply = await request.post(`${base}/customers/institutes/${institute}`, { headers, data: { display_name: `Owned rebooking ${info.project.name}`, idempotency_key: `rebooking-customer-${info.project.name}` } });
  expect(customerReply.status(), await customerReply.text()).toBe(200); const customer = await customerReply.json();
  const ticketReply = await request.post(`${base}/tickets`, { headers, data: { institute_id: institute, service_id: "svc-aisselles", customer_id: customer.id } });
  expect(ticketReply.status()).toBe(200); const ticket = await ticketReply.json();
  const started = await request.post(`${base}/planning/sessions/start`, { headers, data: { ticket_id: ticket.id, employee_id: "emp-angela", service_id: "svc-aisselles" } });
  expect(started.status(), await started.text()).toBe(200); const session = await started.json();
  const finished = await request.patch(`${base}/planning/sessions/${session.id}/finish`, { headers });
  expect(finished.status()).toBe(200); const completed = await finished.json();
  const future = new Date(Date.now()+7*86400000); future.setUTCHours(10, 0, 0, 0);
  const bookingReply = await request.post(`${base}/appointments`, { headers, data: { institute_id: institute, employee_id: "emp-angela", service_id: "svc-aisselles",
    customer_id: customer.id, customer_name: customer.display_name, start_time: future.toISOString(), idempotency_key: `rebooking-target-${info.project.name}` } });
  expect(bookingReply.status(), await bookingReply.text()).toBe(200); const booking = await bookingReply.json();
  let original: any;
  let bookingCancelled = false;
  try {
    const reply = await request.post(`${workforce}/rebookings`, { headers, data: { source_kind: "session", source_id: session.id,
      target_appointment_id: booking.id, reason: `Explicit rebooking ${info.project.name}`, idempotency_key: `native-rebooking-${info.project.name}` } });
    expect(reply.status(), await reply.text()).toBe(200); original = await reply.json();
    await page.getByRole("button", { name: "Équipe", exact: true }).click(); await page.getByRole("button", { name: "Calendrier individuel", exact: true }).click();
    const profile = page.getByRole("region", { name: "Profil et calendrier individuel" });
    await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-angela");
    const panel = profile.getByRole("region", { name: "Rebooking déclaré" });
    await expect(panel).toContainText("Retours réservés : 1"); await expect(panel).toContainText("taux de conversion restent inconnus");
    await profile.getByRole("button", { name: "Consulter le rebooking", exact: true }).click(); await expect(panel.getByRole("heading")).toBeInViewport();
    const card = panel.locator("li").filter({ hasText: original.id }); await card.locator("summary").click();
    await expect(card).toContainText(session.id); await expect(card).toContainText(completed.real_end_time);
    await expect(card).toContainText(original.booking_capture.creation_event_id); await expect(card).toContainText("Identique au lien déclaré");
    const path = "**/workforce/institutes/*/employees/*/rebooking-day?**";
    const corrupt = async (route: any) => { const actual = await route.fetch(), value = await actual.json(); value.conversion_basis_points = "10000"; await route.fulfill({ response: actual, json: value }); };
    await page.route(path, corrupt); await panel.getByRole("button", { name: "Actualiser le rebooking" }).click();
    await expect(panel.getByRole("alert")).toContainText("à vérifier"); await expect(panel.locator("li")).toHaveCount(0);
    await page.unroute(path, corrupt); await panel.getByRole("button", { name: "Actualiser le rebooking" }).click(); await expect(panel).toContainText(original.id);
    expect((await request.patch(`${base}/appointments/${booking.id}/cancel`, { headers })).status()).toBe(200);
    bookingCancelled = true;
    await panel.getByRole("button", { name: "Actualiser le rebooking" }).click(); await expect(panel).toContainText("Réservations annulées : 1");
    await panel.locator("li").filter({ hasText: original.id }).locator("summary").click();
    await expect(panel).toContainText(original.source_capture.actual_end);
    for (const control of await panel.locator("button,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth+1)).toBe(false);
    await panel.screenshot({ path: info.outputPath("native-rebooking.png") });
    await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-assya");
    await expect(panel).toContainText("Aucune déclaration enregistrée ce jour"); await expect(panel).not.toContainText(original.id);
  } finally {
    if (original) expect((await request.post(`${workforce}/rebookings/${original.id}/cancel`, { headers, data: { reason: "Owned fixture closure", idempotency_key: `native-rebooking-cancel-${info.project.name}` } })).status()).toBe(200);
    if (!bookingCancelled) expect((await request.patch(`${base}/appointments/${booking.id}/cancel`, { headers })).status()).toBe(200);
  }
});
