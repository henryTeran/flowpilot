import { expect, test } from "@playwright/test";
test.use({ timezoneId: "America/Los_Angeles" });
test("native declaration and cancellation recover committed lost replies without duplicate writes", async ({ page, request }, info) => {
  test.setTimeout(90000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  const workforce = `${base}/workforce/institutes/${institute}`;
  const customerReply = await request.post(`${base}/customers/institutes/${institute}`, { headers, data: { display_name: `Owned rebooking ${info.project.name}`, idempotency_key: `rebooking-write-customer-${info.project.name}` } });
  expect(customerReply.status(), await customerReply.text()).toBe(200); const customer = await customerReply.json();
  const ticketReply = await request.post(`${base}/tickets`, { headers, data: { institute_id: institute, service_id: "svc-aisselles", customer_id: customer.id } });
  expect(ticketReply.status()).toBe(200); const ticket = await ticketReply.json();
  const started = await request.post(`${base}/planning/sessions/start`, { headers, data: { ticket_id: ticket.id, employee_id: "emp-angela", service_id: "svc-aisselles" } });
  expect(started.status(), await started.text()).toBe(200); const session = await started.json();
  const finished = await request.patch(`${base}/planning/sessions/${session.id}/finish`, { headers });
  expect(finished.status()).toBe(200); const completed = await finished.json();
  const future = new Date(Date.now()+7*86400000); future.setUTCHours(info.project.name === "desktop" ? 10 : 11, 0, 0, 0);
  const bookingReply = await request.post(`${base}/appointments`, { headers, data: { institute_id: institute, employee_id: "emp-angela", service_id: "svc-aisselles",
    customer_id: customer.id, customer_name: customer.display_name, start_time: future.toISOString(), idempotency_key: `rebooking-write-target-${info.project.name}` } });
  expect(bookingReply.status(), await bookingReply.text()).toBe(200); const booking = await bookingReply.json();
  let original: any, cancellation: any, posts = 0, cancellations = 0;
  const enter = async () => {
    await page.getByRole("button", { name: "Équipe", exact: true }).click();
    await page.getByRole("button", { name: "Déclarations de rebooking", exact: true }).click();
  };
  const panel = page.getByRole("region", { name: "Gestion du rebooking" });
  try {
    await page.route("**/workforce/institutes/*/rebookings", async route => {
      if (route.request().method() !== "POST") return route.continue();
      posts++; const actual = await route.fetch(); expect(actual.status()).toBe(200); original = await actual.json();
      await route.abort("failed");
    });
    await enter(); await panel.getByLabel("Collaboratrice du rebooking").selectOption("emp-angela");
    await panel.getByRole("combobox", { name: "Prestation terminée", exact: true }).selectOption(`session:${session.id}`);
    await panel.getByRole("combobox", { name: "Réservation liée", exact: true }).selectOption(booking.id);
    await panel.getByLabel("Motif de déclaration", { exact: true }).fill(`Native declaration ${info.project.name}`);
    await panel.getByRole("button", { name: "Déclarer un rebooking", exact: true }).click();
    await expect(panel.getByRole("heading", { name: "Nouvelle déclaration", exact: true })).toBeInViewport();
    await panel.getByText("Prestation sélectionnée", { exact: true }).click();
    await panel.getByText("Réservation sélectionnée", { exact: true }).click();
    await panel.getByRole("form", { name: "Déclarer un rebooking", exact: true }).screenshot({ path: info.outputPath("native-rebooking-choices.png") });
    await panel.getByRole("button", { name: "Enregistrer le rebooking", exact: true }).click();
    await expect(panel.getByRole("alert")).toBeVisible(); expect(posts).toBe(1); expect(original).toBeTruthy();
    const protectedKey = await page.evaluate(() => Object.keys(sessionStorage).find(key => key.startsWith("flowpilot.rebooking-request:"))!);
    expect(await page.evaluate(key => JSON.parse(sessionStorage.getItem(key)!).intent.terms.idempotency_key, protectedKey)).toBe(original.idempotency_key);
    await page.reload(); await enter();
    await panel.getByRole("button", { name: "Reprendre la demande de rebooking conservée", exact: true }).click();
    await expect(panel.getByRole("status").filter({ hasText: /^Rebooking déclaré\.$/ })).toBeVisible(); expect(posts).toBe(1);
    expect(await page.evaluate(key => sessionStorage.getItem(key), protectedKey)).toBeNull();
    const card = panel.locator("li").filter({ hasText: original.id });
    await card.locator("summary").click(); await expect(card).toContainText(completed.real_end_time);
    await expect(card).toContainText(original.booking_capture.creation_event_id);
    await page.route("**/workforce/institutes/*/rebookings/*/cancel", async route => {
      cancellations++; const actual = await route.fetch(); expect(actual.status()).toBe(200); cancellation = await actual.json();
      await route.abort("failed");
    });
    await card.getByRole("button", { name: "Annuler cette déclaration", exact: true }).click();
    await panel.getByLabel("Motif d’annulation du rebooking", { exact: true }).fill("Native explicit correction");
    await panel.getByRole("button", { name: "Confirmer l’annulation de la déclaration", exact: true }).click();
    await expect(panel.getByRole("alert")).toBeVisible(); expect(cancellations).toBe(1); expect(cancellation).toBeTruthy();
    await page.reload(); await enter();
    await panel.getByRole("button", { name: "Reprendre la demande de rebooking conservée", exact: true }).click();
    await expect(panel.getByRole("status").filter({ hasText: /^Déclaration annulée ; original conservé\.$/ })).toBeVisible(); expect(cancellations).toBe(1);
    expect(await page.evaluate(key => sessionStorage.getItem(key), protectedKey)).toBeNull();
    const retained = await (await request.get(`${workforce}/rebookings/${original.id}`, { headers })).json();
    expect(retained.source_capture).toEqual(original.source_capture); expect(retained.booking_capture).toEqual(original.booking_capture);
    expect(retained.cancellation.id).toBe(cancellation.id);
    await expect(panel.locator("li").filter({ hasText: original.id })).toContainText("original conservé");
    for (const control of await panel.locator("button,select,input,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth+1)).toBe(false);
    await panel.screenshot({ path: info.outputPath("native-rebooking-write.png") });
  } finally {
    if (original && !cancellation) expect((await request.post(`${workforce}/rebookings/${original.id}/cancel`, { headers, data: { reason: "Owned fixture closure", idempotency_key: `rebooking-write-cleanup-${info.project.name}` } })).status()).toBe(200);
    expect((await request.patch(`${base}/appointments/${booking.id}/cancel`, { headers })).status()).toBe(200);
  }
});
