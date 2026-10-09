import { expect, test } from "@playwright/test";
test.setTimeout(120000);
const api = "http://127.0.0.1:4198/api/v1", institute = "demo-institute-geneve";
async function login(page: any, email = "manager@browser.example.com") {
  await page.goto("/");
  await page.getByLabel("Adresse e-mail").fill(email);
  await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button",{name:"Se connecter",exact:true}).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();
  await page.getByRole("button",{name:"Copilot",exact:true}).click();
  const panel = page.getByRole("region",{name:"Copilot",exact:true});
  await expect(panel.getByRole("combobox",{name:"Consultation",exact:true})).toBeEnabled();
  return panel;
}
test("real BASE consultations preserve selected identity, planning and physical versus pending stock",async ({page,request},info) => {
  const session = await request.post(`${api}/auth/login`,{data:{email:"manager@browser.example.com",password:"Browser-test-only-2026"}});
  expect(session.status()).toBe(200);
  const headers = {Authorization:`Bearer ${(await session.json()).access_token}`};
  const identity = `Copilot ${info.project.name}`;
  const customer = await request.post(`${api}/customers/institutes/${institute}`,{headers,data:{display_name:identity,phone:"+33999988877",idempotency_key:`copilot-customer-${info.project.name}`}});
  expect(customer.status()).toBe(200);
  const item = await request.post(`${api}/inventory/institutes/${institute}/items`,{headers,data:{sku:`CP-${info.project.name}`,name:`Article Copilot ${info.project.name}`,category:"cabine",unit:"ml",reorder_threshold:"4.125",reason:"Explicit browser stock fixture",idempotency_key:`copilot-item-${info.project.name}`}});
  expect(item.status(),await item.text()).toBe(200);
  const panel = await login(page);
  const requests:any[]=[];
  page.on("request",r => {if (r.method()==="POST" && r.url().includes("/copilot/")) requests.push({url:r.url(),body:r.postDataJSON()});});
  await expect(panel.getByRole("combobox",{name:"Consultation",exact:true})).toHaveValue("");
  expect(requests).toHaveLength(0);
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("CLIENT_READ");
  await panel.getByRole("textbox",{name:"Rechercher une cliente",exact:true}).fill(identity);
  await panel.getByRole("button",{name:"Rechercher les clientes",exact:true}).click();
  await expect(panel.getByRole("combobox",{name:"Cliente",exact:true}).locator("option").filter({hasText:identity})).toHaveCount(1);
  await expect(panel).not.toContainText("+33999988877");
  await panel.getByRole("combobox",{name:"Cliente",exact:true}).selectOption((await customer.json()).id);
  await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Consulter la fiche cliente");
  await panel.getByRole("button",{name:"Consulter",exact:true}).click();
  await expect(panel.getByRole("region",{name:"Réponse du Copilot",exact:true})).toContainText(identity);
  for (const [capability,message] of [["PLANNING_READ","Consulter le planning du jour"],["PLANNING_GAPS","Consulter les creneaux libres"],["STOCK_READ","Consulter les stocks enregistres"]]) {
    await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption(capability);
    await expect(panel.getByRole("region",{name:"Réponse du Copilot",exact:true})).toHaveCount(0);
    if (capability === "PLANNING_GAPS") await panel.getByRole("combobox",{name:"Prestation à vérifier",exact:true}).selectOption("svc-aisselles");
    await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill(message);
    await panel.getByRole("button",{name:"Consulter",exact:true}).click();
    await expect(panel.getByRole("region",{name:"Réponse du Copilot",exact:true})).toBeVisible();
    await expect(panel.getByRole("alert")).toHaveCount(0);
  }
  await expect(panel).toContainText(`Article Copilot ${info.project.name}`);
  await expect(panel).toContainText("4,125");
  expect(requests).toHaveLength(4);
  expect(requests.every(row => row.url.endsWith("/copilot/query"))).toBe(true);
  expect(requests.map(row => Object.keys(row.body))).toEqual(Array(4).fill(["message","ui_context"]));
  await page.screenshot({path:info.outputPath("copilot-stock.png"),fullPage:true});
  const actual = await request.get(`${api}/inventory/institutes/${institute}/items/${(await item.json()).id}`,{headers});
  expect((await actual.json()).on_hand).toBe("0.000");
});

test("rebooking preserves unavailable original sources through real BASE",async ({page,request},info) => {
  const session=await request.post(`${api}/auth/login`,{data:{email:"manager@browser.example.com",password:"Browser-test-only-2026"}});
  expect(session.status()).toBe(200);
  const headers={Authorization:`Bearer ${(await session.json()).access_token}`};
  const identity=`Reprise Copilot ${info.project.name}`;
  const created=await request.post(`${api}/customers/institutes/${institute}`,{headers,data:{display_name:identity,phone:"+33999777666",idempotency_key:`reprise-copilot-${info.project.name}`}});
  expect(created.status()).toBe(200);const customer=await created.json();
  const panel=await login(page),posts:string[]=[];
  page.on("request",r=>{if(r.method()==="POST")posts.push(r.url());});
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("CLIENT_REBOOKING_OPPORTUNITIES");
  await panel.getByRole("textbox",{name:"Rechercher une cliente",exact:true}).fill(identity);
  await panel.getByRole("button",{name:"Rechercher les clientes",exact:true}).click();
  await panel.getByRole("combobox",{name:"Cliente",exact:true}).selectOption(customer.id);
  await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Examiner les opportunites de reprise rendez-vous");
  const result=page.waitForResponse(r=>r.url().endsWith("/copilot/query") && r.request().method()==="POST");
  await panel.getByRole("button",{name:"Consulter",exact:true}).click();
  const response=await result;expect(response.status()).toBe(200);
  const evidence=(await response.json()).evidence;
  expect(evidence.capability).toBe("CLIENT_REBOOKING_OPPORTUNITIES");expect(evidence.result.customer_id).toBe(customer.id);
  expect(evidence.result.review).toBe("unavailable");expect(evidence.result.candidate).toBeNull();
  expect(evidence.result.execution_authorized).toBe(false);expect(evidence.result.delivery_authorized).toBe(false);
  const facts=panel.getByRole("region",{name:"Réponse du Copilot",exact:true});
  await expect(facts).toContainText("Opportunité non établie");await expect(facts).toContainText("Dernier soin non établi");
  await expect(facts).toContainText("n’autorise aucune réservation");await expect(panel).not.toContainText("+33999777666");
  expect(posts).toEqual([`${api}/copilot/query`]);
  await page.screenshot({path:info.outputPath("copilot-rebooking.png"),fullPage:true});
});

test("recorded capacity binds the selected day through real BASE without reservation authority",async({page},info)=>{
  const panel=await login(page),posts:any[]=[];
  page.on("request",r=>{if(r.method()==="POST")posts.push({url:r.url(),body:r.postDataJSON()});});
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("EMPLOYEE_CAPACITY");
  const day="2025-10-26";
  await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Mesurer la capacite enregistree des collaboratrices");
  await expect(panel.getByRole("button",{name:"Consulter",exact:true})).toBeDisabled();
  await panel.getByLabel("Journée terminée").fill(day);
  const result=page.waitForResponse(r=>r.url().endsWith("/copilot/query") && r.request().method()==="POST");
  await panel.getByRole("button",{name:"Consulter",exact:true}).click();
  const response=await result;expect(response.status()).toBe(200);
  const evidence=(await response.json()).evidence;
  expect(evidence.capability).toBe("EMPLOYEE_CAPACITY");expect(evidence.result.day).toBe(day);
  expect(evidence.result.window.institute_id).toBe(institute);
  expect(evidence.result.complete_attendance).toBe(false);expect(evidence.result.bookable_capacity).toBeNull();
  const facts=panel.getByRole("region",{name:"Réponse du Copilot",exact:true});
  await expect(facts).toContainText(day);await expect(facts).toContainText("capacité réservable ne sont pas établies");
  await expect(panel.getByRole("alert")).toHaveCount(0);
  expect(posts).toEqual([{url:`${api}/copilot/query`,body:{message:"Mesurer la capacite enregistree des collaboratrices",ui_context:{day}}}]);
  await page.screenshot({path:info.outputPath("copilot-capacity.png"),fullPage:true});
  await panel.getByLabel("Journée terminée").fill("2025-10-27");await expect(facts).toHaveCount(0);
});

test("reception consults through BASE and rejects damaged evidence before showing facts",async ({page}) => {
  const panel = await login(page,"cashier@browser.example.com");
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("STOCK_READ");
  await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Consulter les stocks enregistres");
  let damage = true;
  await page.route("**/copilot/query",async route => {
    const response = await route.fetch(), value = await response.json();
    if (damage) expect(response.status()).toBe(200);
    await route.fulfill({response,json:damage ? {...value,evidence:{...value.evidence,fingerprint:"0".repeat(64)}} : value});
  });
  await panel.getByRole("button",{name:"Consulter",exact:true}).click();
  await expect(panel.getByRole("alert")).toBeVisible();
  await expect(panel.getByRole("region",{name:"Réponse du Copilot",exact:true})).toHaveCount(0);
  damage = false;
  await panel.getByRole("button",{name:"Consulter",exact:true}).click();
  await expect(panel.getByRole("region",{name:"Réponse du Copilot",exact:true})).toBeVisible();
  await expect(panel.getByRole("alert")).toHaveCount(0);
  await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Une question inconnue sans selection de source");
  await expect(panel.getByRole("region",{name:"Réponse du Copilot",exact:true})).toHaveCount(0);
  await panel.getByRole("button",{name:"Consulter",exact:true}).click();
  await expect(panel.getByRole("alert")).toBeVisible(); // official BASE resolves a manager-only capability; reception remains denied
  await expect(panel.getByRole("region",{name:"Réponse du Copilot",exact:true})).toHaveCount(0);
  await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Bonjour");
  await panel.getByRole("button",{name:"Consulter",exact:true}).click();
  await expect(panel.getByRole("heading",{name:"Précisions nécessaires",exact:true})).toBeVisible();
  await expect(panel.locator("table")).toHaveCount(0);
});

test("CRM summary uses the real retained policy and selected customer without mutation",async ({page,request},info) => {
  const session = await request.post(`${api}/auth/login`,{data:{email:"manager@browser.example.com",password:"Browser-test-only-2026"}});
  expect(session.status()).toBe(200);
  const headers = {Authorization:`Bearer ${(await session.json()).access_token}`};
  const identity = `CRM Copilot ${info.project.name}`;
  const created = await request.post(`${api}/customers/institutes/${institute}`,{headers,data:{display_name:identity,phone:"+33999111222",idempotency_key:`crm-copilot-${info.project.name}`}});
  expect(created.status()).toBe(200);const customer = await created.json();
  const before = await request.get(`${api}/crm/institutes/${institute}/segment-policies/current`,{headers});
  expect(before.status()).toBe(200);const previous = await before.json();
  const day = 86400000000;
  const retained = await request.post(`${api}/crm/institutes/${institute}/segment-policies`,{headers,data:{
    policy:{institute_id:institute,observation_us:365*day,new_customer_us:30*day,at_risk_us:60*day,dormant_us:90*day,loyal_min_tickets:3,vip_min_tickets:5,vip_currency:"CHF",vip_gross_minor:"10000"},
    previous_policy_id:previous?.id ?? null,reason:"Explicit CRM browser fixture",idempotency_key:`crm-policy-copilot-${info.project.name}`}});
  expect(retained.status(),await retained.text()).toBe(200);const policy = await retained.json();
  const panel = await login(page), posts:string[]=[];
  page.on("request",r => {if(r.method()==="POST") posts.push(r.url());});
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("CLIENT_SUMMARY");
  await panel.getByRole("textbox",{name:"Rechercher une cliente",exact:true}).fill(identity);
  await panel.getByRole("button",{name:"Rechercher les clientes",exact:true}).click();
  await panel.getByRole("combobox",{name:"Cliente",exact:true}).selectOption(customer.id);
  await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Resumer le profil CRM cliente");
  const result = page.waitForResponse(r => r.url().endsWith("/copilot/query") && r.request().method()==="POST");
  await panel.getByRole("button",{name:"Consulter",exact:true}).click();
  const response = await result;expect(response.status()).toBe(200);
  const evidence = (await response.json()).evidence;
  expect(evidence.capability).toBe("CLIENT_SUMMARY");expect(evidence.result.customer_id).toBe(customer.id);
  expect(evidence.result.policy_original.id).toBe(policy.id);
  const facts = panel.getByRole("region",{name:"Réponse du Copilot",exact:true});
  await expect(facts).toContainText("Nouvelle cliente");await expect(facts).toContainText("historique complet");
  await expect(facts).toContainText("0 ticket(s) clôturé(s)");await expect(panel).not.toContainText("+33999111222");
  expect(posts).toEqual([`${api}/copilot/query`]);
  await page.screenshot({path:info.outputPath("copilot-crm.png"),fullPage:true});
  const after = await request.get(`${api}/crm/institutes/${institute}/segment-policies/current`,{headers});
  expect((await after.json()).id).toBe(policy.id);
  await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Autre question");
  await expect(facts).toHaveCount(0);
});
