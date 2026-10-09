import { expect, test } from "@playwright/test";
test("marketing refuses damaged preview then recovers intact original draft", async ({ page, request }, info) => {
  test.setTimeout(120000);
  await page.goto("/"); await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026"); await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("flowpilot.access_token")), headers = { Authorization: `Bearer ${token}` };
  const api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve", prefix = `damaged-${info.project.name}`;
  const customerReply = await request.post(`${api}/customers/institutes/${institute}`, { headers, data: { display_name: `Campaign ${prefix}`, idempotency_key: `campaign-client-${prefix}` } });
  expect(customerReply.status()).toBe(200); const customer = await customerReply.json();
  const policies = `${api}/crm/institutes/${institute}/segment-policies`, before = await request.get(policies + "/current", { headers }), previous = await before.json();
  const policy = await request.post(policies, { headers, data: { policy: { institute_id: institute, observation_us: 1209600000000, new_customer_us: 86400000000,
    at_risk_us: 172800000000, dormant_us: 604800000000, loyal_min_tickets: 2, vip_min_tickets: 3, vip_currency: "CHF", vip_gross_minor: "300" },
    previous_policy_id: previous?.id || null, reason: "Explicit campaign source segments", idempotency_key: `campaign-policy-${prefix}` } }); expect(policy.status()).toBe(200);
  const communications = ["email", "sms"].flatMap(channel => ["service_follow_up", "marketing"].map(purpose => ({ channel, purpose,
    permission: channel === "email" && purpose === "marketing" ? "granted" : "unknown", evidence: channel === "email" && purpose === "marketing" ? "Explicit campaign fixture permission" : null })));
  const declared = await request.post(`${api}/crm/institutes/${institute}/customers/${customer.id}/lifecycle-declarations`, { headers, data: {
    declaration: { institute_id: institute, customer_id: customer.id, birthday: null, birthday_evidence: null, communications }, previous_id: null,
    reason: "Explicit campaign permission", idempotency_key: `campaign-permission-${prefix}` } }); expect(declared.status()).toBe(200);
  const base = `${api}/marketing/institutes/${institute}`;
  const captureReply = await request.post(base + "/audience-captures", { headers, data: { segments: ["NEW"], channel: "email", reason: `Source ${prefix}`, idempotency_key: `campaign-audience-${prefix}` } });
  expect(captureReply.status()).toBe(200); const capture = await captureReply.json();
  const subject = `Campaign subject ${prefix}`, body = " Bonjour {customer_name}\n🙂 literal ";
  const templateReply = await request.post(base + "/templates", { headers, data: { template_id: null, previous_id: null,
    content: { name: `Source template ${prefix}`, channel: "email", origin: "ai", subject, body }, reason: "Explicit retained template", idempotency_key: `campaign-template-${prefix}` } });
  expect(templateReply.status()).toBe(200); const template = await templateReply.json();
  async function open(){await page.getByRole("button",{name:"Copilot",exact:true}).click();await expect(page.getByRole("combobox",{name:"Consultation",exact:true})).toBeEnabled();await page.getByRole("button",{name:"Préparer un brouillon marketing",exact:true}).click();}
  await open();const panel=page.getByRole("region",{name:"Copilot",exact:true}),posts:string[]=[];page.on("request",r=>{if(r.method()==="POST")posts.push(r.url());});
  await expect(panel.getByRole("textbox",{name:"Votre demande de brouillon",exact:true})).toBeEnabled();await panel.getByRole("textbox",{name:"Votre demande de brouillon",exact:true}).fill("Preparer un brouillon de campagne marketing");await panel.getByRole("button",{name:"Lire les audiences conservées",exact:true}).click();await panel.getByRole("combobox",{name:"Audience sélectionnée",exact:true}).selectOption(capture.id);await panel.getByRole("button",{name:"Lire les modèles originaux",exact:true}).click();await panel.getByRole("combobox",{name:"Modèle sélectionné",exact:true}).selectOption(template.id);
  await page.route("**/api/v1/copilot/prepare-preview/marketing",async route=>{const r=await route.fetch();expect(r.status()).toBe(200);const v=await r.json();await route.fulfill({response:r,json:{...v,recipient_count:v.recipient_count+1}});});
  await panel.getByRole("button",{name:"Vérifier le brouillon marketing",exact:true}).click();await expect(panel.getByRole("alert")).toContainText("Sources ou aperçu à vérifier");await expect(panel.getByRole("article",{name:"Brouillon marketing vérifié",exact:true})).toHaveCount(0);await expect(panel.getByRole("button",{name:"Conserver le brouillon marketing",exact:true})).toHaveCount(0);
  await page.unroute("**/api/v1/copilot/prepare-preview/marketing");
  const previewWait=page.waitForResponse(r=>r.url().endsWith("/copilot/prepare-preview/marketing"));await panel.getByRole("button",{name:"Vérifier le brouillon marketing",exact:true}).click();const previewResponse=await previewWait;expect(previewResponse.status(),await previewResponse.text()).toBe(200);await expect(panel.getByRole("article",{name:"Brouillon marketing vérifié",exact:true})).toContainText(subject);await expect(panel.locator("pre")).toHaveText(body);
  const catalogue=async()=>{const r=await request.get(base+"/campaigns?offset=0&limit=20",{headers});expect(r.status()).toBe(200);return await r.json();};const beforeDraft=await catalogue();
  await panel.getByRole("textbox",{name:"Motif du brouillon",exact:true}).fill("Brouillon explicitement relu");let receipt:any;await page.route("**/api/v1/copilot/prepare/marketing",async route=>{const r=await route.fetch();expect(r.status(),await r.text()).toBe(200);receipt=await r.json();await route.abort("failed");});await panel.getByRole("button",{name:"Conserver le brouillon marketing",exact:true}).click();await expect(panel.getByRole("article",{name:"Demande de brouillon conservée",exact:true})).toBeVisible();expect(receipt.state).toBe("DRAFT");const afterDraft=await catalogue();expect(afterDraft.total).toBe(beforeDraft.total+1);
  await page.reload();await expect(page.locator(".flow-session-exit")).toBeVisible();await open();await panel.getByRole("button",{name:"Reprendre le brouillon",exact:true}).click();await expect(panel.getByRole("article",{name:"Brouillon marketing conservé",exact:true})).toContainText(receipt.original_id);await expect(panel.locator("pre")).toHaveText(body);await expect(panel.getByRole("alert")).toHaveCount(0);expect(await catalogue()).toEqual(afterDraft);expect(posts).toEqual([api+"/copilot/prepare-preview/marketing",api+"/copilot/prepare-preview/marketing",api+"/copilot/prepare/marketing"]);
  const originalResponse=await request.get(base+"/campaigns/"+receipt.original_id,{headers});expect(originalResponse.status()).toBe(200);const original=await originalResponse.json();expect(original.revision).toMatchObject({state:"DRAFT",external_message_sent:false,delivery_authorized:false,content:{subject,body,template_original_id:template.id,audience:{id:capture.id}}});await page.screenshot({path:info.outputPath("copilot-marketing-damaged.png"),fullPage:true});
});
