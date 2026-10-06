import { expect, test } from "@playwright/test";

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
  const first = await firstResponse.json();
  expect(first.employee_id).toBe("emp-angela");
  const firstCard = panel.locator(".appointment-card").filter({ hasText: firstName });
  await expect(firstCard).toBeVisible();
  await expect(firstCard).toContainText(selectedTime);
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
