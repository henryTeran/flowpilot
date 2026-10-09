import test from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { CopilotPanel } from "../src/components/CopilotPanel";
import { setAccessToken } from "../src/api/session";
import { revenueOriginalFingerprint as hash } from "../src/revenue-scenario-utils";
const dom = new JSDOM("<div id='root'></div>",{ url:"http://localhost" });
Object.assign(globalThis,{ window:dom.window,document:dom.window.document,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true });
const { createRoot } = await import("react-dom/client");
const clock = "2026-10-09T10:00:00.123456Z";
const token = (institute="own",role="responsable_institut") => `h.${Buffer.from(JSON.stringify({sub:"manager",institute_id:institute,role})).toString("base64url")}.s`;
const reply = (value: unknown) => new Response(JSON.stringify(value),{ headers:{"Content-Type":"application/json"} });
const names = ["CLIENT_READ","CLIENT_SUMMARY","CLIENT_REBOOKING_OPPORTUNITIES","PLANNING_READ","PLANNING_GAPS","PLANNING_CONFLICTS","EMPLOYEE_CAPACITY","REVENUE_SUMMARY","REVENUE_LOSS_ANALYSIS","REVENUE_OPPORTUNITIES","STOCK_READ","STOCK_FORECAST"];
const discovery = (role="responsable_institut") => (role === "accueil" ? names.filter(name => ["CLIENT_READ","PLANNING_READ","PLANNING_GAPS","STOCK_READ","STOCK_FORECAST"].includes(name)) : names).map(name => ({name,level:0,permission:"planning_operator",input_schema:{},output_schema:{},application_service:"existing.service",audit:"signed_scope_interaction_id_and_source_digest_no_raw_message",mutates:false}));
const stock = () => ({institute_id:"own",generated_at:clock,starts_at:null,ends_at:null,source:"recorded_stock",coverage:"not_applicable",demands:[],limit:50,offset:0,
  items:Array.from({length:50},(_,index) => ({item_id:`item-${index}`,item_sku:`SKU-${index}`,item_name:`Article ${index}`,category:"cabine",unit:"ml",on_hand:"1.000",threshold:"4.125",at_or_below_threshold:true,threshold_shortfall:"3.125",pending_order_quantity:"2.000",known_demand:"0.000",complete_demand:null,known_demand_shortfall:"3.125",conditional_shortfall_after_all_orders:"1.125"}))});
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


test("DOM: reorder verifies native sources, freezes lost retain response and recovers one original",async()=>{
  sessionStorage.clear();setAccessToken(token());let retained:any=null,lost=true;const calls:{path:string;body:any}[]=[];
  const registrations=["APPOINTMENT_CREATE","APPOINTMENT_MOVE","MARKETING_CAMPAIGN_DRAFT","STOCK_REORDER_PROPOSAL"].map(name=>({name,level:2,permission:"signed_institute_manager",input_schema:{},preview_input_schema:{},output_schema:{},application_service:name==="MARKETING_CAMPAIGN_DRAFT" ? "marketing.campaign_originals.execute_create_only" : name==="STOCK_REORDER_PROPOSAL" ? "inventory.reorders.create" : "base.sensitive_originals.create",audit:"signed_scope_interaction_id_and_source_digest_no_raw_message",effect:name==="MARKETING_CAMPAIGN_DRAFT" ? "retained_draft_only_no_campaign_approval_contact_or_delivery" : name==="STOCK_REORDER_PROPOSAL" ? "retained_reorder_proposal_no_order_contact_payment_receipt_or_stock_write" : "retained_pending_preparation_no_approval_or_execution"}));
  const supplier={id:"supplier",institute_id:"own",actor_id:"manager",created_at:clock,reference:"SUP",name:"Supplier",reason:"Supplier reviewed",idempotency_key:"supplier-key"};
  const item={id:"item-0",institute_id:"own",sku:"SKU-0",name:"Item",category:"cabine",unit:"ml",reorder_threshold:"4.125",on_hand:"1.000",at_or_below_threshold:true,actor_id:"manager",created_at:clock};
  const rows=stock().items.slice(0,1);let preview:any;
  globalThis.fetch=async(url,init)=>{
    const path=String(url),body=init?.body?JSON.parse(init.body as string):undefined;calls.push({path,body});
    if(path.endsWith("/preparation-capabilities"))return reply(registrations);
    if(path.endsWith("/capabilities"))return reply(discovery());
    if(path.includes("/suppliers?"))return reply([supplier]);
    if(path.endsWith("/suppliers/supplier"))return reply(supplier);
    if(path.includes("/items?"))return reply([item]);
    if(path.includes("/outlook?"))return reply({...stock(),items:rows});
    if(path.endsWith("/prepare-preview/reorder")){
      const raw={institute_id:"own",selection:body.ui_context,coverage:"not_applicable",items:rows.map(r=>({item_id:r.item_id,unit:r.unit,on_hand:r.on_hand,threshold:r.threshold,pending_order_quantity:r.pending_order_quantity,known_demand:r.known_demand,complete_demand:null,proposed_quantity:r.known_demand_shortfall})),source_digest:await hash({supplier,demands:[],items:rows}),basis:"original_stock_shortfalls_selected_scenario_and_explicit_pending_assumption_not_supplier_quote",effect:"reorder_proposal_only_no_order_contact_payment_receipt_or_stock_write"};
      preview={...raw,captured_at:clock,state_fingerprint:await hash(raw)};return reply(preview);
    }
    if(path.includes("/reorder-proposal-by-key?"))return reply(retained);
    if(path.endsWith("/reorder-proposals/proposal"))return reply(retained);
    if(path.endsWith("/prepare/reorder")){
      const original={...body.proposal,id:"proposal",institute_id:"own",actor_id:"manager",created_at:"2026-10-09T10:00:01Z",preview};retained={original,fingerprint:await hash(original)};
      if(lost){lost=false;throw Error("Lost response");}return reply(retained);
    }
    throw Error(`Unexpected ${path}`);
  };
  const root=createRoot(document.getElementById("root")!);
  try{
    await render(root);await settle();await click("Pr\u00e9parer un r\u00e9approvisionnement");
    await fill("Votre demande de r\u00e9approvisionnement","Preparer une proposition de reapprovisionnement");
    await click("V\u00e9rifier le r\u00e9approvisionnement");assert.equal(calls.filter(c=>c.body).length,0);
    await click("Lire les fournisseurs");await fill("Fournisseur s\u00e9lectionn\u00e9","supplier");await click("Lire les articles");
    const checkbox=document.querySelector('input[type="checkbox"]') as HTMLInputElement;await act(async()=>checkbox.click());
    await fill("Hypoth\u00e8se des commandes en attente","ignore_pending_orders");await click("V\u00e9rifier le r\u00e9approvisionnement");
    assert.ok(document.querySelector('[aria-label="R\u00e9approvisionnement v\u00e9rifi\u00e9"]'));assert.match(document.body.textContent!,/3\.125/);
    await fill("Motif du r\u00e9approvisionnement","Proposition relue");await click("Conserver la proposition de r\u00e9approvisionnement");
    assert.ok(document.querySelector('[aria-label="Demande de r\u00e9approvisionnement conserv\u00e9e"]'));
    await click("Consulter avec le Copilot");await click("Pr\u00e9parer un r\u00e9approvisionnement");await click("Reprendre le r\u00e9approvisionnement");
    assert.ok(document.querySelector('[aria-label="R\u00e9approvisionnement conserv\u00e9"]'));assert.equal(calls.filter(c=>c.path.endsWith("/prepare/reorder")).length,1);assert.ok(calls.some(c=>c.path.endsWith("/reorder-proposals/proposal")));
    assert.equal(calls.filter(c=>c.body).length,2);assert.match(document.body.textContent!,/aucun devis fournisseur/i);
  }finally{await act(async()=>root.unmount());}
});
