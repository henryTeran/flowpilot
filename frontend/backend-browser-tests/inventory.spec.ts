import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, operator: string) {
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill(`${operator}@browser.example.com`);
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  await page.getByRole("button", { name: "Inventaire", exact: true }).click();
}

test("signed inventory UI recovers a committed receipt after a lost reply and reload, then restricts cashier writes", async ({ page, request }, info) => {
  await login(page, "manager");
  const creation = page.getByRole("form", { name: "Créer un article" });
  const sku = `BROWSER-${info.project.name}`;
  await creation.getByLabel("Référence", { exact: true }).fill(sku);
  await creation.getByLabel("Nom de l'article").fill(`Serum ${info.project.name}`);
  await creation.getByLabel("Catégorie").selectOption("cabine");
  await creation.getByRole("combobox", { name: "Unité", exact: true }).selectOption("ml");
  await creation.getByLabel("Seuil de réapprovisionnement").fill("4,125");
  await creation.getByLabel("Motif").fill("Catalogue navigateur");
  const prepared = page.waitForResponse(response => response.url().includes("/inventory/") && response.url().endsWith("/items") && response.request().method() === "POST");
  await creation.getByRole("button", { name: "Enregistrer l'article", exact: true }).click();
  const created = await prepared;
  expect(created.status()).toBe(200);
  const item = await created.json();
  const detail = page.getByRole("region", { name: "Article de stock" });
  await expect(detail).toContainText("Stock enregistré : 0,000 ml");
  const form = detail.getByRole("form", { name: "Enregistrer un mouvement" });
  await form.getByLabel("Quantité (ml)").fill("10,125");
  await form.getByLabel("Motif").fill("Livraison navigateur");
  let lost = false;
  let committed!: { id: string; idempotency_key: string };
  await page.route(`**/inventory/institutes/demo-institute-geneve/items/${item.id}/movements`, async route => {
    if (!lost && route.request().method() === "POST") {
      lost = true;
      const actual = await route.fetch();
      expect(actual.status()).toBe(200);
      committed = await actual.json();
      await route.abort("failed"); // The real backend committed; only its transport reply is lost.
    } else await route.continue();
  });
  await form.getByRole("button", { name: "Enregistrer le mouvement", exact: true }).click();
  await expect(form.getByRole("button", { name: "Reprendre la demande conservée" })).toBeVisible();
  await expect(form.getByRole("alert")).toBeVisible();
  expect(committed.id).toBeTruthy();
  await page.reload();
  await page.getByRole("button", { name: "Inventaire", exact: true }).click();
  await page.locator(".bm-stock-card").filter({ hasText: sku }).click();
  await expect(form).toContainText("Demande conservée : 10,125 ml");
  const retry = page.waitForResponse(response => response.url().endsWith(`/items/${item.id}/movements`) && response.request().method() === "POST");
  await form.getByRole("button", { name: "Reprendre la demande conservée" }).click();
  const recovered = await retry;
  expect(recovered.status()).toBe(200);
  expect(await recovered.json()).toMatchObject({ id: committed.id, idempotency_key: committed.idempotency_key, quantity: "10.125" });
  await expect(form).toContainText("Mouvement enregistré.");
  await expect(detail).toContainText("Stock enregistré : 10,125 ml");
  await form.getByLabel("Type de mouvement").selectOption("adjustment");
  await form.getByLabel("Quantité (ml)").fill("-6");
  await form.getByLabel("Motif").fill("Inventaire physique");
  await form.getByRole("button", { name: "Enregistrer le mouvement", exact: true }).click();
  await expect(detail).toContainText("Stock enregistré : 4,125 ml");
  await expect(detail.locator("li")).toHaveCount(2);
  await expect(page.locator(".bm-stock-card").filter({ hasText: sku })).toContainText("Au seuil ou en dessous");
  await page.screenshot({ path: info.outputPath("inventory.png"), fullPage: true });
  await page.getByRole("complementary", { name: "Navigation FlowPilot" }).getByRole("button", { name: "Déconnexion", exact: true }).click();
  await login(page, "cashier");
  await expect(creation).toHaveCount(0);
  await page.locator(".bm-stock-card").filter({ hasText: sku }).click();
  await expect(detail).toContainText("Stock enregistré : 4,125 ml");
  await expect(form).toHaveCount(0);
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const base = `http://127.0.0.1:4198/api/v1/inventory/institutes/demo-institute-geneve/items/${item.id}`;
  const headers = { Authorization: `Bearer ${token}` };
  expect((await request.post(`${base}/movements`, { headers, data: { kind: "receipt", quantity: "1", reason: "Forbidden cashier", idempotency_key: "forbidden" } })).status()).toBe(403);
  expect((await (await request.get(`${base}/movements`, { headers })).json())).toHaveLength(2);
});
