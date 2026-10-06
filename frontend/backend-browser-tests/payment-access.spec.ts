import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, name: string) {
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill(`${name}@browser.example.com`);
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "Navigation FlowPilot" }).getByRole("button", { name: "Déconnexion", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  expect(token).toBeTruthy();
  return { Authorization: `Bearer ${token}` };
}

test("real signed manager session reads cashflows and rejects foreign scope", async ({ page, request }) => {
  const headers = await login(page, "manager");
  const panel = page.getByRole("region", { name: "Flux des paiements prestataire" });
  await expect(panel.getByText("Aucun flux prestataire enregistré.")).toBeVisible();
  await panel.getByRole("button", { name: "Actualiser les flux" }).click();
  await expect(panel.getByText("Aucun flux prestataire enregistré.")).toBeVisible();
  const forbidden = await request.get("http://127.0.0.1:4198/api/v1/payments/institutes/foreign/cashflows", { headers });
  expect(forbidden.status()).toBe(403);
  await page.getByRole("complementary", { name: "Navigation FlowPilot" }).getByRole("button", { name: "Déconnexion", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Ouvrir mon institut" })).toBeVisible();
  await expect(panel).toHaveCount(0);
  expect(await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"))).toBeNull();
});

test("real cashier session cannot read manager cashflows or activate an unconfigured provider", async ({ page, request }) => {
  const headers = await login(page, "cashier");
  await expect(page.getByRole("region", { name: "Flux des paiements prestataire" })).toHaveCount(0);
  const base = "http://127.0.0.1:4198/api/v1/payments/institutes/demo-institute-geneve";
  expect((await request.get(`${base}/cashflows`, { headers })).status()).toBe(403);
  expect((await request.get(`${base}/tickets/absent/authorization-quote`, { headers })).status()).toBe(503);
});
