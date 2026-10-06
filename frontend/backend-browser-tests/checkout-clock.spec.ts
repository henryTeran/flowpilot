import { expect, test } from "@playwright/test";

test.use({ timezoneId: "America/Los_Angeles" });

test("native cashier displays institute hours on a workstation in another timezone", async ({ page, request }, info) => {
  test.setTimeout(60000);
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  expect(await page.evaluate(() => Intl.DateTimeFormat().resolvedOptions().timeZone)).toBe("America/Los_Angeles");
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  expect((await request.put(`${api}/gift-cards/institutes/${institute}/settings`, { headers, data: { currency: "CHF" } })).status()).toBe(200);
  const created = await request.post(`${api}/tickets`, { headers, data: { institute_id: institute, service_id: "svc-aisselles" } });
  expect(created.status()).toBe(200); const ticket = await created.json();
  expect(ticket.arrival_time).toMatch(/(?:Z|[+-]\d{2}:\d{2})$/);
  const started = await request.post(`${api}/planning/sessions/start`, { headers, data: { ticket_id: ticket.id, employee_id: "emp-angela", service_id: "svc-aisselles" } });
  expect(started.status()).toBe(200); const session = await started.json();
  expect((await request.patch(`${api}/planning/sessions/${session.id}/finish`, { headers })).status()).toBe(200);
  // Fixture API completion precedes the websocket/REST UI update. Wait for the
  // same operational snapshot before invoking the ticket's checkout action.
  await expect(page.locator(`.session-block[data-session-id="${session.id}"]`)).toHaveAttribute("data-session-meta", /Terminée/);
  await page.getByRole("button", { name: "Je m’identifie", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: /Angela/ }).click();
  await page.getByRole("button", { name: "Flux tickets", exact: true }).click();
  await page.locator(".bm-ticket-row-clone").filter({ hasText: ticket.ticket_number }).getByRole("button", { name: "Encaisser / Modifier" }).click();
  const checkout = page.locator(".bm-checkout-clone");
  const expected = new Date(ticket.arrival_time).toLocaleTimeString("fr-CH", { timeZone: "Europe/Zurich", hour: "2-digit", minute: "2-digit" });
  await expect(checkout.getByText("Heures : Europe/Zurich", { exact: true })).toBeVisible();
  await expect(checkout.locator(".bm-customer-meta-grid span").filter({ hasText: "Arrivee" })).toContainText(expected);
  await expect(checkout.locator(".bm-cash-audit-block").filter({ hasText: "Créé par" })).toContainText(expected);
  await page.screenshot({ path: info.outputPath("cashier-institute-clock.png"), fullPage: true });
  await checkout.getByRole("button", { name: "esp.", exact: true }).click();
  const paid = page.waitForResponse(response => response.url().endsWith(`/tickets/${ticket.id}/checkout/pay`));
  await checkout.getByRole("button", { name: "Enregistrer le paiement", exact: true }).click();
  const reply = await paid; expect(reply.status()).toBe(200);
  const receipt = await reply.json();
  expect(receipt.paid_at).toMatch(/(?:Z|[+-]\d{2}:\d{2})$/);
  expect(receipt.checkout_started_at).toMatch(/(?:Z|[+-]\d{2}:\d{2})$/);
  const events = await (await request.get(`${api}/tickets/${ticket.id}/events`, { headers })).json();
  expect(events.length).toBeGreaterThan(0);
  for (const row of events) expect(row.occurred_at).toMatch(/(?:Z|[+-]\d{2}:\d{2})$/);
});
