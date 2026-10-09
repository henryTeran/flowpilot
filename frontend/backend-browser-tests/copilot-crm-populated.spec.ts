import {expect,test} from "@playwright/test";

test("CRM consultations classify actual paid histories without changing the retained facts",async({page,request},info)=>{
  test.setTimeout(120000);
  const api="http://127.0.0.1:4198/api/v1", institute="demo-institute-geneve";
  const auth=await request.post(`${api}/auth/login`,{data:{email:"manager@browser.example.com",password:"Browser-test-only-2026"}});
  expect(auth.status()).toBe(200);
  const headers={Authorization:`Bearer ${(await auth.json()).access_token}`};
  const currency=await request.put(`${api}/gift-cards/institutes/${institute}/settings`,{headers,data:{currency:"CHF"}});
  expect(currency.status(),await currency.text()).toBe(200);
  async function post(path:string,data:unknown){const r=await request.post(`${api}${path}`,{headers,data});expect(r.status(),await r.text()).toBe(200);return r.json();}
  async function patch(path:string,data?:unknown){const r=await request.patch(`${api}${path}`,{headers,data});expect(r.status(),await r.text()).toBe(200);return r.json();}
  async function get(path:string){const r=await request.get(`${api}${path}`,{headers});expect(r.status(),await r.text()).toBe(200);return r.json();}
  const policyPath=`/crm/institutes/${institute}/segment-policies`, previous=await get(`${policyPath}/current`), day=86400000000;
  const policy=await post(policyPath,{policy:{institute_id:institute,observation_us:365*day,new_customer_us:30*day,at_risk_us:60*day,dormant_us:90*day,loyal_min_tickets:2,vip_min_tickets:3,vip_currency:"CHF",vip_gross_minor:"1"},previous_policy_id:previous?.id??null,reason:"Owned populated CRM browser fixture",idempotency_key:`populated-crm-policy-${info.project.name}`});
  const cases=[];
  for(const [index,state] of ["ACTIVE","LOYAL","VIP"].entries()){
    const identity=`CRM populated ${info.project.name} ${state}`;
    const customer=await post(`/customers/institutes/${institute}`,{display_name:identity,phone:"+33999111222",idempotency_key:`populated-crm-${info.project.name}-${state}`});
    const tickets=[];
    for(let n=0;n<=index;n++){
      const ticket=await post("/tickets",{institute_id:institute,service_id:"svc-aisselles",customer_id:customer.id,idempotency_key:`populated-ticket-${info.project.name}-${state}-${n}`});
      const session=await post("/planning/sessions/start",{ticket_id:ticket.id,service_id:"svc-aisselles",employee_id:"emp-angela"});
      await patch(`/planning/sessions/${session.id}/finish`);
      await patch(`/tickets/${ticket.id}/checkout/start`,{employee_id:"emp-angela"});
      const paid=await patch(`/tickets/${ticket.id}/checkout/pay`,{employee_id:"emp-angela",payment_method:"especes"});
      expect(paid.currency).toBe("CHF");tickets.push(paid);
    }
    const original=await get(`/crm/institutes/${institute}/customers/${customer.id}/segment`);
    expect(original.segment.state).toBe(state);
    cases.push({identity,customer,state,count:index+1,original,tickets});
  }
  await page.goto("/");await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");await page.getByRole("button",{name:"Se connecter",exact:true}).click();
  await expect(page.locator(".flow-session-exit")).toBeVisible();await page.getByRole("button",{name:"Copilot",exact:true}).click();
  const panel=page.getByRole("region",{name:"Copilot",exact:true}), writes:string[]=[];
  page.on("request",r=>{if(!["GET","HEAD","OPTIONS"].includes(r.method()))writes.push(r.url());});
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("CLIENT_SUMMARY");
  for(const item of cases){
    await panel.getByRole("textbox",{name:"Rechercher une cliente",exact:true}).fill(item.identity);await panel.getByRole("button",{name:"Rechercher les clientes",exact:true}).click();await panel.getByRole("combobox",{name:"Cliente",exact:true}).selectOption(item.customer.id);
    await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Resumer le profil CRM cliente");
    const pending=page.waitForResponse(r=>r.url().endsWith("/copilot/query")&&r.request().method()==="POST");await panel.getByRole("button",{name:"Consulter",exact:true}).click();
    const response=await pending;expect(response.status()).toBe(200);const evidence=(await response.json()).evidence;
    expect(evidence.result.customer_id).toBe(item.customer.id);expect(evidence.result.policy_original.id).toBe(policy.id);expect(evidence.result.segment.state).toBe(item.state);expect(evidence.result.segment.billing.closed_tickets).toBe(item.count);
    const facts=panel.getByRole("region",{name:"Réponse du Copilot",exact:true});
    await expect(facts.getByRole("heading",{name:({ACTIVE:"Active",LOYAL:"Fidèle",VIP:"VIP"} as Record<string,string>)[item.state],exact:true})).toBeVisible();
    await expect(facts).toContainText(`${item.count} ticket(s) clôturé(s)`);await expect(facts).toContainText("CHF");await expect(facts).toContainText("historique complet");await expect(panel).not.toContainText("+33999111222");
    const after=await get(`/crm/institutes/${institute}/customers/${item.customer.id}/segment`);
    expect(after.segment.billing.currencies).toEqual(item.original.segment.billing.currencies);expect(after.segment.billing.closed_tickets).toBe(item.count);expect(after.segment.billing.last_recorded_closed_at).toBe(item.original.segment.billing.last_recorded_closed_at);
    await page.screenshot({path:info.outputPath(`crm-${item.state.toLowerCase()}.png`),fullPage:true});
  }
  expect(writes).toEqual(Array(3).fill(`${api}/copilot/query`));expect(await get(`${policyPath}/current`)).toEqual(policy);
});
