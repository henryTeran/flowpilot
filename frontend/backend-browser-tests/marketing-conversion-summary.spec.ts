import { expect, test } from "@playwright/test";

test("native conversion summary uses institute dates refuses corrupt reports and retries", async ({ page, request }, info) => {
  test.setTimeout(120000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1";
  const institute = "demo-institute-geneve", prefix = info.project.name, base = `${api}/marketing/institutes/${institute}`;
  const customerReply = await request.post(`${api}/customers/institutes/${institute}`, { headers, data: { display_name: `SEND ${prefix}`, idempotency_key: `send-customer-${prefix}` } });
  expect(customerReply.status()).toBe(200); const customer = await customerReply.json();
  const policies = `${api}/crm/institutes/${institute}/segment-policies`;
  const previous = await (await request.get(policies + "/current", { headers })).json();
  const policy = await request.post(policies, { headers, data: { policy: { institute_id: institute, observation_us: 1209600000000, new_customer_us: 86400000000,
    at_risk_us: 172800000000, dormant_us: 604800000000, loyal_min_tickets: 2, vip_min_tickets: 3, vip_currency: "CHF", vip_gross_minor: "300" },
    previous_policy_id: previous?.id || null, reason: "Explicit SEND segments", idempotency_key: `send-policy-${prefix}` } }); expect(policy.status()).toBe(200);
  const communications = ["email", "sms"].flatMap(channel => ["service_follow_up", "marketing"].map(purpose => ({ channel, purpose,
    permission: channel === "email" && purpose === "marketing" ? "granted" : "unknown", evidence: channel === "email" && purpose === "marketing" ? "Explicit SEND fixture" : null })));
  const declared = await request.post(`${api}/crm/institutes/${institute}/customers/${customer.id}/lifecycle-declarations`, { headers, data: {
    declaration: { institute_id: institute, customer_id: customer.id, birthday: null, birthday_evidence: null, communications }, previous_id: null,
    reason: "Explicit SEND permission", idempotency_key: `send-permission-${prefix}` } }); expect(declared.status()).toBe(200);
  const captureReply = await request.post(base + "/audience-captures", { headers, data: { segments: ["NEW"], channel: "email", reason: "SEND retained source", idempotency_key: `send-audience-${prefix}` } });
  expect(captureReply.status()).toBe(200); const capture = await captureReply.json(), subject = `SEND subject ${prefix}`;
  let original: any;
  for (const action of ["create", "review", "approve"]) {
    const response = await request.post(base + "/campaigns", { headers, data: { action, campaign_id: original?.revision.campaign_id || null,
      expected_revision_id: original?.revision.id || null,
      content: action === "create" ? { channel: "email", origin: "ai", subject, body: "Explicit approved literal SEND content", audience_id: capture.id, template_original_id: null } : null,
      reason: `Explicit ${action} fixture`, idempotency_key: `send-${action}-${prefix}` } });
    expect(response.status()).toBe(200); original = await response.json();
  }
  await page.getByRole("button", { name: "Marketing", exact: true }).click();
  const marketing = page.getByRole("region", { name: "Marketing", exact: true });
  const selected = page.getByRole("button", { name: `${subject} \u00b7 Approuv\u00e9e \u00b7 email`, exact: true });
  const catalog = await (await request.get(base + "/campaigns?limit=1", { headers })).json();
  for (let offset = 0; offset < catalog.total; offset += 20) {
    await expect(marketing).toContainText(`${offset + 1}\u2013${Math.min(offset + 20, catalog.total)} sur ${catalog.total} campagnes`);
    if (await selected.count()) break;
    await marketing.getByRole("button", { name: "Campagnes suivantes", exact: true }).click();
  }
  await selected.click();
  const report = page.getByRole("region", { name: "Synth\u00e8se des conversions", exact: true });
  await expect(report).toBeVisible();
  const button = report.getByRole("button", { name: "Lire la synth\u00e8se des conversions", exact: true });
  let reads = 0, corrupt = true;
  await page.route("**/conversions/summary?**", async route => {
    reads++;
    const url = new URL(route.request().url());
    expect(url.searchParams.get("start")).toBe("2020-01-01T23:00:00.000Z");
    expect(url.searchParams.get("end")).toBe("2020-01-02T23:00:00.000Z");
    const response = await route.fetch(), body = await response.json();
    expect(response.status()).toBe(200);
    if (corrupt) body.full_retained_current_cohort = 1;
    await route.fulfill({ response, json: body });
  });
  expect(reads).toBe(0);
  await report.getByLabel("Date de d\u00e9but").fill("2020-01-02");
  await report.getByLabel("Date de fin exclue").fill("2020-01-03");
  await button.click(); await expect(report.getByRole("alert")).toBeVisible();
  await expect(report).not.toContainText("0 tickets li\u00e9s courants");
  corrupt = false; await button.click();
  await expect(report).toContainText("0 tickets li\u00e9s courants");
  expect(reads).toBe(2);
  await report.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("native-conversion-summary.png") });
});
