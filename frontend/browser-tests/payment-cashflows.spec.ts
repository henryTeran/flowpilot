import { expect, test, type Page } from "@playwright/test";

async function setup(page: Page, role: string) {
  const token = `h.${Buffer.from(JSON.stringify({ sub: "browser-test", role })).toString("base64url")}.s`;
  await page.addInitScript(value => sessionStorage.setItem("flowpilot.access_token", value), token);
  const reads: string[] = [];
  let invalid = false;
  await page.route("http://localhost:8001/api/v1/**", async route => {
    const request = route.request();
    expect(request.method()).toBe("GET");
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    reads.push(path);
    let body: unknown = [];
    if (path === "/institutes") body = [{ id: "inst", name: "Browser institute", city: "Test", timezone: "Europe/Berlin", status: "active" }];
    if (path.endsWith("/today")) body = { institute_id: "inst", rows: [] };
    if (path.endsWith("/availability")) body = { institute_id: "inst", employees: [] };
    if (path === "/tickets/chiffres") body = { institute_id: "inst", currency: "CHF", currency_groups: [], rows: [], unknown_currency_tickets: 0 };
    if (path.endsWith("/cashflows")) body = { institute_id: invalid ? "foreign" : "inst", accounts: [
      { provider: "Test provider", account_id: "CHF account", currency: "CHF", captured: "10.35", applied: "10.35", unapplied: "0.00", refunded: "3.00", refund_reserved: "2.00", net_confirmed: "7.35" },
      { provider: "Test provider", account_id: "EUR account", currency: "EUR", captured: "90071992547409.93", applied: "90071992547409.93", unapplied: "0.00", refunded: "0.00", refund_reserved: "0.00", net_confirmed: "90071992547409.93" },
    ] };
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Pilotage", exact: true }).click();
  return { reads, invalidate: () => { invalid = true; } };
}

test("manager reads separate exact cashflows and hides facts after invalid refresh", async ({ page }, info) => {
  const errors: Error[] = [];
  page.on("pageerror", error => errors.push(error));
  const fixture = await setup(page, "responsable_institut");
  const panel = page.getByRole("region", { name: "Flux des paiements prestataire" });
  await expect(panel.getByRole("heading", { level: 4 })).toHaveCount(2);
  await expect(panel.getByText("90071992547409,93 EUR", { exact: true })).toHaveCount(3);
  await expect(panel.getByText("7,35 CHF", { exact: true })).toBeVisible();
  await panel.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("cashflows.png"), fullPage: true });
  fixture.invalidate();
  await panel.getByRole("button", { name: "Actualiser les flux" }).click();
  await expect(panel.getByRole("alert")).toBeVisible();
  await expect(panel.locator("dl")).toHaveCount(0);
  await expect(panel.getByRole("button", { name: "Actualiser les flux" })).toBeEnabled();
  expect(errors).toEqual([]);
});

test("cashier does not request or expose manager cashflows", async ({ page }) => {
  const fixture = await setup(page, "accueil");
  await expect(page.getByRole("heading", { name: "Chiffres", exact: true, level: 2 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Flux des paiements prestataire" })).toHaveCount(0);
  expect(fixture.reads.some(path => path.endsWith("/cashflows"))).toBe(false);
});
