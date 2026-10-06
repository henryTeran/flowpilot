import { expect, test, type Page, type Locator } from "@playwright/test";

const cents = (amount: string) => BigInt(amount.replace(".", ""));

async function finishPreparation(page: Page, history: Locator, ticketId: string) {
  const recovery = history.getByRole("button", { name: "Reprendre cette opération", exact: true });
  const retained = history.getByRole("alert").filter({ hasText: "Reprenez la demande conservée" });
  await expect(recovery.or(retained)).toBeVisible();
  if (await retained.isVisible()) {
    // A real-time refresh can supersede the operation refresh. The saved request
    // stays latched until its original terms have been read and refreshed again.
    const replay = page.waitForResponse(response => response.url().endsWith(`/tickets/${ticketId}/intents`) && response.request().method() === "POST");
    await history.getByRole("button", { name: "Reprendre la demande conservée", exact: true }).click();
    expect((await replay).status()).toBe(200);
  }
  await expect(recovery).toBeVisible();
}

async function openCheckout(page: Page, number: string) {
  await page.getByRole("button", { name: "Flux tickets", exact: true }).click();
  const row = page.locator(".bm-ticket-row-clone").filter({ hasText: number });
  await expect(row).toContainText("En caisse", { timeout: 15000 });
  await row.getByRole("button", { name: "Encaisser / Modifier" }).click();
  await page.getByRole("dialog").getByRole("button", { name: /Angela/ }).click();
  await expect(page.locator(".bm-checkout-clone")).toBeVisible();
}

test("lost simulator authorization reply is recovered with the original durable operation after reload", async ({ page, request }, info) => {
  test.setTimeout(60000);
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, base = "http://127.0.0.1:4198/api/v1";
  const ledgerBefore = await (await request.get(`${base}/payments/institutes/demo-institute-geneve/cashflows`, { headers })).json();
  expect((await request.put(`${base}/gift-cards/institutes/demo-institute-geneve/settings`, { headers, data: { currency: "CHF" } })).status()).toBe(200);
  const created = await request.post(`${base}/tickets`, { headers, data: { institute_id: "demo-institute-geneve", service_id: "svc-aisselles", created_by_id: "emp-angela", idempotency_key: `payment-fixture-${info.project.name}` } });
  expect(created.status()).toBe(200);
  const ticket = await created.json();
  const started = await request.post(`${base}/planning/sessions/start`, { headers, data: { ticket_id: ticket.id, employee_id: "emp-angela", service_id: "svc-aisselles" } });
  expect(started.status()).toBe(200);
  expect((await request.patch(`${base}/planning/sessions/${(await started.json()).id}/finish`, { headers })).status()).toBe(200);
  await openCheckout(page, ticket.ticket_number);
  const history = page.getByRole("region", { name: "Historique des paiements" });
  const preparation = page.waitForResponse(response => response.url().endsWith(`/tickets/${ticket.id}/intents`) && response.request().method() === "POST");
  await history.getByRole("button", { name: "Préparer l'autorisation", exact: true }).click();
  expect((await preparation).status()).toBe(200);
  await finishPreparation(page, history, ticket.id);
  const path = `${base}/payments/institutes/demo-institute-geneve/tickets/${ticket.id}/snapshot`;
  const prepared = await (await request.get(path, { headers })).json();
  expect(prepared.operations).toHaveLength(1);
  const original = prepared.operations[0];
  const dispatch = page.waitForResponse(response => response.url().endsWith(`/intents/${original.id}/dispatch`));
  await history.getByRole("button", { name: "Reprendre cette opération", exact: true }).click();
  const uncertain = await dispatch;
  expect(uncertain.status()).toBe(503);
  expect(await uncertain.text()).not.toContain("SIMULATOR PRIVATE");
  const unknown = await (await request.get(path, { headers })).json();
  expect(unknown.protected).toBe(true);
  expect(unknown.operations[0].status).toBe("unknown");
  await page.reload();
  await openCheckout(page, ticket.ticket_number);
  await expect(history).toContainText("Résultat à récupérer");
  const retry = page.waitForResponse(response => response.url().endsWith(`/intents/${original.id}/dispatch`));
  await history.getByRole("button", { name: "Reprendre cette opération", exact: true }).click();
  expect((await retry).status()).toBe(200);
  await expect(history.getByRole("button", { name: "Préparer l'encaissement", exact: true })).toBeVisible();
  const recovered = await (await request.get(path, { headers })).json();
  expect(recovered.operations).toHaveLength(1);
  expect(recovered.operations[0].id).toBe(original.id);
  expect(recovered.operations[0].idempotency_key).toBe(original.idempotency_key);
  expect(recovered.operations[0].status).toBe("authorized");
  expect(recovered.operations[0].amount).toBe(original.amount);
  const capturePreparation = page.waitForResponse(response => response.url().endsWith(`/tickets/${ticket.id}/intents`) && response.request().method() === "POST");
  await history.getByRole("button", { name: "Préparer l'encaissement", exact: true }).click();
  expect((await capturePreparation).status()).toBe(200);
  await finishPreparation(page, history, ticket.id);
  const capture = (await (await request.get(path, { headers })).json()).operations.find((row: { kind: string }) => row.kind === "capture");
  expect(capture).toBeDefined();
  const captureDispatch = page.waitForResponse(response => response.url().endsWith(`/intents/${capture.id}/dispatch`));
  await history.getByRole("button", { name: "Reprendre cette opération", exact: true }).click();
  expect((await captureDispatch).status()).toBe(200);
  await page.locator(".bm-checkout-clone").getByRole("button", { name: "CB", exact: true }).click();
  const checkout = page.waitForResponse(response => response.url().endsWith(`/intents/${capture.id}/checkout`));
  await history.getByRole("button", { name: "Appliquer l'encaissement en caisse", exact: true }).click();
  const applied = await checkout;
  expect(applied.status()).toBe(200);
  expect((await applied.json()).status).toBe("paid");
  const final = await (await request.get(path, { headers })).json();
  expect(final.protected).toBe(false);
  expect(final.operations).toHaveLength(2);
  expect(final.operations.find((row: { id: string }) => row.id === capture.id)).toMatchObject({ status: "captured", applied: true, amount: original.amount });
  const ledger = await (await request.get(`${base}/payments/institutes/demo-institute-geneve/cashflows`, { headers })).json();
  expect(ledger.accounts).toHaveLength(1);
  expect(ledger.accounts[0]).toMatchObject({ provider: "browser-simulator", account_id: "browser-test-account", currency: "CHF", unapplied: "0.00", refunded: "0.00" });
  for (const field of ["captured", "applied"]) {
    expect(cents(ledger.accounts[0][field]) - cents(ledgerBefore.accounts[0]?.[field] || "0.00")).toBe(cents(original.amount));
  }
});
