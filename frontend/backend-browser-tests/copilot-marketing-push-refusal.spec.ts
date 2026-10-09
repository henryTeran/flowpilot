import { expect, test } from "@playwright/test";
test("unsupported push audience blocks Copilot preparation without campaign creation", async ({ page, request }, info) => {
  test.setTimeout(120000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token")), headers = { Authorization: `Bearer ${token}` };
  const api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve", prefix = `push-${info.project.name}`;
  const customerReply = await request.post(`${api}/customers/institutes/${institute}`, { headers, data: { display_name: `Campaign ${prefix}`, idempotency_key: `campaign-client-${prefix}` } });
  expect(customerReply.status()).toBe(200); const customer = await customerReply.json();
  const policies = `${api}/crm/institutes/${institute}/segment-policies`, before = await request.get(policies + "/current", { headers }), previous = await before.json();
  const policy = await request.post(policies, { headers, data: { policy: { institute_id: institute, observation_us: 1209600000000, new_customer_us: 86400000000,
    at_risk_us: 172800000000, dormant_us: 604800000000, loyal_min_tickets: 2, vip_min_tickets: 3, vip_currency: "CHF", vip_gross_minor: "300" },
    previous_policy_id: previous?.id || null, reason: "Explicit campaign source segments", idempotency_key: `campaign-policy-${prefix}` } }); expect(policy.status()).toBe(200);
  const communications = ["email", "sms"].flatMap(channel => ["service_follow_up", "marketing"].map(purpose => ({ channel, purpose,
    permission: channel === "sms" && purpose === "marketing" ? "granted" : "unknown", evidence: channel === "sms" && purpose === "marketing" ? "Explicit campaign fixture permission" : null })));
  const declared = await request.post(`${api}/crm/institutes/${institute}/customers/${customer.id}/lifecycle-declarations`, { headers, data: {
    declaration: { institute_id: institute, customer_id: customer.id, birthday: null, birthday_evidence: null, communications }, previous_id: null,
    reason: "Explicit campaign permission", idempotency_key: `campaign-permission-${prefix}` } }); expect(declared.status()).toBe(200);
  const base = `${api}/marketing/institutes/${institute}`;
  const captureReply = await request.post(base + "/audience-captures", { headers, data: { segments: ["NEW"], channel: "push", reason: `Source ${prefix}`, idempotency_key: `campaign-audience-${prefix}` } });
  expect(captureReply.status()).toBe(200); const capture = await captureReply.json();
  const subject = null, body = " Bonjour {customer_name}\n🙂 literal ";
  const templateReply = await request.post(base + "/templates", { headers, data: { template_id: null, previous_id: null,
    content: { name: `Source template ${prefix}`, channel: "push", origin: "ai", subject, body }, reason: "Explicit retained template", idempotency_key: `campaign-template-${prefix}` } });
  expect(templateReply.status()).toBe(200); const template = await templateReply.json();
  async function open(){await page.getByRole("button",{name:"Copilot",exact:true}).click();await expect(page.getByRole("combobox",{name:"Consultation",exact:true})).toBeEnabled();await page.getByRole("button",{name:"Préparer un brouillon marketing",exact:true}).click();}
  await open();const panel=page.getByRole("region",{name:"Copilot",exact:true}),posts:string[]=[];page.on("request",r=>{if(r.method()==="POST")posts.push(r.url());});
  await expect(panel.getByRole("textbox",{name:"Votre demande de brouillon",exact:true})).toBeEnabled();await panel.getByRole("textbox",{name:"Votre demande de brouillon",exact:true}).fill("Preparer un brouillon de campagne marketing");await panel.getByRole("button",{name:"Lire les audiences conservées",exact:true}).click();await panel.getByRole("combobox",{name:"Audience sélectionnée",exact:true}).selectOption(capture.id);await panel.getByRole("button",{name:"Lire les modèles originaux",exact:true}).click();await panel.getByRole("combobox",{name:"Modèle sélectionné",exact:true}).selectOption(template.id);
  expect(capture.summary.eligible_count).toBe(0);
  const campaigns=async()=>{const r=await request.get(base+"/campaigns?offset=0&limit=20",{headers});expect(r.status()).toBe(200);return await r.json();};const beforeDraft=await campaigns();
  await panel.getByRole("button",{name:"Vérifier le brouillon marketing",exact:true}).click();await expect(panel.getByRole("alert")).toContainText("Choisissez une audience admissible");
  await expect(panel.getByRole("article",{name:"Brouillon marketing vérifié",exact:true})).toHaveCount(0);await expect(panel.getByRole("button",{name:"Conserver le brouillon marketing",exact:true})).toHaveCount(0);
  expect(posts).toEqual([]);expect(await campaigns()).toEqual(beforeDraft);await page.screenshot({path:info.outputPath("copilot-marketing-push-refused.png"),fullPage:true});
});
