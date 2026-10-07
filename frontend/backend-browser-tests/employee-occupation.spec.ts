import { expect, test } from "@playwright/test";
test.use({ timezoneId: "America/Los_Angeles" });
test("native occupation retains actual execution and declared denominator without claiming complete coverage", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  const workforce = `${base}/workforce/institutes/${institute}`;
  const created = await request.post(`${base}/tickets`, { headers, data: { institute_id: institute, service_id: "svc-aisselles" } });
  expect(created.status()).toBe(200); const ticket = await created.json();
  const started = await request.post(`${base}/planning/sessions/start`, { headers, data: { ticket_id: ticket.id, employee_id: "emp-angela", service_id: "svc-aisselles" } });
  expect(started.status(), await started.text()).toBe(200); const session = await started.json();
  const finished = await request.patch(`${base}/planning/sessions/${session.id}/finish`, { headers });
  expect(finished.status()).toBe(200); const completed = await finished.json();
  const work = await request.post(`${workforce}/work-intervals`, { headers, data: { employee_id: "emp-angela", start_time: session.start_time,
    end_time: completed.real_end_time, reason: `Owned occupation ${info.project.name}`, idempotency_key: `native-occupation-${info.project.name}` } });
  expect(work.status(), await work.text()).toBe(200); const original = await work.json();
  try {
    await page.getByRole("button", { name: "Équipe", exact: true }).click(); await page.getByRole("button", { name: "Calendrier individuel", exact: true }).click();
    const profile = page.getByRole("region", { name: "Profil et calendrier individuel" });
    await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-angela");
    const panel = profile.getByRole("region", { name: "Occupation enregistrée" });
    await expect(panel).toContainText("100,00 %"); await expect(panel).toContainText("complètes restent inconnues");
    await expect(panel).toContainText("Heures déclarées à cette lecture");
    const card = panel.locator("li").filter({ hasText: session.id }); await card.locator("summary").click();
    await expect(card).toContainText(session.start_time); await expect(card).toContainText(completed.real_end_time);
    await profile.getByRole("button", { name: "Consulter l’occupation", exact: true }).click();
    await expect(panel.getByRole("heading", { name: "Occupation enregistrée" })).toBeInViewport();
    const path = "**/workforce/institutes/*/employees/*/occupation?**";
    const corrupt = async (route: any) => { const actual = await route.fetch(), value = await actual.json(); value.complete_activity = true; await route.fulfill({ response: actual, json: value }); };
    await page.route(path, corrupt); await panel.getByRole("button", { name: "Actualiser l’occupation" }).click();
    await expect(panel.getByRole("alert")).toContainText("à vérifier"); await expect(panel.locator("li")).toHaveCount(0);
    await page.unroute(path, corrupt); await panel.getByRole("button", { name: "Actualiser l’occupation" }).click(); await expect(panel).toContainText("100,00 %");
    for (const control of await panel.locator("button,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth+1)).toBe(false);
    await panel.screenshot({ path: info.outputPath("native-occupation.png") });
    await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-assya");
    await expect(panel).toContainText("Occupation non déterminable"); await expect(panel).not.toContainText(session.id);
  } finally {
    expect((await request.post(`${workforce}/work-intervals/${original.id}/cancel`, { headers, data: { reason: "Owned fixture closure", idempotency_key: `native-occupation-cancel-${info.project.name}` } })).status()).toBe(200);
  }
});
