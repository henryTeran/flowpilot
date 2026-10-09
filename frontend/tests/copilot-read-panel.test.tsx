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

test("DOM: unauthorized presentation or mismatched selected institute makes no request",async () => {
  let calls=0;globalThis.fetch=async () => {calls++;return reply(discovery());};
  const root=createRoot(document.getElementById("root")!);
  try {setAccessToken(token("own","collaboratrice"));await render(root);setAccessToken(token());await render(root,"other");assert.equal(calls,0);assert.equal(document.body.textContent,"");}
  finally {await act(async () => root.unmount());}
});
