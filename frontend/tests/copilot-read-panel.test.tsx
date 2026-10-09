import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { CopilotPanel } from "../src/components/CopilotPanel";
import { setAccessToken } from "../src/api/session";
import { revenueOriginalFingerprint as hash } from "../src/revenue-scenario-utils";
import { validReadResponse, validReadDiscovery } from "../src/copilot-read-utils";
import {canonicalCreationSelection} from "../src/copilot-creation-utils";
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

test("opportunity responses bind explicit capacity source, capture, action boundary and canonical hash",async()=>{
  const selection={opportunity_source:"capacity" as const,service_id:"service",horizon_end:"2026-10-09T11:00:00Z"};
  const source={institute_id:"own",service_id:"service",captured_at:clock,horizon_end:selection.horizon_end,opportunity:null,unavailable_reason:"capacity_unknown"};
  const response=await answer("REVENUE_OPPORTUNITIES",source);
  assert.ok(await validReadResponse(response,"own","REVENUE_OPPORTUNITIES",selection));
  assert.equal(await validReadResponse(response,"own","REVENUE_OPPORTUNITIES",{opportunity_source:"rebooking"}),false);
  assert.equal(await validReadResponse(response,"own","REVENUE_OPPORTUNITIES",{...selection,customer_id:"customer"}),false);
  assert.equal(await validReadResponse({...response,actions:[{execute:true}]},"own","REVENUE_OPPORTUNITIES",selection),false);
  assert.equal(await validReadResponse({...response,evidence:{...response.evidence,fingerprint:"0".repeat(64)}},"own","REVENUE_OPPORTUNITIES",selection),false);
  assert.equal(await validReadResponse(await answer("REVENUE_OPPORTUNITIES",{...source,captured_at:"2026-10-09T10:00:00.123455Z"}),"own","REVENUE_OPPORTUNITIES",selection),false);
});

test("opportunity form sends exclusive source selections and clears evidence when switching",async()=>{
  const period={start:"2026-10-07T22:00:00.000Z",end:"2026-10-08T22:00:00.000Z"},window={institute_id:"own",...period,captured_at:clock};
  const returns={institute_id:"own",captured_at:clock,source_digest:"a".repeat(64),source:"observed_care_declared_rebooking_rule",total_candidates:0,examined_customers:0,already_booked_customers:0,scheduled_customers:0,disabled_customers:0,no_candidate_customers:0,diagnostics:{},candidates:[],page_limit:20,estimated_value:null,delivery_authorized:false,action_executed:false,complete_customer_history:false};
  const follow={institute_id:"own",captured_at:clock,source:"recorded_closure_follow_up",bookings:{window,source_digest:"a".repeat(64),cancelled_count:0,no_show_count:0,unpriced_count:0,institute_terminal_bookings_without_closure_event:0},walk_ins:{window,source_digest:"b".repeat(64),retained_terms_count:0,legacy_unpriced_count:0,retained_amounts:[]},booking_total:0,walk_in_total:0,booking_candidates:[],walk_in_candidates:[],page_limit_per_source:20,estimated_recovered_revenue:null,causal_loss_proven:false,delivery_authorized:false,action_executed:false,complete_history:false};
  setAccessToken(token());const queries:any[]=[];
  globalThis.fetch=async(url,init)=>{
    if(String(url).endsWith("/capabilities"))return reply(discovery());
    const body=JSON.parse(init!.body as string);queries.push(body);const selected=body.ui_context;
    return reply(await answer("REVENUE_OPPORTUNITIES",selected.opportunity_source==="rebooking" ? returns : selected.opportunity_source==="closures" ? follow : {institute_id:"own",service_id:"service",captured_at:clock,horizon_end:selected.horizon_end,opportunity:null,unavailable_reason:"capacity_unknown"}));
  };
  const root=createRoot(document.getElementById("root")!);
  try{
    await render(root);await settle();await fill("Consultation","REVENUE_OPPORTUNITIES");await fill("Votre question","Examiner les opportunites");
    await click("Consulter");assert.equal(queries.length,0);assert.match(document.querySelector('[role="alert"]')!.textContent!,/Choisissez une source/);
    await fill("Source des opportunités","capacity");await fill("Prestation sélectionnée","service");await fill("Horizon local","2026-10-09T13:00");await click("Consulter");
    assert.deepEqual(queries[0].ui_context,{opportunity_source:"capacity",service_id:"service",horizon_end:"2026-10-09T11:00:00.000Z"});assert.match(document.body.textContent!,/Capacité non établie/);
    await fill("Source des opportunités","rebooking");assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);await click("Consulter");assert.deepEqual(queries[1].ui_context,{opportunity_source:"rebooking"});assert.match(document.body.textContent!,/Aucun message envoyé/);
    await fill("Source des opportunités","closures");await fill("Début de période","2026-10-08");await fill("Fin de période exclue","2026-10-09");await click("Consulter");assert.deepEqual(queries[2].ui_context,{opportunity_source:"closures",...period});assert.match(document.body.textContent!,/Aucun contact effectué/);
    await fill("Source des opportunités","capacity");assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);await click("Consulter");assert.equal(queries.length,3);assert.match(document.querySelector('[role="alert"]')!.textContent!,/prestation/);
  }finally{await act(async()=>root.unmount());}
});

test("local opportunity horizon rejects skipped hours and requires an explicit repeated occurrence",async()=>{
  setAccessToken(token());const queries:any[]=[];
  globalThis.fetch=async(url,init)=>{
    if(String(url).endsWith("/capabilities"))return reply(discovery());
    const body=JSON.parse(init!.body as string);queries.push(body);
    return reply(await answer("REVENUE_OPPORTUNITIES",{institute_id:"own",service_id:"service",captured_at:clock,horizon_end:body.ui_context.horizon_end,opportunity:null,unavailable_reason:"capacity_unknown"}));
  };
  const root=createRoot(document.getElementById("root")!);
  try{
    await render(root);await settle();await fill("Consultation","REVENUE_OPPORTUNITIES");await fill("Source des opportunités","capacity");await fill("Prestation sélectionnée","service");await fill("Votre question","Examiner les opportunites");
    await fill("Horizon local","2027-03-28T02:30");await click("Consulter");assert.equal(queries.length,0);assert.match(document.querySelector('[role="alert"]')!.textContent!,/heure d’horizon valide/);
    await fill("Horizon local","2026-10-25T02:30");await click("Consulter");assert.equal(queries.length,0);
    const options=Array.from(document.querySelectorAll("label")).find(r=>r.textContent?.startsWith("Occurrence de l’heure répétée"))!.querySelectorAll("option");
    assert.equal(options.length,3);assert.equal(options[1].value,"2026-10-25T00:30:00.000Z");assert.equal(options[2].value,"2026-10-25T01:30:00.000Z");
    await fill("Occurrence de l’heure répétée",options[2].value);await click("Consulter");assert.equal(queries[0].ui_context.horizon_end,"2026-10-25T01:30:00.000Z");
    await fill("Horizon local","2027-10-31T02:30");await click("Consulter");assert.equal(queries.length,1);
    const select=Array.from(document.querySelectorAll("label")).find(r=>r.textContent?.startsWith("Occurrence de l’heure répétée"))!.querySelector("select")!;assert.equal(select.value,"");
  }finally{await act(async()=>root.unmount());}
});

test("forecast controls retain multiple selected services, original quantities and explicit missing norms",async()=>{
  setAccessToken(token());const calls:{path:string;body:any}[]=[];let changed=false,wrongQuantity=false;
  const original={id:"recipe",institute_id:"own",service_id:"service",revision:1,base_revision:0,enabled:true,entries:[{item_id:"item-0",quantity:"1.250",unit:"ml"}],reason:"Norme originale",actor_id:"manager",idempotency_key:"original",created_at:clock};
  globalThis.fetch=async(url,init)=>{
    const path=String(url),body=init?.body ? JSON.parse(init.body as string) : undefined;calls.push({path,body});
    if(path.endsWith("/capabilities"))return reply(discovery());
    if(path.includes("/services/service/recipes"))return reply([original]);
    if(path.endsWith("/recipes/recipe"))return reply(changed ? {...original,reason:"Changed original"} : original);
    assert.ok(path.endsWith("/copilot/query"));const scenario=body.ui_context.scenario,complete=scenario.demands.every((d:any)=>d.recipe_id!==null);
    const item={...stock().items[0],known_demand:wrongQuantity ? "4.000" : "3.750",complete_demand:complete ? wrongQuantity ? "4.000" : "3.750" : null,known_demand_shortfall:wrongQuantity ? "7.125" : "6.875",conditional_shortfall_after_all_orders:wrongQuantity ? "5.125" : "4.875"};
    const response=await answer("STOCK_FORECAST",{...stock(),...scenario,source:"explicit_service_volume_scenario",coverage:complete ? "complete_selected_norms" : "partial_selected_norms",demands:scenario.demands.map((d:any)=>({...d,service_name:d.service_id==="service" ? "Soin" : "Autre soin",recipe_revision:d.recipe_id ? 1 : null,state:d.recipe_id ? "enabled" : "missing_selected_norm"})),items:[item]});
    assert.ok(await validReadResponse(response,"own","STOCK_FORECAST",body.ui_context));
    return reply(response);
  };
  const root=createRoot(document.getElementById("root")!);
  try{
    await act(async()=>root.render(<CopilotPanel institute="own" timezone="Europe/Zurich" employees={[]} services={[{id:"service",name:"Soin",status:"active"},{id:"other",name:"Autre soin",status:"active"}] as any}/>));await settle();
    await fill("Consultation","STOCK_FORECAST");await fill("Votre question","Projeter les besoins de stock");await click("Consulter");assert.equal(calls.length,1);assert.match(document.querySelector('[role="alert"]')!.textContent!,/volumes entiers/);
    await fill("Premier jour du scénario","2026-10-25");await fill("Fin du scénario exclue","2026-10-26");await fill("Prestation du scénario","service");assert.equal(calls.length,1);
    await click("Lire les normes originales");await fill("Norme du scénario","recipe");await click("Ajouter au scénario");await fill("Volume de Soin","3");
    await fill("Prestation du scénario","other");await fill("Norme du scénario","missing");await click("Ajouter au scénario");await fill("Volume de Autre soin","2");await click("Consulter");
    assert.deepEqual(calls.at(-1)!.body.ui_context,{scenario:{starts_at:"2026-10-24T22:00:00.000Z",ends_at:"2026-10-25T23:00:00.000Z",demands:[{service_id:"service",recipe_id:"recipe",quantity:3},{service_id:"other",recipe_id:null,quantity:2}]}});
    assert.match(document.body.textContent!,/Couverture partielle/);assert.match(document.body.textContent!,/Aucune commande ni consommation physique créée/);assert.equal(document.querySelectorAll("tbody tr").length,1);assert.match(document.querySelector("tbody")!.textContent!,/3,75|3\.75/);
    await fill("Volume de Soin","0");assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);const before=calls.length;await click("Consulter");assert.equal(calls.length,before);
    await fill("Volume de Soin","3");await click("Retirer Autre soin du scénario");await click("Consulter");assert.match(document.body.textContent!,/toutes les normes choisies sont connues/);
    changed=true;const queries=calls.filter(c=>c.body).length;await click("Consulter");assert.equal(calls.filter(c=>c.body).length,queries);assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);
    changed=false;wrongQuantity=true;await click("Consulter");assert.equal(document.querySelector('[aria-label="Réponse du Copilot"]'),null);assert.ok(document.querySelector('[role="alert"]'));
    assert.ok(calls.every(c=>!c.body || c.path.endsWith("/copilot/query")));
  }finally{await act(async()=>root.unmount());}
});

test("creation form uses official preview with explicit owned customer and repeated local-hour selection",async()=>{
  setAccessToken(token());const calls:{path:string;body:any}[]=[];let damaged=false;
  const registrations=Object.entries({APPOINTMENT_CREATE:["base.sensitive_originals.create","retained_pending_preparation_no_approval_or_execution"],APPOINTMENT_MOVE:["base.sensitive_originals.create","retained_pending_preparation_no_approval_or_execution"],MARKETING_CAMPAIGN_DRAFT:["marketing.campaign_originals.execute_create_only","retained_draft_only_no_campaign_approval_contact_or_delivery"],STOCK_REORDER_PROPOSAL:["inventory.reorders.create","retained_reorder_proposal_no_order_contact_payment_receipt_or_stock_write"]}).map(([name,[application_service,effect]])=>({name,level:2,permission:"signed_institute_manager",input_schema:{},preview_input_schema:{},output_schema:{},application_service,effect,audit:"signed_scope_interaction_id_and_source_digest_no_raw_message"}));
  globalThis.fetch=async(url,init)=>{
    const path=String(url),body=init?.body ? JSON.parse(init.body as string) : undefined;calls.push({path,body});
    if(path.endsWith("/preparation-capabilities"))return reply(registrations);
    if(path.endsWith("/capabilities"))return reply(discovery());
    if(path.includes("/customers/"))return reply([{id:"customer",institute_id:"own",display_name:"Cliente revue",phone:"+33999000000",created_at:clock}]);
    assert.ok(path.endsWith("/copilot/prepare-preview"));const selection=canonicalCreationSelection({...body.ui_context,...(damaged ? {notes:null} : {})}),end_time="2026-10-25T01:40:00Z",resource_ids=["room"];
    return reply({principal:{actor_id:"manager",institute_id:"own",role:"responsable_institut"},capability:{name:"APPOINTMENT_CREATE",prepare_level:2,roles:["responsable_institut"],application_service:"appointments.service.preview_creation",approval:"explicit_human_approval_of_exact_retained_operation_required",execution_registered:true},selection,captured_at:clock,end_time,resource_ids,state_fingerprint:await hash({institute_id:"own",selection,end_time:end_time.replace("Z","+00:00"),resource_ids}),basis:"exact_creation_terms_and_current_eligible_interval_resources_not_full_database_digest",effect:"creation_preview_only_no_reservation_approval_or_execution"});
  };
  const root=createRoot(document.getElementById("root")!);
  try{
    await render(root);await settle();await click("Créer un rendez-vous avec le Copilot");assert.equal(calls.length,2);assert.equal(calls.filter(c=>c.body).length,0);
    await fill("Votre demande de création","Preparer la creation du rendez-vous");await fill("Collaboratrice sélectionnée","employee");await fill("Prestation sélectionnée","service");await fill("Nom revu pour le rendez-vous","Cliente saisie");
    await fill("Début local du rendez-vous","2027-03-28T02:30");await click("Vérifier les termes de création");assert.equal(calls.filter(c=>c.body).length,0);assert.match(document.querySelector('[role="alert"]')!.textContent!,/heure locale valide/);
    await fill("Début local du rendez-vous","2026-10-25T02:30");await click("Vérifier les termes de création");assert.equal(calls.filter(c=>c.body).length,0);
    await fill("Occurrence de l’heure répétée","2026-10-25T01:30:00.000Z");await fill("Rechercher une cliente","Cliente");await click("Rechercher les clientes");await fill("Cliente enregistrée","customer");await fill("Notes revues","Note revue");await click("Vérifier les termes de création");
    assert.deepEqual(calls.at(-1)!.body,{message:"Preparer la creation du rendez-vous",ui_context:{employee_id:"employee",service_id:"service",customer_id:"customer",customer_name:"Cliente revue",phone:"+33999000000",notes:"Note revue",start_time:"2026-10-25T01:30:00.000Z"}});
    assert.ok(document.querySelector('[aria-label="Termes de création vérifiés"]'));assert.match(document.body.textContent!,/aucune réservation effectuée/);assert.equal(document.querySelectorAll("button").length>0,true);
    await fill("Notes revues","Note corrigée");assert.equal(document.querySelector('[aria-label="Termes de création vérifiés"]'),null);damaged=true;await click("Vérifier les termes de création");assert.equal(document.querySelector('[aria-label="Termes de création vérifiés"]'),null);assert.ok(document.querySelector('[role="alert"]'));
    assert.ok(calls.every(c=>!c.body || c.path.endsWith("/copilot/prepare-preview")));assert.ok(!Array.from(document.querySelectorAll("button")).some(b=>/Approuver|Exécuter/.test(b.textContent!)));
    await click("Consulter avec le Copilot");await fill("Consultation","STOCK_READ");assert.equal(document.querySelector('[aria-label="Termes de création vérifiés"]'),null);
  }finally{await act(async()=>root.unmount());}
});

test("DOM: unauthorized presentation or mismatched selected institute makes no request",async () => {
  let calls=0;globalThis.fetch=async () => {calls++;return reply(discovery());};
  const root=createRoot(document.getElementById("root")!);
  try {setAccessToken(token("own","collaboratrice"));await render(root);setAccessToken(token());await render(root,"other");assert.equal(calls,0);assert.equal(document.body.textContent,"");}
  finally {await act(async () => root.unmount());}
});
