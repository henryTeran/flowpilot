import { expect, test } from "@playwright/test";
test.use({ timezoneId: "America/Los_Angeles" });
test("native employee calendar separates current availability, selected institute day and original execution facts", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  // Signed disposable fixture workflow records actual start/finish; this test
  // exercises native profile/calendar reading rather than physical execution.
  const ticketReply = await request.post(`${base}/tickets`, { headers, data: { institute_id: institute, service_id: "svc-aisselles" } });
  expect(ticketReply.status()).toBe(200); const ticket = await ticketReply.json();
  const startReply = await request.post(`${base}/planning/sessions/start`, { headers, data: { ticket_id: ticket.id, employee_id: "emp-angela", service_id: "svc-aisselles" } });
  expect(startReply.status(), await startReply.text()).toBe(200); const execution = await startReply.json();
  expect((await request.patch(`${base}/planning/sessions/${execution.id}/finish`, { headers })).status()).toBe(200);
  let year = new Date().getUTCFullYear();
  const fold = () => { const last = new Date(Date.UTC(year, 9, 31)); return new Date(last.getTime()-last.getUTCDay()*86400000).toISOString().slice(0, 10); };
  if (Date.parse(`${fold()}T00:30:00Z`) <= Date.now()+86400000) year++;
  const day = fold(), reason = `Calendar leave ${info.project.name}`;
  const appointmentReply = await request.post(`${base}/appointments`, { headers, data: { institute_id: institute, employee_id: "emp-angela", service_id: "svc-aisselles", customer_name: "Owned calendar fixture", start_time: `${day}T00:30:00Z` } });
  expect(appointmentReply.status()).toBe(200); const appointment = await appointmentReply.json();
  let absence: any;
  try {
    const absenceReply = await request.post(`${base}/workforce/institutes/${institute}/absences`, { headers, data: {
      employee_id: "emp-angela", kind: "leave", start_time: `${day}T02:00:00Z`, end_time: `${day}T03:00:00Z`, reason, idempotency_key: `calendar-${info.project.name}` } });
    expect(absenceReply.status()).toBe(200); absence = await absenceReply.json();
    await page.getByRole("button", { name: "Équipe", exact: true }).click();
    await page.getByRole("button", { name: "Calendrier individuel", exact: true }).click();
    const panel = page.getByRole("region", { name: "Profil et calendrier individuel" });
    await panel.getByLabel("Collaboratrice du calendrier").selectOption("emp-angela");
    await expect(panel).toContainText("Enregistré : début"); await expect(panel).toContainText("Terminé");
    await expect(panel).toContainText("Compétences enregistrées");
    await panel.getByLabel("Jour du calendrier individuel").fill(day);
    await expect(panel).toContainText("25 heures réelles");
    await expect(panel.locator("li").filter({ hasText: reason })).toBeVisible();
    await expect(panel.locator("li").filter({ hasText: "Rendez-vous" }).last()).toContainText("UTC+02:00");
    await expect(panel).toContainText("La disponibilité ci-dessus décrit l’instant de lecture");
    await panel.getByLabel("Collaboratrice du calendrier").selectOption("emp-assya");
    await expect(panel).toContainText("Aucun intervalle sur cette page"); await expect(panel).not.toContainText(reason);
    await panel.getByLabel("Collaboratrice du calendrier").selectOption("emp-angela"); await expect(panel).toContainText(reason);
    const corrupt = async (route: any) => { const actual = await route.fetch(), value = await actual.json(); value.employee.id = "foreign"; await route.fulfill({ response: actual, json: value }); };
    await page.route("**/workforce/institutes/*/employees/*/day?**", corrupt);
    await panel.getByRole("button", { name: "Actualiser le calendrier individuel" }).click();
    await expect(panel.getByRole("alert")).toContainText("à vérifier"); await expect(panel.locator("li")).toHaveCount(0);
    await page.unroute("**/workforce/institutes/*/employees/*/day?**", corrupt);
    await panel.getByRole("button", { name: "Réessayer le calendrier individuel" }).click(); await expect(panel).toContainText(reason);
    for (const control of await panel.locator("input,select,button").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth+1)).toBe(false);
    await page.screenshot({ path: info.outputPath("employee-calendar.png"), fullPage: true });
  } finally {
    expect((await request.patch(`${base}/appointments/${appointment.id}/cancel`, { headers })).status()).toBe(200);
    if (absence) expect((await request.post(`${base}/workforce/institutes/${institute}/absences/${absence.id}/cancel`, { headers, data: { reason: "Fixture release", idempotency_key: `calendar-release-${info.project.name}` } })).status()).toBe(200);
  }
});
