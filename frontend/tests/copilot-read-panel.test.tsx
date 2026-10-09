import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { CopilotPanel } from "../src/components/CopilotPanel";
import { setAccessToken } from "../src/api/session";
import { revenueOriginalFingerprint as hash } from "../src/revenue-scenario-utils";
import { validReadResponse, validReadDiscovery } from "../src/copilot-read-utils";
const dom = new JSDOM("<div id='root'></div>",{ url:"http://localhost" });
Object.assign(globalThis,{ window:dom.window,document:dom.window.document,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true });
const { createRoot } = await import("react-dom/client");
const clock = "2026-10-09T10:00:00.123456Z";
const token = (institute="own",role="responsable_institut") => `h.${Buffer.from(JSON.stringify({sub:"manager",institute_id:institute,role})).toString("base64url")}.s`;
const reply = (value: unknown) => new Response(JSON.stringify(value),{ headers:{"Content-Type":"application/json"} });
const names = ["CLIENT_READ","CLIENT_SUMMARY","CLIENT_REBOOKING_OPPORTUNITIES","PLANNING_READ","PLANNING_GAPS","PLANNING_CONFLICTS","EMPLOYEE_CAPACITY","REVENUE_SUMMARY","REVENUE_LOSS_ANALYSIS","REVENUE_OPPORTUNITIES","STOCK_READ","STOCK_FORECAST"];
const discovery = (role="responsable_institut") => (role === "accueil" ? names.filter(name => ["CLIENT_READ","PLANNING_READ","PLANNING_GAPS","STOCK_READ","STOCK_FORECAST"].includes(name)) : names).map(name => ({name,level:0,permission:"planning_operator",input_schema:{},output_schema:{},application_service:"existing.service",audit:"signed_scope_interaction_id_and_source_digest_no_raw_message",mutates:false}));
async function answer(capability: string, result: unknown) {
  const evidence = {capability,institute_id:"own",captured_at:clock,read_completed_at:clock,result,integrity:"response_sha256_not_signature_or_retained_original",complete_customer_history:false};
  return {request_id:"interaction",status:"answered",answer:"Faits enregistrés",capability,evidence:{...evidence,fingerprint:await hash(evidence)},actions:[],framework:"ai-swiss/base@1.5.1"};
}
const stock = () => ({institute_id:"own",generated_at:clock,starts_at:null,ends_at:null,source:"recorded_stock",coverage:"not_applicable",demands:[],limit:50,offset:0,
  items:Array.from({length:50},(_,index) => ({item_id:`item-${index}`,item_sku:`SKU-${index}`,item_name:`Article ${index}`,category:"cabine",unit:"ml",on_hand:"1.000",threshold:"4.125",at_or_below_threshold:true,threshold_shortfall:"3.125",pending_order_quantity:"2.000",known_demand:"0.000",complete_demand:null,known_demand_shortfall:"3.125",conditional_shortfall_after_all_orders:"1.125"}))});
const customer = () => ({customer_id:"customer",institute_id:"own",display_name:"Cliente vérifiée",created_at:clock});
const render = (root:ReturnType<typeof createRoot>,institute="own") => act(async () => root.render(<CopilotPanel institute={institute} timezone="Europe/Zurich" employees={[{id:"employee",institute_id:institute,first_name:"Anne",skills:[],status:"available"}]} services={[{id:"service",name:"Soin",status:"active"} as any]} />));
async function settle() { for (let i=0;i<200 && document.querySelector('[role="status"]');i++) await act(async () => new Promise(resolve => setTimeout(resolve,5))); assert.equal(document.querySelector('[role="status"]'),null); }
async function fill(label:string,value:string) {
  const input = Array.from(document.querySelectorAll("label")).find(row => row.textContent?.startsWith(label))!.querySelector("input,select,textarea") as HTMLInputElement;
  assert.ok(input,label);
  const proto = input.tagName === "SELECT" ? dom.window.HTMLSelectElement.prototype : input.tagName === "TEXTAREA" ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype;
  await act(async () => {Object.getOwnPropertyDescriptor(proto,"value")!.set!.call(input,value);input.dispatchEvent(new dom.window.Event(input.tagName === "SELECT" ? "change" : "input",{bubbles:true}));});
}
async function click(label:string) {
  const button = Array.from(document.querySelectorAll("button")).find(row => row.textContent === label)!;
  assert.ok(button,label);assert.equal(button.disabled,false);
  await act(async () => button.click());await settle();
}

test("DOM: explicit stock/client selection, verified first50 and no implicit query, mutation or contact",async () => {
  sessionStorage.clear();setAccessToken(token());const calls:{path:string;body:any}[]=[];
  globalThis.fetch = async (url,init) => {
    const path = String(url),body = init?.body ? JSON.parse(init.body as string) : undefined;calls.push({path,body});
    if (path.endsWith("/capabilities")) return reply(discovery());
    if (path.includes("/customers/")) return reply([{id:"customer",institute_id:"own",display_name:"Cliente vérifiée",phone:"PRIVATE-PHONE",created_at:clock}]);
    assert.ok(path.endsWith("/copilot/query"));
    assert.equal(body.institute_id,undefined);assert.equal(body.actor_id,undefined);
    return reply(await answer(body.ui_context.customer_id ? "CLIENT_READ" : "STOCK_READ",body.ui_context.customer_id ? customer() : stock()));
  };
  const root = createRoot(document.getElementById("root")!);
  try {
    await render(root);await settle();assert.equal(calls.length,1);assert.equal(document.querySelector("select")!.value,"");
    await fill("Consultation","STOCK_READ");await fill("Votre question","Consulter les stocks enregistres");await click("Consulter");
    assert.equal(document.querySelectorAll("tbody tr").length,50);assert.match(document.body.textContent!,/commandes en attente/);
    assert.deepEqual(calls.at(-1)!.body,{message:"Consulter les stocks enregistres",ui_context:{}});
    await fill("Consultation","CLIENT_READ");assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);
    await fill("Rechercher une cliente","Cliente");await click("Rechercher les clientes");assert.ok(!document.body.textContent!.includes("PRIVATE-PHONE"));
    assert.equal(Array.from(document.querySelectorAll("button")).find(row => row.textContent === "Consulter")!.disabled,true);
    await fill("Cliente","customer");await fill("Votre question","Consulter la fiche cliente");await click("Consulter");
    assert.match(document.body.textContent!,/Cliente vérifiée/);assert.deepEqual(calls.at(-1)!.body.ui_context,{customer_id:"customer"});
    await fill("Votre question","Nouvelle question");assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);
    assert.ok(calls.every(call => !call.body || call.path.endsWith("/copilot/query")));
  } finally {await act(async () => root.unmount());}
});

test("DOM: damaged or relabelled evidence stays hidden; old institute/token results cannot return",async () => {
  setAccessToken(token());let resolveRead:(value:Response)=>void = () => {};
  globalThis.fetch = async (url) => String(url).endsWith("/capabilities") ? reply(discovery()) : new Promise<Response>(resolve => {resolveRead=resolve;});
  const root = createRoot(document.getElementById("root")!);
  try {
    await render(root);await settle();await fill("Consultation","STOCK_READ");await fill("Votre question","Consulter les stocks enregistres");
    const button = Array.from(document.querySelectorAll("button")).find(row => row.textContent === "Consulter")!;
    await act(async () => button.click());
    setAccessToken(token("other"));await render(root,"other");await settle();
    await act(async () => resolveRead(reply(await answer("STOCK_READ",stock()))));
    assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);
    setAccessToken(token());await render(root);await settle();
    globalThis.fetch = async () => {const value=await answer("STOCK_READ",stock());value.evidence.fingerprint="0".repeat(64);return reply(value);};
    await fill("Consultation","STOCK_READ");await fill("Votre question","Consulter les stocks enregistres");await click("Consulter");
    assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);assert.ok(document.querySelector('[role="alert"]'));
  } finally {await act(async () => root.unmount());}
});

test("response gate: owned typed source, clocks, coverage/action boundaries and hash are required",async () => {
  const valid = await answer("CLIENT_READ",customer());
  assert.ok(await validReadResponse(valid,"own","CLIENT_READ",{customer_id:"customer"}));
  for (const change of [{capability:"STOCK_READ"},{actions:[{execute:true}]},{framework:"custom-router"}]) assert.equal(await validReadResponse({...valid,...change},"own","CLIENT_READ",{customer_id:"customer"}),false);
  assert.equal(await validReadResponse(await answer("CLIENT_READ",{...customer(),phone:"PRIVATE"}),"own","CLIENT_READ",{customer_id:"customer"}),false);
  assert.equal(await validReadResponse(valid,"other","CLIENT_READ",{customer_id:"customer"}),false);
  assert.equal(await validReadResponse(valid,"own","CLIENT_READ",{customer_id:"wrong"}),false);
  const damaged = structuredClone(valid);damaged.evidence.read_completed_at="2026-10-09T10:00:00.123455Z";
  const {fingerprint,...payload}=damaged.evidence;damaged.evidence.fingerprint=await hash(payload);
  assert.equal(await validReadResponse(damaged,"own","CLIENT_READ",{customer_id:"customer"}),false);
  assert.ok(validReadDiscovery(discovery("accueil"),"accueil"));assert.equal(validReadDiscovery(discovery(),"accueil"),false);
  assert.ok(await validReadResponse(await answer("PLANNING_READ",{generated_at:clock,rows:[{employee_id:"employee",employee_status:"available",sessions:[]}]}),"own","PLANNING_READ",{}));
  const slot = {employee_id:"employee",institute_id:"own",available_from:null,available_until:null,reason:"capacity_unknown",blocking_session_id:null,blocking_appointment_id:null,blocking_resource_id:null,blocking_absence_id:null};
  const gaps = {captured_at:clock,rows:[{employee_id:"employee",institute_id:"own",service_id:"service",available:false,current_slot:slot,upcoming_slots:[]}],basis:"current_scheduling_engine_windows",complete_work_hours:false,booking_authorized:false};
  assert.ok(await validReadResponse(await answer("PLANNING_GAPS",gaps),"own","PLANNING_GAPS",{service_id:"service"}));
  assert.equal(await validReadResponse(await answer("PLANNING_GAPS",{...gaps,booking_authorized:true}),"own","PLANNING_GAPS",{service_id:"service"}),false);
});

test("CRM summary: absent policy remains explicit and rehashed wrong source is rejected",async () => {
  const profile = {institute_id:"own",customer_id:"customer",captured_at:clock,customer:{institute_id:"own",customer_id:"customer",created_at:clock},policy_original:null,undated_paid_tickets:0,future_paid_tickets:0,segment:null,unavailable_reason:"policy_absent",complete_customer_history:false};
  assert.ok(await validReadResponse(await answer("CLIENT_SUMMARY",profile),"own","CLIENT_SUMMARY",{customer_id:"customer"}));
  for (const change of [{customer_id:"foreign"},{captured_at:"2026-10-09T10:00:00.123455Z"},{unavailable_reason:null},{phone:"PRIVATE"},{complete_customer_history:true}]) {
    assert.equal(await validReadResponse(await answer("CLIENT_SUMMARY",{...profile,...change}),"own","CLIENT_SUMMARY",{customer_id:"customer"}),false);
  }
  setAccessToken(token());
  globalThis.fetch = async (url,init) => {
    if (String(url).endsWith("/capabilities")) return reply(discovery());
    if (String(url).includes("/customers/")) return reply([{id:"customer",institute_id:"own",display_name:"Cliente",phone:null,created_at:clock}]);
    assert.deepEqual(JSON.parse(init!.body as string).ui_context,{customer_id:"customer"});
    return reply(await answer("CLIENT_SUMMARY",profile));
  };
  const root = createRoot(document.getElementById("root")!);
  try {
    await render(root);await settle();await fill("Consultation","CLIENT_SUMMARY");
    await fill("Rechercher une cliente","Cliente");await click("Rechercher les clientes");await fill("Cliente","customer");
    await fill("Votre question","Resumer le profil CRM cliente");await click("Consulter");
    assert.match(document.body.textContent!,/Politique CRM non configurée/);
    assert.match(document.body.textContent!,/historique complet/);
    assert.equal(document.querySelectorAll("tbody tr").length,0);
  } finally {await act(async () => root.unmount());}
});

test("rebooking: original due rule, active bookings and authority refusals remain bound",async () => {
  const rule = {trigger:"rebooking",enabled:true,offset_us:"1"};
  const candidate = {institute_id:"own",customer_id:"customer",policy_original_id:"policy",rule,source:{institute_id:"own",customer_id:"customer",source_id:"care",source_kind:"care_episode",occurred_at:"2026-10-09T10:00:00.123455Z",expires_at:null,remaining:null},due_at:clock,valid_until:null,captured_at:clock,state:"due",external_message_sent:false,delivery_authorized:false};
  const source = {institute_id:"own",customer_id:"customer",captured_at:clock,policy_original_id:"policy",policy_original_digest:"a".repeat(64),rule,candidate,active_bookings:[],invalid_booking_count:0,diagnostics:{},review:"available",complete_customer_history:false,external_message_sent:false,delivery_authorized:false,execution_authorized:false};
  const check = async (value:unknown)=>validReadResponse(await answer("CLIENT_REBOOKING_OPPORTUNITIES",value),"own","CLIENT_REBOOKING_OPPORTUNITIES",{customer_id:"customer"});
  assert.ok(await check(source));
  const booking={appointment_id:"booking",service_id:"service",start_at:clock,end_at:"2026-10-09T11:00:00Z",status:"confirmed"};
  assert.ok(await check({...source,active_bookings:[booking],review:"already_booked"}));
  for (const change of [{execution_authorized:true},{delivery_authorized:true},{external_message_sent:true},{customer_id:"foreign"},{active_bookings:[booking]},{candidate:{...candidate,customer_id:"foreign"}},{candidate:{...candidate,due_at:"2026-10-09T10:00:00.123455Z"}},{rule:{...rule,enabled:false}},{diagnostics:{birthday_unavailable:1}},{active_bookings:[{...booking,end_at:clock}]}])assert.equal(await check({...source,...change}),false);
  const unavailable={...source,policy_original_id:null,policy_original_digest:null,rule:null,candidate:null,review:"unavailable",diagnostics:{policy_absent:1,care_unavailable:1}};
  assert.ok(await check(unavailable));
  setAccessToken(token());
  globalThis.fetch = async (url,init)=>String(url).endsWith("/capabilities") ? reply(discovery()) : String(url).includes("/customers/") ? reply([{id:"customer",institute_id:"own",display_name:"Cliente",phone:null,created_at:clock}]) : (assert.deepEqual(JSON.parse(init!.body as string).ui_context,{customer_id:"customer"}),reply(await answer("CLIENT_REBOOKING_OPPORTUNITIES",{...source,active_bookings:[booking],review:"already_booked"})));
  const root=createRoot(document.getElementById("root")!);
  try {
    await render(root);await settle();await fill("Consultation","CLIENT_REBOOKING_OPPORTUNITIES");await fill("Rechercher une cliente","Cliente");await click("Rechercher les clientes");await fill("Cliente","customer");
    await fill("Votre question","Examiner les opportunites de reprise rendez-vous");await click("Consulter");
    assert.match(document.body.textContent!,/Rendez-vous actif déjà enregistré/);assert.match(document.body.textContent!,/n’autorise aucune réservation/);
  } finally {await act(async()=>root.unmount());}
});

test("capacity binds selected completed day and preserves unavailable physical authority",async()=>{
  const day="2026-10-08";
  const source={window:{institute_id:"own",start:"2026-10-07T22:00:00Z",end:"2026-10-08T22:00:00Z",captured_at:clock},day,timezone:"Europe/Zurich",basis:"declared_work_intersected_with_finalized_recorded_activity",page:{offset:0,limit:20,total:0},rows:[],employee_count:0,employees_without_usable_hours:0,employees_with_uncertain_activity:0,known_declared_union_duration_us:"0",known_covered_busy_duration_us:"0",known_outside_declared_work_duration_us:"0",recorded_unoccupied_duration_us:null,recorded_utilization_ratio:null,complete_attendance:false,complete_activity:false,physical_unused_capacity:null,bookable_capacity:null,estimated_value:null};
  const check=async(v:unknown,selected=day)=>validReadResponse(await answer("EMPLOYEE_CAPACITY",v),"own","EMPLOYEE_CAPACITY",{day:selected});
  assert.ok(await check(source));assert.equal(await check(source,"2026-10-07"),false);
  for(const change of [{bookable_capacity:"1"},{complete_attendance:true},{known_declared_union_duration_us:"1"},{timezone:"Invalid/Zone"},{window:{...source.window,captured_at:"2026-10-09T10:00:00.123455Z"}}])assert.equal(await check({...source,...change}),false);
  setAccessToken(token());globalThis.fetch=async(url,init)=>String(url).endsWith("/capabilities") ? reply(discovery()) : (assert.deepEqual(JSON.parse(init!.body as string).ui_context,{day}),reply(await answer("EMPLOYEE_CAPACITY",source)));
  const root=createRoot(document.getElementById("root")!);
  try{await render(root);await settle();await fill("Consultation","EMPLOYEE_CAPACITY");await fill("Journée terminée",day);await fill("Votre question","Mesurer la capacite enregistree des collaboratrices");await click("Consulter");assert.match(document.body.textContent!,/capacité réservable ne sont pas établies/);assert.match(document.body.textContent!,/0 h 00 min 00 s/);}finally{await act(async()=>root.unmount());}
});

test("conflict controls explicitly select one owned employee or loaded resource and discard edited evidence",async()=>{
  const day="2026-10-08",calls:{path:string;body:any}[]=[];
  const base={institute_id:"own",day,captured_at:clock,start_at:"2026-10-07T22:00:00Z",end_at:"2026-10-08T22:00:00Z",source_digest:"a".repeat(64),source_count:0,invalid_source_count:0,overlap_count:0,overlaps:[],page_limit:50,physical_activity_proven:false};
  const employee={...base,employee_id:"employee",overdue_open_source_count:0,basis:"current_recorded_employee_commitments_half_open",resource_conflicts_covered:false};
  const resource={...base,resource_id:"room",resource_status:"maintenance",overdue_unreleased_source_count:0,basis:"current_unreleased_resource_reservations_half_open",complete_institute_conflict_coverage:false,booking_authorized:false};
  assert.ok(await validReadResponse(await answer("PLANNING_CONFLICTS",employee),"own","PLANNING_CONFLICTS",{day,employee_id:"employee"},"Europe/Zurich"));
  assert.equal(await validReadResponse(await answer("PLANNING_CONFLICTS",resource),"own","PLANNING_CONFLICTS",{day,resource_id:"room"},"UTC"),false);
  assert.equal(await validReadResponse(await answer("PLANNING_CONFLICTS",resource),"own","PLANNING_CONFLICTS",{day,employee_id:"employee",resource_id:"room"},"Europe/Zurich"),false);
  setAccessToken(token());
  globalThis.fetch=async(url,init)=>{
    const path=String(url),body=init?.body ? JSON.parse(init.body as string) : undefined;calls.push({path,body});
    if(path.endsWith("/capabilities"))return reply(discovery());
    if(path.includes("/resources/"))return reply([{id:"room",institute_id:"own",name:"Cabine",kind:"room",capabilities:[],status:"maintenance"}]);
    return reply(await answer("PLANNING_CONFLICTS",body.ui_context.resource_id ? resource : employee));
  };
  const root=createRoot(document.getElementById("root")!);
  try{
    await render(root);await settle();assert.equal(calls.length,1);
    await fill("Consultation","PLANNING_CONFLICTS");await fill("Votre question","Examiner les conflits du planning");
    assert.equal(Array.from(document.querySelectorAll("button")).find(b=>b.textContent==="Consulter")!.disabled,true);
    await fill("Journée à examiner",day);await fill("Collaboratrice ou ressource","employee:employee");await click("Consulter");
    assert.deepEqual(calls.at(-1)!.body.ui_context,{day,employee_id:"employee"});assert.match(document.body.textContent!,/0 conflit/);
    await click("Lire les ressources");assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);
    await fill("Collaboratrice ou ressource","resource:room");await click("Consulter");
    assert.deepEqual(calls.at(-1)!.body.ui_context,{day,resource_id:"room"});assert.match(document.body.textContent!,/Cabine/);
    await fill("Journée à examiner","2026-10-07");assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);
    assert.ok(calls.filter(c=>c.body).every(c=>c.path.endsWith("/copilot/query")));
  }finally{await act(async()=>root.unmount());}
});

test("revenue controls bind institute midnight period and keep mixed currencies separate",async()=>{
  const period={start:"2026-10-07T22:00:00.000Z",end:"2026-10-08T22:00:00.000Z"};
  const amounts=(currency:string|null,minor:string)=>({currency,source_count:1,known_amount_count:1,missing_amount_count:0,invalid_amount_count:0,known_gross_minor:minor,complete_gross_minor:currency ? minor : null,average_minor:currency ? {numerator:minor,denominator:"1"} : null});
  const source={window:{institute_id:"own",...period,captured_at:clock},basis:"recorded_paid_tickets_and_active_invoice_lines",ticket_count:3,ticket_amounts:[amounts("CHF","1200"),amounts("EUR","800"),amounts(null,"500")],active_line_count:0,service_mix:[],tickets_without_active_lines:3,tickets_with_unknown_category:0,care_tickets:0,care_and_retail_tickets:0,recorded_retail_attach_ratio:null,institute_undated_paid_tickets:1,complete_sales_history:false,settlement_confirmed:false,projected_revenue:null};
  const check=async(v:unknown,p=period)=>validReadResponse(await answer("REVENUE_SUMMARY",v),"own","REVENUE_SUMMARY",p);
  assert.ok(await check(source));assert.equal(await check(source,{...period,end:clock}),false);
  for(const change of [{settlement_confirmed:true},{complete_sales_history:true},{projected_revenue:"2500"},{ticket_count:2},{ticket_amounts:[amounts(null,"500"),amounts(null,"500"),amounts(null,"500")]},{window:{...source.window,captured_at:"2026-10-09T10:00:00.123455Z"}}])assert.equal(await check({...source,...change}),false);
  setAccessToken(token());const queries:any[]=[];
  globalThis.fetch=async(url,init)=>{
    if(String(url).endsWith("/capabilities"))return reply(discovery());
    queries.push(JSON.parse(init!.body as string));return reply(await answer("REVENUE_SUMMARY",source));
  };
  const root=createRoot(document.getElementById("root")!);
  try{
    await render(root);await settle();await fill("Consultation","REVENUE_SUMMARY");await fill("Votre question","Consulter les revenus enregistres");
    await fill("Début de période","2026-10-08");await fill("Fin de période exclue","2026-10-09");await click("Consulter");
    assert.deepEqual(queries[0].ui_context,period);
    assert.match(document.body.textContent!,/12.00 CHF/);assert.match(document.body.textContent!,/8.00 EUR/);assert.match(document.body.textContent!,/Devise inconnue/);
    assert.match(document.body.textContent!,/Total complet : non établi/);
    await fill("Fin de période exclue","2026-10-08");assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);await click("Consulter");assert.equal(queries.length,1);assert.match(document.querySelector('[role="alert"]')!.textContent!,/postérieure/);
  }finally{await act(async()=>root.unmount());}
});

test("loss consultation binds selected period and shows uncertainty without a financial loss",async()=>{
  const period={start:"2026-10-07T22:00:00.000Z",end:"2026-10-08T22:00:00.000Z"},window={institute_id:"own",...period,captured_at:clock};
  const source={institute_id:"own",captured_at:clock,bookings:{window,source_digest:"a".repeat(64),cancelled_count:2,no_show_count:1,unpriced_count:3,institute_terminal_bookings_without_closure_event:1},walk_ins:{window,source_digest:"b".repeat(64),retained_terms_count:0,legacy_unpriced_count:1,retained_amounts:[]},causal_loss_proven:false,complete_history:false,financial_loss:null,basis:"recorded_closure_events_not_causal_financial_loss"};
  assert.ok(await validReadResponse(await answer("REVENUE_LOSS_ANALYSIS",source),"own","REVENUE_LOSS_ANALYSIS",period));
  assert.equal(await validReadResponse(await answer("REVENUE_LOSS_ANALYSIS",{...source,financial_loss:"100"}),"own","REVENUE_LOSS_ANALYSIS",period),false);
  setAccessToken(token());const queries:any[]=[];
  globalThis.fetch=async(url,init)=>String(url).endsWith("/capabilities") ? reply(discovery()) : (queries.push(JSON.parse(init!.body as string)),reply(await answer("REVENUE_LOSS_ANALYSIS",source)));
  const root=createRoot(document.getElementById("root")!);
  try{await render(root);await settle();await fill("Consultation","REVENUE_LOSS_ANALYSIS");await fill("Début de période","2026-10-08");await fill("Fin de période exclue","2026-10-09");await fill("Votre question","Examiner les pertes enregistrees");await click("Consulter");assert.deepEqual(queries[0].ui_context,period);assert.match(document.body.textContent!,/2 annulation/);assert.match(document.body.textContent!,/3 événement/);assert.match(document.body.textContent!,/perte financière causale non établis/);await fill("Début de période","2026-10-07");assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);}finally{await act(async()=>root.unmount());}
});

test("DOM: unauthorized presentation or mismatched selected institute makes no request",async () => {
  let calls=0;globalThis.fetch=async () => {calls++;return reply(discovery());};
  const root=createRoot(document.getElementById("root")!);
  try {setAccessToken(token("own","collaboratrice"));await render(root);setAccessToken(token());await render(root,"other");assert.equal(calls,0);assert.equal(document.body.textContent,"");}
  finally {await act(async () => root.unmount());}
});
