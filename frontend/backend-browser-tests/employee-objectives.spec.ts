import { expect, test } from "@playwright/test";
test.use({ timezoneId: "America/Los_Angeles" });
test("employee profile preserves original objective periods, exact targets and cancelled history", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1/workforce/institutes/demo-institute-geneve";
  const created = await request.post(`${base}/objectives`, { headers, data: { employee_id: "emp-angela", title: "Original declared target",
    metric: "closed_attributed_gross", currency: "CHF", target: "90071992547409.93", first_day: "2026-10-25", last_day: "2026-10-25",
    reason: "Owned browser fixture", idempotency_key: `native-objective-${info.project.name}` } });
  expect(created.status(), await created.text()).toBe(200); const original = await created.json();
  await page.getByRole("button", { name: "Équipe", exact: true }).click();
  await page.getByRole("button", { name: "Calendrier individuel", exact: true }).click();
  const profile = page.getByRole("region", { name: "Profil et calendrier individuel" });
  await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-angela");
  const panel = profile.getByRole("region", { name: "Objectifs individuels" });
  await expect(panel).toContainText("90071992547409,93 CHF"); await expect(panel).toContainText("2026-10-25");
  await profile.getByRole("button", { name: "Consulter les objectifs", exact: true }).click();
  await expect(panel.getByRole("heading", { name: "Objectifs individuels" })).toBeInViewport();
  await panel.locator("summary").first().click(); await expect(panel.locator("details[open]")).toContainText(original.period_start);
  const path = "**/workforce/institutes/*/employees/*/objectives?**";
  const corrupt = async (route: any) => { const actual = await route.fetch(), value = await actual.json(); value.rows[0].achieved = true; await route.fulfill({ response: actual, json: value }); };
  await page.route(path, corrupt); await panel.getByRole("button", { name: "Actualiser les objectifs" }).click();
  await expect(panel.getByRole("alert")).toContainText("à vérifier"); await expect(panel.locator("li")).toHaveCount(0);
  await page.unroute(path, corrupt);
  expect((await request.post(`${base}/objectives/${original.id}/cancel`, { headers, data: { reason: "Separate cancellation", idempotency_key: `native-cancel-${info.project.name}` } })).status()).toBe(200);
  await panel.getByRole("button", { name: "Actualiser les objectifs" }).click();
  await expect(panel).toContainText("Annulé, original conservé"); await expect(panel).toContainText("90071992547409,93 CHF");
  await expect(panel).not.toContainText("Progrès enregistré");
  for (const control of await panel.locator("button, summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth+1)).toBe(false);
  await panel.screenshot({ path: info.outputPath("native-objectives.png") });
  await profile.getByLabel("Collaboratrice du calendrier").selectOption("emp-assya");
  await expect(panel).toContainText("Aucun objectif enregistré"); await expect(panel).not.toContainText("90071992547409");
});
