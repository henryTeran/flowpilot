import { expect, test } from "@playwright/test";
test.use({ actionTimeout: 15000 });

test("signed native contact declaration verifies canonical email, recovers lost reply and retains withdrawal history", async ({ page, request }, info) => {
  test.setTimeout(120000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token")), headers = { Authorization: `Bearer ${token}` };
  const api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve", name = `Contacts ${info.project.name}`;
  const response = await request.post(`${api}/customers/institutes/${institute}`, { headers, data: { display_name: name, idempotency_key: `contacts-client-${info.project.name}` } });
  expect(response.status()).toBe(200); const customer = await response.json();
  async function select() {
    await page.getByRole("button", { name: "Clientes", exact: true }).click();
    const directory = page.getByRole("region", { name: "Clientes et CRM", exact: true });
    await directory.getByLabel("Nom ou téléphone").fill(name); await directory.getByRole("button", { name: "Rechercher", exact: true }).click();
    await directory.getByRole("button", { name, exact: true }).click();
  }
  await select(); const editor = page.getByRole("region", { name: "Contacts marketing", exact: true });
  await editor.getByRole("button", { name: "Préparer les contacts marketing", exact: true }).click();
  for (const channel of ["Email", "SMS", "Push"]) {
    await editor.getByRole("combobox", { name: `Permission marketing ${channel}`, exact: true }).selectOption("granted");
    await editor.getByLabel(`Preuve de permission ${channel}`, { exact: true }).fill(`Explicit ${channel} marketing permission`);
    await editor.getByLabel(`Déclarer une destination ${channel}`, { exact: true }).check();
    await editor.getByLabel(`Destination ${channel}`, { exact: true }).fill(channel === "Email" ? "customer@EXAMPLE.COM" : channel === "SMS" ? "+41791234567" : `device-${info.project.name}`);
    await editor.getByLabel(`Preuve de destination ${channel}`, { exact: true }).fill(`Explicit ${channel} destination`);
  }
  await editor.getByLabel("Application Push", { exact: true }).fill("fixture-app");
  await editor.getByLabel("Motif des contacts", { exact: true }).fill("Explicit native three-channel contacts");
  for (const control of await editor.locator("button,input,select").all()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await editor.screenshot({ path: info.outputPath("native-contact-form.png") });
  let posts = 0, previews = 0, first: any;
  let markLost!: () => void; const lost = new Promise<void>(resolve => { markLost = resolve; });
  await page.route("**/contact-declarations/validate", async route => { previews++; await route.continue(); });
  await page.route("**/contact-declarations", async route => {
    if (route.request().method() !== "POST") return route.continue(); posts++;
    const result = await route.fetch(); expect(result.status()).toBe(200); const value = await result.json();
    if (posts === 1) { first = value; await route.abort("failed"); markLost(); return; }
    await route.fulfill({ response: result });
  });
  await editor.getByRole("button", { name: "Vérifier la déclaration de contacts", exact: true }).click();
  await expect(editor).toContainText("Déclaration vérifiée"); await expect(editor).toContainText("customer@example.com");
  expect(posts).toBe(0); expect(previews).toBe(1);
  const base = `${api}/marketing/institutes/${institute}/customers/${customer.id}/contact-declarations`;
  expect(await (await request.get(base + "/current", { headers })).json()).toBeNull();
  await editor.screenshot({ path: info.outputPath("native-contact-confirm.png") });
  await editor.getByRole("button", { name: "Conserver la déclaration vérifiée", exact: true }).click(); await lost;
  await expect(editor.getByRole("button", { name: "Reprendre les contacts conservés", exact: true })).toBeEnabled();
  await page.reload(); await select(); await editor.getByRole("button", { name: "Reprendre les contacts conservés", exact: true }).click();
  await expect(editor).toContainText("Contacts originaux vérifiés"); expect(posts).toBe(1); expect(previews).toBe(1);
  expect(first.declaration.communications.map((c: any) => c.channel)).toEqual(["email", "sms", "push"]);
  expect(first.declaration.communications[0].destination.email).toBe("customer@example.com");
  expect(first.declaration.communications[2].destination.push_token).toBe(`device-${info.project.name}`);
  expect(await page.evaluate(() => Object.keys(sessionStorage).some(k => k.startsWith("flowpilot.marketing-contact-request:")))).toBe(false);
  await editor.getByRole("button", { name: "Préparer les contacts marketing", exact: true }).click();
  await expect(editor.getByLabel("Destination Email", { exact: true })).toHaveValue("customer@example.com");
  await expect(editor.getByLabel("Destination Push", { exact: true })).toHaveValue(`device-${info.project.name}`);
  await editor.getByRole("combobox", { name: "Permission marketing Push", exact: true }).selectOption("refused");
  await editor.getByLabel("Preuve de permission Push", { exact: true }).fill("Explicit customer push withdrawal");
  await editor.getByLabel("Motif des contacts", { exact: true }).fill("Explicit native push withdrawal");
  await editor.getByRole("button", { name: "Vérifier la déclaration de contacts", exact: true }).click();
  await expect(editor).toContainText("Push : Refus déclaré"); expect(posts).toBe(1); expect(previews).toBe(2);
  await editor.getByRole("button", { name: "Conserver la déclaration vérifiée", exact: true }).click();
  await expect(editor).toContainText("Contacts originaux vérifiés"); expect(posts).toBe(2);
  const current = await (await request.get(base + "/current", { headers })).json();
  expect(current.previous_id).toBe(first.id); expect(current.declaration.communications[2].permission).toBe("refused");
  expect(current.declaration.communications[0]).toEqual(first.declaration.communications[0]);
  expect(await (await request.get(base + "/" + first.id, { headers })).json()).toEqual(first);
  await editor.screenshot({ path: info.outputPath("native-contact-withdrawal.png") });
});
