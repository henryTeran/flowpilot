import { expect as baseExpect, test } from "@playwright/test";
import { spawnSync } from "node:child_process";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(180000);
test("native cancelled walk-in review preserves original commercial values and explicit missing coverage", async ({ page }, info) => {
  const python = process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python";
  const seed = spawnSync(python, ["browser-tests/walk_in_cancellation_fixture.py", info.project.name], { encoding: "utf8", env: process.env });
  expect(seed.status,seed.stderr+seed.stdout).toBe(0); const fixture = JSON.parse(seed.stdout.trim().split(/\r?\n/).at(-1)!);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com"); await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click(); await expect(page.locator(".flow-session-exit")).toBeVisible();
  let reads = 0, corrupt = false; const methods: string[] = [];
  await page.route("**/walk-in-cancellations?**", async route => { reads++; methods.push(route.request().method());
    if (!corrupt) return route.continue(); const response = await route.fetch(); const value = await response.json(); value.causal_loss_proven = true; await route.fulfill({ response, json: value }); });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click(); const panel = page.getByRole("region", { name: "Annulations sans rendez-vous", exact: true });
  await expect(panel).toBeVisible(); expect(reads).toBe(0);
  await panel.getByLabel("Début des annulations", { exact: true }).fill(fixture.start); await panel.getByLabel("Fin des annulations exclue", { exact: true }).fill(fixture.end);
  const read = panel.getByRole("button", { name: "Lire les annulations sans rendez-vous", exact: true }); await read.click();
  await expect(panel).toContainText(info.project.name === "desktop" ? "1–20 sur 26" : "1–20 sur 52");
  await expect(panel).toContainText("Sous-total connu, incomplet"); await expect(panel).toContainText("Devise inconnue : aucun montant monétaire affiché");
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  async function findOwn(id: string) {
    await expect(read).toBeEnabled(); await expect(panel.getByRole("status")).toHaveCount(0);
    const card = panel.locator("article").filter({ has: page.getByRole("heading", { name: `Ticket annulé ${id}`, exact: true }) });
    while (!await card.count()) { await panel.getByRole("button", { name: "Annulations suivantes", exact: true }).click(); await expect(read).toBeEnabled(); await expect(panel.getByRole("status")).toHaveCount(0); }
    return card;
  }
  const zero = await findOwn(fixture.zero); await expect(zero).toContainText("0.00 CHF"); await zero.locator("summary").click();
  await expect(zero).toContainText("fixture-source 😀"); await expect(zero).toContainText("2 unités"); await expect(zero).toContainText("Total de ligne : 1.01 CHF"); await expect(zero).toContainText("Retirée de la facture");
  await expect(zero).not.toContainText("999.00"); for (const control of await panel.locator("button,input,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await zero.screenshot({ path: info.outputPath("native-walk-in-original.png") });
  const unknown = await findOwn(fixture.unknown); await unknown.locator("summary").click(); await expect(unknown).toContainText("Devise inconnue : valeur indisponible"); await expect(unknown).not.toContainText("1.01");
  await unknown.screenshot({ path: info.outputPath("native-walk-in-unknown.png") });
  const legacy = await findOwn(fixture.legacy); await expect(legacy).toContainText("Annulation ancienne sans preuve tarifaire"); await expect(legacy.locator("details")).toHaveCount(0);
  await expect(panel).toContainText(info.project.name === "desktop" ? "21–26 sur 26" : "41–52 sur 52");
  corrupt = true; await read.click(); await expect(panel.getByRole("alert")).toBeVisible(); await expect(panel.locator("article")).toHaveCount(0);
  corrupt = false; await read.click(); await expect(panel.getByRole("alert")).toHaveCount(0); await expect(panel.locator("article").first()).toBeVisible();
  await panel.getByLabel("Début des annulations", { exact: true }).fill("2026-01-02"); await expect(panel.locator("article")).toHaveCount(0);
  expect(methods.every(m => m === "GET")).toBe(true); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
