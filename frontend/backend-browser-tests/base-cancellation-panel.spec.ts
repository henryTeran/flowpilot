import { expect, test } from "@playwright/test";
test.setTimeout(120000);
test.use({ actionTimeout: 20000 });
test("signed human cancellation recovers each committed lost acknowledgement once", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1";
  const day = new Date(Date.now() + (info.project.name.includes("tablet") ? 12 : 11) * 86400000);
  day.setUTCHours(10, 0, 0, 0);
  const reply = await request.post(`${api}/appointments`, { headers, data: { institute_id: "demo-institute-geneve", employee_id: "emp-angela", service_id: "svc-soin-profond", customer_name: `BASE native ${info.project.name}`, start_time: day.toISOString(), idempotency_key: `base-native-${info.project.name}` } });
  expect(reply.status(), await reply.text()).toBe(200); const appointment = await reply.json();
  const posts: Record<string, number> = { operation: 0, decision: 0, execution: 0 };
  await page.route("**/base/**", async route => {
    const path = route.request().url();
    if (route.request().method() !== "POST" || path.includes("sensitive-previews")) return route.continue();
    const mode = path.endsWith("/sensitive-operations") ? "operation" : path.endsWith("/approvals") ? "decision" : "execution";
    posts[mode]++;
    const request = route.request().postDataJSON();
    expect(request.actor_id).toBeUndefined(); expect(request.approved).toBeUndefined();
    const saved = await page.evaluate(() => Object.keys(sessionStorage).filter(k => k.startsWith("flowpilot.base-cancellation.v1:")).map(k => JSON.parse(sessionStorage.getItem(k)!)));
    expect(saved.find(v => v.mode === mode)?.terms).toEqual(request);
    const response = await route.fetch(); expect(response.status(), await response.text()).toBe(200);
    await route.abort("connectionfailed");
  });
  const enter = async () => { await page.getByRole("button", { name: "RDV sous appel", exact: true }).click(); };
  await enter(); const panel = page.locator(".base-cancellation-panel");
  await expect(panel).toBeVisible();
  await page.getByLabel("Date de l’agenda", { exact: true }).fill(day.toISOString().slice(0, 10));
  await expect(panel.getByRole("combobox").locator(`option[value="${appointment.id}"]`)).toHaveCount(1);
  await panel.getByLabel("Rendez-vous à relire", { exact: true }).selectOption(appointment.id);
  await panel.getByRole("button", { name: "Relire avant préparation", exact: true }).click();
  await expect(panel.getByRole("heading", { name: "État relu", exact: true })).toBeVisible();
  await panel.getByLabel("Validité jusqu’au (UTC)", { exact: true }).fill(new Date(Date.now()+3600000).toISOString().slice(0,16));
  await panel.getByLabel("Motif de l’action", { exact: true }).fill("Préparation native explicitement examinée");
  await panel.getByRole("button", { name: "Conserver la préparation", exact: true }).click();
  const recover = async (mode: string, button: string) => {
    await expect(panel.getByRole("heading", { name: `Demande conservée — ${mode}`, exact: true })).toBeVisible();
    await page.reload(); await enter(); await panel.getByRole("button", { name: button, exact: true }).click();
    await expect(panel.getByRole("heading", { name: "Décisions relues", exact: true })).toBeVisible();
  };
  await recover("préparation", "Reprendre la préparation");
  await expect(panel).toContainText("en attente");
  await panel.locator("article").filter({ has: page.getByRole("heading", { name: "Préparation conservée", exact: true }) }).screenshot({ path: info.outputPath("base-native-prepared.png") });
  await panel.getByLabel("Motif de l’action", { exact: true }).fill("Approbation native explicitement confirmée");
  await panel.getByRole("button", { name: "Approuver cette préparation", exact: true }).click();
  await recover("décision", "Reprendre la décision"); await expect(panel).toContainText("approuvée");
  await panel.locator("article").filter({ has: page.getByRole("heading", { name: "Décisions relues", exact: true }) }).screenshot({ path: info.outputPath("base-native-approved.png") });
  await panel.getByLabel("Motif de l’action", { exact: true }).fill("Exécution native explicitement confirmée");
  await panel.getByRole("button", { name: "Exécuter l’annulation approuvée", exact: true }).click();
  await recover("exécution", "Reprendre l’exécution");
  await expect(panel.getByRole("heading", { name: "Annulation exécutée et preuve relue", exact: true })).toBeVisible();
  expect(posts).toEqual({ operation: 1, decision: 1, execution: 1 });
  expect(await page.evaluate(() => Object.keys(sessionStorage).filter(k => k.startsWith("flowpilot.base-cancellation.v1:")))).toHaveLength(0);
  const actual = await request.get(`${api}/appointments?institute_id=demo-institute-geneve&day=${day.toISOString().slice(0,10)}`, { headers });
  expect(actual.status()).toBe(200); expect((await actual.json()).find((v: any) => v.id === appointment.id)?.status).toBe("cancelled");
  for (const control of await panel.locator("button,input,select").all()) if (await control.isVisible()) expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)).toBe(false);
  await panel.locator("article").filter({ has: page.getByRole("heading", { name: "Annulation exécutée et preuve relue", exact: true }) }).screenshot({ path: info.outputPath("base-native-executed.png") });
});

test("signed native refusal, revocation and changed-source guards preserve appointments", async ({ page, request }, info) => {
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token"));
  const headers = { Authorization: `Bearer ${token}` }, api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
  let executions = 0;
  page.on("request", r => { if (r.method() === "POST" && r.url().endsWith("/executions")) executions++; });
  for (const scenario of ["decline", "revoke", "stale-approval", "stale-execution"]) {
    const index = ["decline", "revoke", "stale-approval", "stale-execution"].indexOf(scenario);
    const day = new Date(Date.now() + (20 + index + (info.project.name.includes("tablet") ? 5 : 0)) * 86400000); day.setUTCHours(10, 0, 0, 0);
    const created = await request.post(`${api}/appointments`, { headers, data: { institute_id: institute, employee_id: "emp-angela", service_id: "svc-soin-profond", customer_name: `BASE stop ${scenario} ${info.project.name}`, start_time: day.toISOString(), idempotency_key: `base-stop-${scenario}-${info.project.name}` } });
    expect(created.status(), await created.text()).toBe(200); const appointment = await created.json();
    await page.getByRole("button", { name: "RDV sous appel", exact: true }).click();
    const panel = page.locator(".base-cancellation-panel");
    await page.getByLabel("Date de l’agenda", { exact: true }).fill(day.toISOString().slice(0,10));
    await expect(panel.getByRole("combobox").locator(`option[value="${appointment.id}"]`)).toHaveCount(1);
    await panel.getByLabel("Rendez-vous à relire", { exact: true }).selectOption(appointment.id);
    await panel.getByRole("button", { name: "Relire avant préparation", exact: true }).click();
    await expect(panel.getByRole("heading", { name: "État relu", exact: true })).toBeVisible();
    await panel.getByLabel("Validité jusqu’au (UTC)", { exact: true }).fill(new Date(Date.now()+3600000).toISOString().slice(0,16));
    await panel.getByLabel("Motif de l’action", { exact: true }).fill(`Préparation arrêt ${scenario}`);
    await panel.getByRole("button", { name: "Conserver la préparation", exact: true }).click();
    await expect(panel.getByRole("heading", { name: "Décisions relues", exact: true })).toBeVisible();
    const operation = await panel.getByLabel("Référence de préparation", { exact: true }).inputValue();
    if (scenario === "revoke" || scenario === "stale-execution") {
      await panel.getByLabel("Motif de l’action", { exact: true }).fill("Approbation examinée avant arrêt");
      await panel.getByRole("button", { name: "Approuver cette préparation", exact: true }).click();
      await expect(panel).toContainText("État : approuvée");
    }
    if (scenario.startsWith("stale")) {
      const changed = await request.patch(`${api}/appointments/${appointment.id}`, { headers, data: { notes: "Peer source revision in owned test fixture" } }); expect(changed.status()).toBe(200);
      await panel.getByLabel("Motif de l’action", { exact: true }).fill("Tentative après modification de source");
      const failed = page.waitForResponse(r => r.request().method() === "POST" && r.url().endsWith(scenario === "stale-approval" ? "/approvals" : "/executions"));
      await panel.getByRole("button", { name: scenario === "stale-approval" ? "Approuver cette préparation" : "Exécuter l’annulation approuvée", exact: true }).click();
      expect((await failed).status()).toBe(400);
      await expect(panel.getByRole("heading", { name: `Demande conservée — ${scenario === "stale-approval" ? "décision" : "exécution"}`, exact: true })).toBeVisible();
      await panel.getByRole("button", { name: "Vérifier le rejet et corriger", exact: true }).click();
      await expect(panel.getByRole("heading", { name: /Demande conservée/ })).toHaveCount(0);
      await panel.getByRole("button", { name: "Relire préparation et décisions", exact: true }).click();
      await expect(panel.getByRole("heading", { name: "Décisions relues", exact: true })).toBeVisible();
    }
    const revoke = scenario === "revoke" || scenario === "stale-execution";
    await panel.getByLabel("Motif de l’action", { exact: true }).fill("Arrêt explicite sans annulation");
    await panel.getByRole("button", { name: revoke ? "Révoquer l’approbation" : "Refuser cette préparation", exact: true }).click();
    await expect(panel).toContainText(revoke ? "État : révoquée" : "État : refusée");
    await expect(panel.getByRole("button", { name: "Exécuter l’annulation approuvée", exact: true })).toHaveCount(0);
    const receipt = await request.get(`${api}/base/institutes/${institute}/sensitive-operations/${operation}/execution`, { headers }); expect(receipt.status()).toBe(200); expect(await receipt.json()).toBeNull();
    const actual = await request.get(`${api}/appointments?institute_id=${institute}&day=${day.toISOString().slice(0,10)}`, { headers }); expect((await actual.json()).find((a: any) => a.id === appointment.id)?.status).toBe("scheduled");
    await panel.locator("article").filter({ has: page.getByRole("heading", { name: "Décisions relues", exact: true }) }).screenshot({ path: info.outputPath(`base-stop-${scenario}.png`) });
    await page.reload(); await expect(page.locator(".flow-session-exit")).toBeVisible();
  }
  expect(executions).toBe(1); // The only execution request was rejected by fresh source validation.
});
