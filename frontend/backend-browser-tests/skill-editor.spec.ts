import { expect, test } from "@playwright/test";

test("native skill change recovers its original without overwriting later configuration", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1";
  const skillPath = `${base}/resources/institutes/demo-institute-geneve/employees/emp-angela/skills`;
  const beforeReply = await request.get(skillPath, { headers }); expect(beforeReply.status()).toBe(200);
  const before = await beforeReply.json(), code = `NATIVE_${info.project.name}`;
  const open = async () => {
    await page.getByRole("button", { name: "Équipe", exact: true }).click();
    await page.getByRole("button", { name: "Gérer les compétences", exact: true }).click();
    return page.getByRole("region", { name: "Gestion des compétences" });
  };
  let panel = await open(); await panel.getByLabel("Collaboratrice des compétences").selectOption("emp-angela");
  await expect(panel.getByLabel("Ajouter un code de compétence")).toBeEnabled();
  await panel.getByLabel("Ajouter un code de compétence").fill(code);
  await panel.getByRole("button", { name: "Ajouter le code", exact: true }).click();
  await panel.getByLabel("Motif de modification des compétences").fill("Formation déclarée par la responsable");
  let posts = 0;
  page.on("request", req => { if (req.method() === "POST" && req.url().endsWith("/skill-changes")) posts++; });
  const path = "**/workforce/institutes/*/skill-changes";
  let original: any;
  const lose = async (route: any) => {
    const actual = await route.fetch(); expect(actual.status(), await actual.text()).toBe(200); original = await actual.json();
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Saved reply unavailable" }) });
  };
  await page.route(path, lose);
  await panel.getByRole("button", { name: "Enregistrer les compétences", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("Saved reply unavailable");
  await expect(panel.getByLabel("Collaboratrice des compétences")).toBeDisabled();
  // Another authorized configuration succeeds after the unknown response.
  // Recovery must return the first original, never replay its obsolete write.
  expect((await request.patch(skillPath, { headers, data: before })).status()).toBe(200);
  await page.unroute(path, lose); await page.reload(); panel = await open();
  await panel.getByRole("button", { name: "Reprendre la modification conservée" }).click();
  await expect(panel).toContainText("Modification originale vérifiée ; compétences actuelles relues."); expect(posts).toBe(1);
  expect(await (await request.get(skillPath, { headers })).json()).toEqual(before);
  const originalReply = await request.get(`${base}/workforce/institutes/demo-institute-geneve/skill-changes/original/${original.idempotency_key}`, { headers });
  expect(originalReply.status()).toBe(200); expect(await originalReply.json()).toEqual(original);
  await expect(panel.getByRole("button", { name: `Retirer ${code}`, exact: true })).toHaveCount(0);
  for (const control of await panel.locator("input,select,button").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth+1)).toBe(false);
  await page.screenshot({ path: info.outputPath("native-skill-editor.png"), fullPage: true });
});

test("reception has a matrix but no native skill editor", async ({ page, request }) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("cashier@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  await page.getByRole("button", { name: "Équipe", exact: true }).click();
  await expect(page.getByRole("button", { name: "Gérer les compétences", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Matrice des compétences" })).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  expect((await request.get("http://127.0.0.1:4198/api/v1/workforce/institutes/demo-institute-geneve/skill-changes/original/missing", {
    headers: { Authorization: `Bearer ${token}` },
  })).status()).toBe(403);
});
