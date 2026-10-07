import { expect, test } from "@playwright/test";
test.use({ timezoneId: "America/Los_Angeles" });
test("native employee hours retain microseconds and unknown attendance coverage", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1/workforce/institutes/demo-institute-geneve";
  const reply = await request.post(`${base}/work-intervals`, { headers, data: { employee_id: "emp-angela",
    start_time: "2025-10-26T00:30:00.000001Z", end_time: "2025-10-26T01:30:00.000002Z", reason: `Owned hours ${info.project.name}`, idempotency_key: `native-hours-${info.project.name}` } });
  expect(reply.status(), await reply.text()).toBe(200); const original = await reply.json();
  try {
    await page.getByRole("button", { name: "Équipe", exact: true }).click(); await page.getByRole("button", { name: "Calendrier individuel", exact: true }).click();
    const profile = page.getByRole("region", { name: "Profil et calendrier individuel" });
    await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-angela");
    await profile.getByLabel("Jour du calendrier individuel").fill("2025-10-26");
    const panel = profile.getByRole("region", { name: "Heures effectives déclarées" });
    await expect(panel).toContainText("Durée enregistrée sans double comptage : 1 h 00 min 00,000001 s");
    await expect(panel).toContainText("ne prouvent pas une présence complète");
    await profile.getByRole("button", { name: "Consulter les heures", exact: true }).click();
    await expect(panel.getByRole("heading", { name: "Heures effectives déclarées" })).toBeInViewport();
    const card = panel.locator("li").filter({ hasText: `Owned hours ${info.project.name}` }); await card.locator("summary").click();
    await expect(card).toContainText("UTC+02:00"); await expect(card).toContainText("UTC+01:00");
    await expect(card).toContainText(original.start_time); await expect(card).toContainText(original.id);
    const path = "**/workforce/institutes/*/employees/*/work-hours?**";
    const corrupt = async (route: any) => { const actual = await route.fetch(), value = await actual.json(); value.complete_attendance = true; await route.fulfill({ response: actual, json: value }); };
    await page.route(path, corrupt); await panel.getByRole("button", { name: "Actualiser les heures" }).click();
    await expect(panel.getByRole("alert")).toContainText("à vérifier"); await expect(panel.locator("li")).toHaveCount(0);
    await page.unroute(path, corrupt); await panel.getByRole("button", { name: "Actualiser les heures" }).click();
    await expect(panel).toContainText("1 h 00 min 00,000001 s");
    for (const control of await panel.locator("button,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth+1)).toBe(false);
    await panel.screenshot({ path: info.outputPath("native-work-hours.png") });
    await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-assya");
    await expect(panel).toContainText("Les heures travaillées restent inconnues"); await expect(panel).not.toContainText(original.id);
  } finally {
    expect((await request.post(`${base}/work-intervals/${original.id}/cancel`, { headers, data: { reason: "Owned fixture closure", idempotency_key: `native-hours-cancel-${info.project.name}` } })).status()).toBe(200);
  }
});
