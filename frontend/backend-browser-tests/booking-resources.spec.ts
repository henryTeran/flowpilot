import { expect, test } from "@playwright/test";

test.use({ timezoneId: "America/Los_Angeles" });
function instituteSlot(value: string) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Zurich", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(value)).map(part => [part.type, part.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
}

test("booking resource conflict survives different staff and cancellation releases the slot", async ({ page }, info) => {
  test.setTimeout(60000);
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  await page.getByRole("button", { name: "RDV sous appel", exact: true }).click();
  const panel = page.locator(".appointment-panel");
  await panel.getByRole("combobox", { name: "Prestation", exact: true }).selectOption("svc-soin-profond");
  await panel.getByRole("combobox", { name: "Collaboratrice", exact: true }).selectOption("emp-angela");
  const selectedTime = await panel.getByLabel("Heure", { exact: true }).inputValue();
  const firstName = `Room first ${info.project.name}`, secondName = `Room second ${info.project.name}`;
  await panel.getByLabel("Cliente", { exact: true }).fill(firstName);
  const create = () => page.waitForResponse(response => response.url().endsWith("/api/v1/appointments") && response.request().method() === "POST");
  const firstReply = create();
  await panel.getByRole("button", { name: "Créer RDV", exact: true }).click();
  const firstResponse = await firstReply;
  expect(firstResponse.status()).toBe(200);
  let first = await firstResponse.json();
  expect(instituteSlot(first.start_time).time).toBe(selectedTime);
  expect(await panel.getByLabel("Date", { exact: true }).inputValue()).toBe(instituteSlot(first.start_time).date);
  expect(first.employee_id).toBe("emp-angela");
  const firstCard = panel.locator(".appointment-card").filter({ hasText: firstName });
  await expect(firstCard).toBeVisible();
  await expect(firstCard).toContainText(selectedTime);
  await firstCard.getByRole("button", { name: "Modifier", exact: true }).click();
  expect(await panel.getByLabel("Heure", { exact: true }).inputValue()).toBe(selectedTime);
  const movedSlot = instituteSlot(new Date(Date.parse(first.start_time) + 15 * 60000).toISOString());
  await panel.getByLabel("Date", { exact: true }).fill(movedSlot.date);
  await panel.getByLabel("Heure", { exact: true }).fill(movedSlot.time);
  const movement = page.waitForResponse(response => response.url().endsWith(`/appointments/${first.id}`) && response.request().method() === "PATCH");
  await panel.getByRole("button", { name: "Enregistrer les modifications", exact: true }).click();
  const movedResponse = await movement;
  expect(movedResponse.status()).toBe(200);
  const moved = await movedResponse.json();
  expect(Date.parse(moved.start_time) - Date.parse(first.start_time)).toBe(15 * 60000);
  expect(instituteSlot(moved.start_time)).toEqual(movedSlot);
  first = moved;
  await expect(firstCard).toContainText(movedSlot.time);
  await expect(page.locator(".planning-zone")).toContainText("Europe/Zurich");
  const confirmation = page.waitForResponse(response => response.url().endsWith(`/appointments/${first.id}/confirm`));
  await firstCard.getByRole("button", { name: "Confirmer", exact: true }).click();
  expect((await confirmation).status()).toBe(200);

  await panel.getByRole("combobox", { name: "Collaboratrice", exact: true }).selectOption("emp-assya");
  await panel.getByLabel("Cliente", { exact: true }).fill(secondName);
  const rejected = create();
  await panel.getByRole("button", { name: "Créer RDV", exact: true }).click();
  const conflict = await rejected;
  expect(conflict.status()).toBe(400);
  expect(JSON.stringify(await conflict.json())).toMatch(/ressources/);
  await expect(panel.getByRole("alert")).toContainText("ressources");
  await expect(panel.locator(".appointment-card").filter({ hasText: secondName })).toHaveCount(0);

  const cancellation = page.waitForResponse(response => response.url().endsWith(`/appointments/${first.id}/cancel`));
  await firstCard.getByRole("button", { name: "Annuler", exact: true }).click();
  expect((await cancellation).status()).toBe(200);
  // Retry the still-pending original form/key after the real reservation release.
  const retried = create();
  await panel.getByRole("button", { name: "Créer RDV", exact: true }).click();
  const accepted = await retried;
  expect(accepted.status()).toBe(200);
  const second = await accepted.json();
  expect(second.employee_id).toBe("emp-assya");
  expect(second.start_time).toBe(first.start_time);
  const secondCard = panel.locator(".appointment-card").filter({ hasText: secondName });
  await expect(secondCard).toBeVisible();
  const cleanup = page.waitForResponse(response => response.url().endsWith(`/appointments/${second.id}/cancel`));
  await secondCard.getByRole("button", { name: "Annuler", exact: true }).click();
  expect((await cleanup).status()).toBe(200);
});


test("a repeated institute hour requires a choice and records two distinct actual instants", async ({ page, request }, info) => {
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  await page.getByRole("button", { name: "RDV sous appel", exact: true }).click();
  const panel = page.locator(".appointment-panel");
  await panel.getByRole("combobox", { name: "Prestation", exact: true }).selectOption("svc-aisselles");
  await panel.getByRole("combobox", { name: "Collaboratrice", exact: true }).selectOption("emp-angela");
  let year = new Date().getUTCFullYear();
  const octoberSunday = () => {
    const last = new Date(Date.UTC(year, 9, 31));
    return new Date(last.getTime() - last.getUTCDay() * 86400000).toISOString().slice(0, 10);
  };
  if (Date.parse(`${octoberSunday()}T00:30:00Z`) <= Date.now() + 86400000) year++;
  const day = octoberSunday();
  await panel.getByLabel("Date", { exact: true }).fill(day);
  await panel.getByLabel("Heure", { exact: true }).fill("02:30");
  await panel.getByLabel("Cliente", { exact: true }).fill(`Fold first ${info.project.name}`);
  let posts = 0;
  page.on("request", req => { if (req.url().endsWith("/api/v1/appointments") && req.method() === "POST") posts++; });
  await panel.getByRole("button", { name: "Créer RDV", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("occurrence");
  expect(posts).toBe(0);
  const occurrence = panel.getByRole("combobox", { name: "Occurrence de l’heure" });
  await occurrence.selectOption(`${day}T00:30:00.000Z`);
  expect(await occurrence.boundingBox()).not.toBeNull();
  expect((await occurrence.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await page.screenshot({ path: info.outputPath("institute-hour-occurrence.png"), fullPage: true });
  const save = async () => {
    const reply = page.waitForResponse(response => response.url().endsWith("/api/v1/appointments") && response.request().method() === "POST");
    await panel.getByRole("button", { name: "Créer RDV", exact: true }).click();
    const response = await reply;
    expect(response.status(), await response.text()).toBe(200);
    return response.json();
  };
  const first = await save();
  await expect(panel.getByLabel("Cliente", { exact: true })).toHaveValue("");
  await panel.getByLabel("Cliente", { exact: true }).fill(`Fold second ${info.project.name}`);
  await occurrence.selectOption(`${day}T01:30:00.000Z`);
  const second = await save();
  expect(Date.parse(second.start_time) - Date.parse(first.start_time)).toBe(3600000);
  expect(instituteSlot(first.start_time)).toEqual({ date: day, time: "02:30" });
  expect(instituteSlot(second.start_time)).toEqual({ date: day, time: "02:30" });
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` };
  const rows = await request.get(`http://127.0.0.1:4198/api/v1/appointments?institute_id=demo-institute-geneve&day=${day}`, { headers });
  expect(rows.status()).toBe(200);
  const recorded = await rows.json();
  await expect(panel.getByLabel("Date de l’agenda", { exact: true })).toHaveValue(day);
  const operationalDay = await page.locator(".planning-zone").textContent();
  const otherDay = new Date(Date.parse(`${day}T12:00:00Z`) + 86400000).toISOString().slice(0, 10);
  await panel.getByLabel("Date de l’agenda", { exact: true }).fill(otherDay);
  await expect(panel.locator(".appointment-card").filter({ hasText: first.customer_name })).toHaveCount(0);
  await panel.getByLabel("Date de l’agenda", { exact: true }).fill(day);
  await expect(panel.locator(".appointment-card").filter({ hasText: first.customer_name })).toBeVisible();
  expect(await page.locator(".planning-zone").textContent()).toBe(operationalDay);
  expect((await panel.getByLabel("Date de l’agenda", { exact: true }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await page.screenshot({ path: info.outputPath("selected-day-agenda.png"), fullPage: true });
  for (const booking of [first, second]) {
    expect(recorded.find((row: any) => row.id === booking.id).start_time).toBe(booking.start_time);
    const card = panel.locator(".appointment-card").filter({ hasText: booking.customer_name });
    await expect(card).toContainText("02:30");
    await expect(card).toContainText(booking.id === first.id ? "UTC+2" : "UTC+1");
    const cancelled = page.waitForResponse(response => response.url().endsWith(`/appointments/${booking.id}/cancel`));
    await card.getByRole("button", { name: "Annuler", exact: true }).click();
    expect((await cancelled).status()).toBe(200);
    await expect(panel.locator(".appointment-list.history").filter({ hasText: booking.customer_name })).toBeVisible();
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
});
