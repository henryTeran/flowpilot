import { expect, test } from "@playwright/test";

test.use({ timezoneId: "America/Los_Angeles" });
test("native skill matrix pages recorded facts, refreshes configuration and refuses corrupted or foreign reads", async ({ page, request }, info) => {
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1";
  const institute = "demo-institute-geneve", skillPath = `${base}/resources/institutes/${institute}/employees/emp-angela/skills`;
  const requirementPath = `${base}/resources/institutes/${institute}/services/svc-aisselles/requirements`;
  const originalSkills = await (await request.get(skillPath, { headers })).json();
  const originalRequirements = await (await request.get(requirementPath, { headers })).json();
  const code = `MATRIX_${info.project.name}`;
  expect((await request.patch(requirementPath, { headers, data: { ...originalRequirements, skills: [code] } })).status()).toBe(200);
  expect((await request.patch(skillPath, { headers, data: { skills: [...new Set([...originalSkills.skills, code])] } })).status()).toBe(200);
  // Explicit disposable reference data exercises employee pagination beyond the live board's page.
  for (let index = 0; index < 8; index++) {
    const created = await request.post(`${base}/employees`, { headers, data: { institute_id: institute,
      first_name: `Matrix ${info.project.name} ${index}`, skills: [] } });
    expect(created.status()).toBe(200);
  }
  await page.getByRole("button", { name: "Équipe", exact: true }).click();
  const panel = page.getByRole("main", { name: "Compétences de l’équipe" });
  await expect(panel.getByRole("heading", { name: "Matrice des compétences" })).toBeVisible();
  const covered = panel.locator('td[aria-label="Angela · Aisselles"]');
  await expect(covered).toContainText("Exigences couvertes");
  await expect(panel.locator('td[aria-label="Assya · Aisselles"]')).toContainText(`Manque : ${code}`);
  await expect(panel).toContainText("Aucune exigence enregistrée");
  await expect(panel).toContainText("ni une certification ni la disponibilité");
  await expect(panel).toContainText("Europe/Zurich");
  await panel.getByRole("button", { name: "Collaboratrices suivantes", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Collaboratrices précédentes", exact: true })).toBeEnabled();
  await expect(panel.getByRole("button", { name: "Collaboratrices suivantes", exact: true })).toBeDisabled();
  expect(await panel.locator("tbody tr").count()).toBeGreaterThan(0);
  await panel.getByRole("button", { name: "Prestations suivantes", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Prestations précédentes", exact: true })).toBeEnabled();
  await panel.getByRole("button", { name: "Collaboratrices précédentes", exact: true }).click();
  await panel.getByRole("button", { name: "Prestations précédentes", exact: true }).click();
  await expect(covered).toContainText("Exigences couvertes");
  // The same protected server authority changes recorded requirements; the native read refreshes.
  expect((await request.patch(requirementPath, { headers, data: { ...originalRequirements, skills: [code, "MATRIX_MISSING"] } })).status()).toBe(200);
  await panel.getByRole("button", { name: "Actualiser les compétences", exact: true }).click();
  await expect(covered).toContainText("Manque : MATRIX_MISSING");
  const corrupt = async (route: any) => {
    const actual = await route.fetch(), value = await actual.json();
    value.cells[0].meets_recorded_requirements = !value.cells[0].meets_recorded_requirements;
    await route.fulfill({ response: actual, json: value });
  };
  await page.route("**/workforce/institutes/*/skill-matrix?**", corrupt);
  await panel.getByRole("button", { name: "Actualiser les compétences", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("incohérente");
  await expect(panel.locator("table")).toHaveCount(0);
  await page.unroute("**/workforce/institutes/*/skill-matrix?**", corrupt);
  await panel.getByRole("button", { name: "Réessayer", exact: true }).click();
  await expect(covered).toContainText("Manque : MATRIX_MISSING");
  expect((await request.get(`${base}/workforce/institutes/foreign/skill-matrix`, { headers })).status()).toBe(403);
  for (const button of await panel.getByRole("button").all()) expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  const lastNavigationItem = page.getByRole("navigation").getByRole("button", { name: "Parametres", exact: true });
  await lastNavigationItem.scrollIntoViewIfNeeded();
  await expect(lastNavigationItem).toBeInViewport();
  const lastBox = (await lastNavigationItem.boundingBox())!, logoutBox = (await page.locator(".bm-logout-button").boundingBox())!;
  expect(lastBox.y + lastBox.height).toBeLessThanOrEqual(logoutBox.y);
  await page.getByRole("button", { name: "Équipe", exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath("skill-matrix.png"), fullPage: true });
  // Restore shared signed fixture authority for subsequent workflows.
  expect((await request.patch(requirementPath, { headers, data: originalRequirements })).status()).toBe(200);
  expect((await request.patch(skillPath, { headers, data: originalSkills })).status()).toBe(200);
});

test("reception opens the native matrix and cannot replace recorded employee skills", async ({ page, request }) => {
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill("cashier@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  await page.getByRole("button", { name: "Équipe", exact: true }).click();
  const panel = page.getByRole("main", { name: "Compétences de l’équipe" });
  await expect(panel.locator("table")).toBeVisible();
  await expect(panel.locator("input,select,textarea")).toHaveCount(0);
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` };
  const path = "http://127.0.0.1:4198/api/v1/resources/institutes/demo-institute-geneve/employees/emp-angela/skills";
  const original = await (await request.get(path, { headers })).json();
  expect((await request.patch(path, { headers, data: { skills: ["UNAUTHORIZED"] } })).status()).toBe(403);
  expect(await (await request.get(path, { headers })).json()).toEqual(original);
});
