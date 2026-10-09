import {expect,test} from "@playwright/test";

test("BASE rebooking reads completed care, explicit policy and linked active booking without execution",async({page,request},info)=>{
  test.setTimeout(120000);
  const api="http://127.0.0.1:4198/api/v1",institute="demo-institute-geneve";
  const auth=await request.post(`${api}/auth/login`,{data:{email:"manager@browser.example.com",password:"Browser-test-only-2026"}});expect(auth.status()).toBe(200);
  const headers={Authorization:`Bearer ${(await auth.json()).access_token}`},key=`rebooking-populated-${info.project.name}`;
  async function post(path:string,data:unknown){const r=await request.post(`${api}${path}`,{headers,data});expect(r.status(),await r.text()).toBe(200);return r.json();}
  async function get(path:string){const r=await request.get(`${api}${path}`,{headers});expect(r.status(),await r.text()).toBe(200);return r.json();}
  const name=`Reprise observée ${info.project.name}`,customer=await post(`/customers/institutes/${institute}`,{display_name:name,phone:"+33999111222",idempotency_key:key});
  const ticket=await post("/tickets",{institute_id:institute,service_id:"svc-aisselles",customer_id:customer.id,idempotency_key:key+"-ticket"});
  const session=await post("/planning/sessions/start",{ticket_id:ticket.id,service_id:"svc-aisselles",employee_id:"emp-angela"});
  const finished=await request.patch(`${api}/planning/sessions/${session.id}/finish`,{headers});expect(finished.status(),await finished.text()).toBe(200);const care=await finished.json();
  const policies=`/crm/institutes/${institute}/automation-policies`;
  let previous=await get(policies+"/current");
  async function retain(enabled:boolean,offset:string,label:string){
    const rules=["birthday","post_service","rebooking","inactivity","package_expiry","subscription_renewal"].map(trigger=>({trigger,enabled:trigger==="rebooking"&&enabled,offset_us:trigger==="rebooking"?offset:trigger==="inactivity"?"1":"0"}));
    previous=await post(policies,{policy:{institute_id:institute,rules},previous_policy_id:previous?.id??null,reason:"Explicit owned rebooking browser policy",idempotency_key:key+"-"+label});return previous;
  }
  await retain(true,"86400000000","not-due");
  await page.goto("/");await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");await page.getByRole("button",{name:"Se connecter",exact:true}).click();await expect(page.locator(".flow-session-exit")).toBeVisible();await page.getByRole("button",{name:"Copilot",exact:true}).click();
  const panel=page.getByRole("region",{name:"Copilot",exact:true}),writes:string[]=[];
  page.on("request",r=>{if(!["GET","HEAD","OPTIONS"].includes(r.method()))writes.push(r.url());});
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("CLIENT_REBOOKING_OPPORTUNITIES");await panel.getByRole("textbox",{name:"Rechercher une cliente",exact:true}).fill(name);await panel.getByRole("button",{name:"Rechercher les clientes",exact:true}).click();await panel.getByRole("combobox",{name:"Cliente",exact:true}).selectOption(customer.id);await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Examiner les opportunites de reprise rendez-vous");
  async function consult(review:string,label:string){
    const pending=page.waitForResponse(r=>r.url().endsWith("/copilot/query")&&r.request().method()==="POST");await panel.getByRole("button",{name:"Consulter",exact:true}).click();const response=await pending;expect(response.status()).toBe(200);
    const evidence=(await response.json()).evidence,value=evidence.result;
    expect(evidence.capability).toBe("CLIENT_REBOOKING_OPPORTUNITIES");expect(value.customer_id).toBe(customer.id);expect(value.policy_original_id).toBe(previous.id);expect(value.review).toBe(review);expect(value.candidate.source.source_kind).toBe("care_episode");
    expect(value.candidate.source.source_id).toBe(ticket.id);expect(value.candidate.source.occurred_at).toBe(care.real_end_time);
    expect(value.execution_authorized).toBe(false);expect(value.delivery_authorized).toBe(false);expect(value.external_message_sent).toBe(false);expect(value.complete_customer_history).toBe(false);
    const facts=panel.getByRole("region",{name:"Réponse du Copilot",exact:true});await expect(facts.getByRole("heading",{name:label,exact:true})).toBeVisible();await expect(facts).toContainText("Soin observé");await expect(facts).toContainText("Échéance selon la règle");await expect(facts).toContainText("n’autorise aucune réservation");await expect(panel).not.toContainText("+33999111222");
    await page.screenshot({path:info.outputPath(`rebooking-${review}.png`),fullPage:true});return value;
  }
  const notDue=await consult("not_due","Échéance de reprise non atteinte");expect(notDue.candidate.state).toBe("scheduled");expect(notDue.active_bookings).toEqual([]);
  await retain(false,"1","disabled");const disabled=await consult("disabled","Règle de reprise désactivée");expect(disabled.candidate.state).toBe("disabled");
  await retain(true,"1","due");const available=await consult("available","Reprise à examiner avec la cliente");expect(available.candidate.state).toBe("due");expect(available.active_bookings).toEqual([]);
  const day=info.project.name==="desktop"?"2027-12-08":"2027-12-09";
  const booking=await post("/appointments",{institute_id:institute,employee_id:"emp-angela",service_id:"svc-aisselles",customer_id:customer.id,customer_name:name,start_time:`${day}T09:00:00Z`,idempotency_key:key+"-booking"});
  const path=`/appointments?institute_id=${institute}&day=${day}`,before=await get(path);
  const booked=await consult("already_booked","Rendez-vous actif déjà enregistré");expect(booked.active_bookings.map((b:any)=>b.appointment_id)).toEqual([booking.id]);expect(booked.candidate.source).toEqual(available.candidate.source);
  expect(await get(path)).toEqual(before);expect(await get(policies+"/current")).toEqual(previous);expect(writes).toEqual(Array(4).fill(`${api}/copilot/query`));
});
