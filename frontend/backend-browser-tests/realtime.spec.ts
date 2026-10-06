import { expect, test, type Page } from "@playwright/test";

async function openTickets(page: Page) {
  await page.goto("http://127.0.0.1:4199/");
  await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.getByText("Temps réel actif", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Flux tickets", exact: true }).click();
}
async function arrive(page: Page) {
  await page.getByRole("button", { name: /Créer un nouveau ticket/ }).click();
  const dialog = page.getByRole("dialog", { name: "Nouveau Ticket" });
  await dialog.getByRole("button", { name: "Épilation", exact: true }).click();
  await dialog.getByRole("button", { name: /^Aisselles/ }).click();
  const reply = page.waitForResponse(response => response.url().endsWith("/api/v1/tickets") && response.request().method() === "POST");
  await dialog.getByRole("button", { name: "Ajouter à la file", exact: true }).click();
  const response = await reply;
  expect(response.status()).toBe(200);
  const ticket = await response.json();
  await expect(dialog).toHaveCount(0);
  return ticket.ticket_number as string;
}

test("second signed page receives real websocket changes and recovers missed arrivals after reconnect", async ({ page, browser }, info) => {
  test.setTimeout(60000);
  const context = await browser.newContext({ viewport: page.viewportSize()!, hasTouch: Boolean(info.project.use.hasTouch), timezoneId: "Europe/Zurich" });
  try {
    const observer = await context.newPage();
    // Track native sockets solely to close the live connection deterministically.
    // All handshakes and frames still use the real browser/network/backend.
    await observer.addInitScript(() => {
      const NativeSocket = window.WebSocket;
      const sockets: WebSocket[] = [];
      Object.assign(window, { flowpilotTestSockets: sockets });
      window.WebSocket = class extends NativeSocket {
        constructor(...args: ConstructorParameters<typeof WebSocket>) { super(...args); sockets.push(this); }
      };
    });
    let changes = 0, connections = 0;
    observer.on("websocket", socket => {
      connections++;
      socket.on("framereceived", frame => {
        try { if (JSON.parse(String(frame.payload)).event === "planning.changed") changes++; } catch { /* Non-JSON heartbeat is irrelevant. */ }
      });
    });
    await openTickets(page);
    await openTickets(observer);
    const before = changes;
    const first = await arrive(page);
    await expect.poll(() => changes).toBeGreaterThan(before);
    await expect(observer.locator(".bm-ticket-row-clone").filter({ hasText: first })).toBeVisible();

    await context.setOffline(true);
    await observer.evaluate(() => {
      const sockets = (window as unknown as { flowpilotTestSockets: WebSocket[] }).flowpilotTestSockets;
      sockets.forEach(socket => socket.close());
    });
    await expect(observer.getByText("Hors ligne", { exact: true })).toBeVisible();
    const missed = await arrive(page);
    await expect(observer.locator(".bm-ticket-row-clone").filter({ hasText: missed })).toHaveCount(0);
    const connectionCount = connections;
    await context.setOffline(false);
    await expect(observer.getByText("Temps réel actif", { exact: true })).toBeVisible({ timeout: 15000 });
    await expect.poll(() => connections).toBeGreaterThan(connectionCount);
    await expect(observer.locator(".bm-ticket-row-clone").filter({ hasText: missed })).toBeVisible();
  } finally { await context.close(); }
});
