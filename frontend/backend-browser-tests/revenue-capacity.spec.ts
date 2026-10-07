import { expect as baseExpect, test } from "@playwright/test";
import { formatWorkDuration } from "../src/work-hours-utils";
test.use({ timezoneId: "America/Los_Angeles" });
test.setTimeout(180000);
const expect = baseExpect.configure({ timeout: 15000 });
test("native capacity reads all staff totals, source evidence and pages without certifying physical availability", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  for (let i = 0; i < 21; i++) expect((await request.post(`${base}/employees`, { headers, data: { institute_id: institute, first_name: `Capacity ${info.project.name} ${i}`, skills: [] } })).status()).toBe(200);
  const employees: any[] = [];
  for (let offset = 0; ; offset += 20) {
    const source = await request.get(`${base}/employees?institute_id=${institute}&offset=${offset}&limit=20`, { headers });
    expect(source.status()).toBe(200); const rows = await source.json(); employees.push(...rows); if (rows.length < 20) break;
  }
  const originals: any[] = [];
  const capacity = `${base}/revenue/institutes/${institute}/capacity?day=2025-10-26&limit=20`;
  const initial = await request.get(capacity, { headers }); expect(initial.status()).toBe(200);
  expect((await initial.json()).recorded_unoccupied_duration_us).toBeNull();
  try {
    for (const e of employees) {
      const reply = await request.post(`${base}/workforce/institutes/${institute}/work-intervals`, { headers, data: {
        employee_id: e.id, start_time: "2025-10-26T00:30:00.000001Z", end_time: "2025-10-26T01:30:00.000002Z",
        reason: `Owned capacity ${info.project.name}`, idempotency_key: `capacity-${info.project.name}-${e.id}` } });
      expect(reply.status(), await reply.text()).toBe(200); originals.push(await reply.json());
    }
    const actual = await (await request.get(capacity, { headers })).json();
    expect(actual.employee_count).toBe(employees.length); expect(actual.employee_count).toBeGreaterThan(20);
    expect(actual.recorded_unoccupied_duration_us).toBe(String(3600000001n * BigInt(employees.length)));
    expect(actual.window.start).toBe("2025-10-25T22:00:00Z"); expect(actual.window.end).toBe("2025-10-26T23:00:00Z");
    let reads = 0, corrupt = false;
    await page.route("**/revenue/institutes/*/capacity?**", async route => {
      reads++; const response = await route.fetch(), value = await response.json(); expect(response.status()).toBe(200);
      if (corrupt) value.complete_attendance = true;
      await route.fulfill({ response, json: value });
    });
    await page.getByRole("button", { name: "Pilotage", exact: true }).click();
    const panel = page.getByRole("region", { name: "Capacités enregistrées", exact: true });
    await expect(panel).toBeVisible(); expect(reads).toBe(0);
    await panel.getByLabel("Journée des capacités").fill("2025-10-26");
    const button = panel.getByRole("button", { name: "Lire les capacités enregistrées", exact: true }); await button.click();
    await expect(panel).toContainText(`${employees.length} collaboratrices dans l’institut`);
    await expect(panel).toContainText(`Durée déclarée sans activité enregistrée : ${formatWorkDuration(actual.recorded_unoccupied_duration_us)}`);
    await expect(panel).toContainText("Utilisation enregistrée : 0,00 %");
    await expect(panel).toContainText("ni des créneaux réservables");
    await panel.locator("summary").first().click(); await expect(panel.locator("details[open]")).toContainText("Déclaration");
    await panel.getByRole("button", { name: "Collaboratrices suivantes" }).click();
    await expect(panel).toContainText(`21–${Math.min(40, employees.length)} sur ${employees.length}`);
    await expect(panel).toContainText(formatWorkDuration(actual.recorded_unoccupied_duration_us));
    await panel.getByRole("button", { name: "Collaboratrices précédentes" }).click();
    await expect(panel).toContainText(`1–20 sur ${employees.length}`);
    corrupt = true; await button.click(); await expect(panel.getByRole("alert")).toBeVisible();
    await expect(panel).not.toContainText("Totaux de toutes les collaboratrices");
    corrupt = false; await button.click(); await expect(panel).toContainText(`1–20 sur ${employees.length}`);
    await panel.locator("summary").first().click();
    expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
    for (const control of await panel.locator("button,input,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false);
    await panel.screenshot({ path: info.outputPath("native-revenue-capacity.png") });
    await panel.getByRole("heading", { name: "Capacités enregistrées", exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath("native-revenue-capacity-viewport.png") });
  } finally {
    for (const original of originals) expect((await request.post(`${base}/workforce/institutes/${institute}/work-intervals/${original.id}/cancel`, { headers,
      data: { reason: "Owned capacity fixture closure", idempotency_key: `capacity-cancel-${original.id}` } })).status()).toBe(200);
  }
});
