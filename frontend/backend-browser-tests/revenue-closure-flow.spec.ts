import { expect as baseExpect, test } from "@playwright/test";
import { spawnSync } from "node:child_process";
const expect = baseExpect.configure({ timeout: 15000 });
test.setTimeout(180000);
test("native closure/reference review retains a historical value and recovers after lost acknowledgement", async ({ page, request }, info) => {
  const python = process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python";
  const seeded = spawnSync(python, ["browser-tests/closure_fixture.py", info.project.name], { encoding: "utf8", env: process.env });
  expect(seeded.status, seeded.stderr+seeded.stdout).toBe(0); const fixture = JSON.parse(seeded.stdout.trim().split(/\r?\n/).at(-1)!);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com"); await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click(); await expect(page.locator(".flow-session-exit")).toBeVisible();
  let sourceReads = 0, posts = 0, retained: any, corrupt = false;
  await page.route("**/booking-closures?**", async route => { sourceReads++; await route.continue(); });
  await page.route("**/appointments/*/closure-value-originals", async route => { if (route.request().method() !== "POST") { await route.continue(); return; }
    posts++; const response = await route.fetch(); expect(response.status()).toBe(200); retained = await response.json();
    if (posts === 1) await route.abort("failed"); else await route.fulfill({ response }); });
  await page.getByRole("button", { name: "Pilotage", exact: true }).click(); const sources = page.getByRole("region", { name: "Annulations et absences déclarées", exact: true });
  await expect(sources).toBeVisible(); expect(sourceReads).toBe(0); expect(posts).toBe(0);
  await sources.getByLabel("Début des événements", { exact: true }).fill(fixture.start); await sources.getByLabel("Fin des événements exclue", { exact: true }).fill(fixture.end);
  await sources.getByRole("button", { name: "Lire les événements terminaux", exact: true }).click(); await expect(sources).toContainText("1–20 sur");
  await expect(sources).toContainText("absences déclarées"); await sources.getByRole("button", { name: "Événements suivants", exact: true }).click(); await expect(sources).toContainText("21–");
  await sources.getByRole("button", { name: "Événements précédents", exact: true }).click(); await expect(sources).toContainText("1–20 sur");
  const open = sources.getByRole("button", { name: `Lire les références tarifaires ${fixture.appointment_id}`, exact: true });
  if (!await open.count()) { await sources.getByRole("button", { name: "Événements suivants", exact: true }).click(); await expect(open).toBeVisible(); }
  await open.click(); const refs = page.getByRole("region", { name: "Références tarifaires de la réservation", exact: true });
  await expect(refs).toContainText("1–20 sur 25 références"); await expect(refs).toContainText("9.87 CHF"); await expect(refs).toContainText("12.34 CHF");
  await refs.getByRole("button", { name: "Références suivantes", exact: true }).click(); await expect(refs).toContainText("21–25 sur 25 références");
  await refs.getByRole("button", { name: "Références précédentes", exact: true }).click(); await expect(refs).toContainText("1–20 sur 25 références");
  for (const panel of [sources, refs]) {
    expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);
    for (const control of await panel.locator("button,input,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  await refs.locator("article").first().locator("summary").click();
  await sources.locator("article").first().screenshot({ path: info.outputPath("native-closure-source.png") });
  await refs.locator("article").first().screenshot({ path: info.outputPath("native-closure-reference.png") });
  await refs.getByRole("button", { name: /^Choisir cette référence / }).first().click(); const writer = page.getByRole("region", { name: "Conserver une valorisation", exact: true });
  await writer.getByLabel("Tarif déclaré").selectOption("member"); const reason = `Décision ${info.project.name} 😀\nTarif déclaré 2026-10-07T12:00:00Z`; await writer.getByLabel("Motif de la valorisation").fill(reason);
  await writer.getByRole("button", { name: "Conserver ce scénario de valorisation", exact: true }).click(); await expect(writer.getByRole("alert")).toBeVisible(); expect(posts).toBe(1);
  expect(retained.original.estimated_value.amount_minor).toBe("987"); expect(retained.original.actor_id).toBe("browser-manager"); expect(retained.original.request.reason).toBe(reason);
  const key = retained.original.idempotency_key, fingerprint = retained.fingerprint;
  await page.reload(); await expect(page.locator(".flow-session-exit")).toBeVisible(); await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  await expect(writer).toContainText(key); await writer.getByRole("button", { name: "Reprendre la valorisation par clé", exact: true }).click();
  await expect(writer).toContainText("Valorisation conservée et relue"); await expect(writer).toContainText("9.87 CHF"); expect(posts).toBe(1);
  await writer.locator("summary").click(); await expect(writer).toContainText(fingerprint);
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token")), headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1/revenue/institutes/demo-institute-geneve";
  for (let n = 0; n < 25; n++) {
    const created = await request.post(`${base}/appointments/${fixture.appointment_id}/closure-value-originals`, { headers, data: { valuation: { ...retained.original.request, reason: `Audit ${info.project.name} ${n}` }, idempotency_key: `closure-audit-${info.project.name}-${n}` } });
    expect(created.status()).toBe(200);
  }
  await page.route("**/closure-value-originals?**", async route => { const response = await route.fetch(), value = await response.json(); if (corrupt) value.causal_loss_proven = true; await route.fulfill({ response, json: value }); });
  const history = page.getByRole("region", { name: "Valorisations conservées", exact: true }), read = history.getByRole("button", { name: "Lire les valorisations conservées", exact: true });
  async function findOwn() {
    await expect(read).toBeEnabled();
    await expect(history.getByRole("status")).toHaveCount(0);
    for (let n = 0; n < 3 && !await history.getByText(reason, { exact: true }).count(); n++) {
      await history.getByRole("button", { name: "Valorisations suivantes", exact: true }).click(); await expect(history.getByRole("status")).toHaveCount(0);
    }
    await expect(history).toContainText(reason);
  }
  await read.click(); await expect(history).toContainText("1–20 sur");
  await history.getByRole("button", { name: "Valorisations suivantes", exact: true }).click(); await expect(history).toContainText("21–");
  await history.getByRole("button", { name: "Valorisations précédentes", exact: true }).click(); await expect(history).toContainText("1–20 sur"); await findOwn();
  corrupt = true; await read.click(); await expect(history.getByRole("alert")).toBeVisible(); await expect(history).not.toContainText(reason);
  corrupt = false; await read.click(); await findOwn();
  expect((await writer.boundingBox())!.width).toBeGreaterThanOrEqual(600);
  for (const control of await writer.locator("button,summary").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false); await writer.screenshot({ path: info.outputPath("native-closure-valuation.png") });
  expect((await request.get(base+"/closure-value-original-by-key", { params: { key }, headers })).status()).toBe(200);
  await writer.getByRole("button", { name: "Déclarer une autre valorisation", exact: true }).click();
  await sources.getByLabel("Début des événements", { exact: true }).fill(fixture.start); await sources.getByLabel("Fin des événements exclue", { exact: true }).fill(fixture.end);
  await sources.getByRole("button", { name: "Lire les événements terminaux", exact: true }).click(); await expect(sources).toContainText("1–20 sur");
  if (!await open.count()) { await sources.getByRole("button", { name: "Événements suivants", exact: true }).click(); await expect(open).toBeVisible(); }
  await open.click(); await expect(refs).toContainText("1–20 sur 25 références"); await refs.getByRole("button", { name: /^Choisir cette référence / }).first().click();
  await writer.getByLabel("Tarif déclaré").selectOption("passage"); await writer.getByLabel("Motif de la valorisation").fill(reason+" passage");
  await writer.getByRole("button", { name: "Conserver ce scénario de valorisation", exact: true }).click(); await expect(writer).toContainText("Valorisation conservée et relue");
  expect(posts).toBe(2); expect(retained.original.idempotency_key).not.toBe(key); expect(retained.original.estimated_value.amount_minor).toBe("1234"); await expect(history).not.toContainText(reason);
});
