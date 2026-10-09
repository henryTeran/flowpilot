import {expect,test} from "@playwright/test";

test("BASE historical CRM preserves recency precedence and unknown history",async({page,request},info)=>{
  test.setTimeout(120000);
  test.skip(process.env.FLOWPILOT_BROWSER_CRM_HISTORY_FIXTURE!=="1","Explicit owned historical fixture required");
  const api="http://127.0.0.1:4198/api/v1",institute="demo-institute-geneve";
  const manifestReply=await request.get("http://127.0.0.1:4198/_fixture/crm-history");expect(manifestReply.status()).toBe(200);
  const cases=(await manifestReply.json()).filter((row:any)=>row.project===info.project.name);expect(cases).toHaveLength(4);
  const auth=await request.post(`${api}/auth/login`,{data:{email:"manager@browser.example.com",password:"Browser-test-only-2026"}});expect(auth.status()).toBe(200);const headers={Authorization:`Bearer ${(await auth.json()).access_token}`};
  async function get(path:string){const r=await request.get(`${api}${path}`,{headers});expect(r.status(),await r.text()).toBe(200);return r.json();}
  const path=`/crm/institutes/${institute}/segment-policies`,previous=await get(path+"/current"),day=86400000000;
  const retained=await request.post(api+path,{headers,data:{policy:{institute_id:institute,observation_us:365*day,new_customer_us:30*day,at_risk_us:60*day,dormant_us:90*day,loyal_min_tickets:2,vip_min_tickets:3,vip_currency:"CHF",vip_gross_minor:"300"},previous_policy_id:previous?.id??null,reason:"Explicit historical CRM acceptance policy",idempotency_key:`history-policy-${info.project.name}`}});expect(retained.status(),await retained.text()).toBe(200);const policy=await retained.json();
  await page.goto("/");await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");await page.getByRole("button",{name:"Se connecter",exact:true}).click();await expect(page.locator(".flow-session-exit")).toBeVisible();await page.getByRole("button",{name:"Copilot",exact:true}).click();
  const panel=page.getByRole("region",{name:"Copilot",exact:true}),writes:string[]=[];
  page.on("request",r=>{if(!["GET","HEAD","OPTIONS"].includes(r.method()))writes.push(r.url());});
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("CLIENT_SUMMARY");
  for(const item of cases){
    const profilePath=`/crm/institutes/${institute}/customers/${item.customer_id}/segment`,before=await get(profilePath);
    const observed=item.label==="risk"||item.label==="dormant",state=item.label==="risk"?"AT_RISK":item.label==="dormant"?"DORMANT":null;
    expect(before.segment.state).toBe(state);expect(before.segment.reason).toBe(observed?(state==="AT_RISK"?"risk_recency":"dormant_recency"):"no_observed_closing");
    await panel.getByRole("textbox",{name:"Rechercher une cliente",exact:true}).fill(item.name);await panel.getByRole("button",{name:"Rechercher les clientes",exact:true}).click();await panel.getByRole("combobox",{name:"Cliente",exact:true}).selectOption(item.customer_id);await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Resumer le profil CRM cliente");
    const pending=page.waitForResponse(r=>r.url().endsWith("/copilot/query")&&r.request().method()==="POST");await panel.getByRole("button",{name:"Consulter",exact:true}).click();const reply=await pending;expect(reply.status()).toBe(200);const evidence=(await reply.json()).evidence,value=evidence.result;
    expect(evidence.capability).toBe("CLIENT_SUMMARY");expect(value.customer_id).toBe(item.customer_id);expect(value.policy_original.id).toBe(policy.id);expect(value.segment.state).toBe(state);expect(value.segment.billing.closed_tickets).toBe(observed?3:0);expect(value.segment.billing.currencies).toEqual(before.segment.billing.currencies);expect(value.complete_customer_history).toBe(false);
    if(observed){expect(value.segment.billing.currencies[0].known_gross_minor).toBe("4500");expect(new Date(value.segment.billing.last_recorded_closed_at).toISOString()).toBe(new Date(item.paid_at).toISOString());}
    const facts=panel.getByRole("region",{name:"Réponse du Copilot",exact:true});await expect(facts.getByRole("heading",{name:state==="AT_RISK"?"À risque":state==="DORMANT"?"Inactive":"Segment non établi",exact:true})).toBeVisible();await expect(facts).toContainText(`${observed?3:0} ticket(s) clôturé(s)`);await expect(facts).toContainText("historique complet");await expect(panel).not.toContainText("+33999111222");
    const after=await get(profilePath);expect(after.segment.billing.currencies).toEqual(before.segment.billing.currencies);expect(after.segment.billing.closed_tickets).toBe(before.segment.billing.closed_tickets);expect(after.segment.billing.last_recorded_closed_at).toBe(before.segment.billing.last_recorded_closed_at);
    await page.screenshot({path:info.outputPath(`crm-history-${item.label}.png`),fullPage:true});
  }
  expect(writes).toEqual(Array(4).fill(api+"/copilot/query"));expect(await get(path+"/current")).toEqual(policy);
});
