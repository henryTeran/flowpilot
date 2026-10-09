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

test("DOM: marketing reads catalogues explicitly and refuses absent source selection without a POST",async()=>{
  sessionStorage.clear();setAccessToken(token());const calls:{path:string;body:any}[]=[];
  const registrations=["APPOINTMENT_CREATE","APPOINTMENT_MOVE","MARKETING_CAMPAIGN_DRAFT","STOCK_REORDER_PROPOSAL"].map(name=>({name,level:2,permission:"signed_institute_manager",input_schema:{},preview_input_schema:{},output_schema:{},application_service:name==="MARKETING_CAMPAIGN_DRAFT" ? "marketing.campaign_originals.execute_create_only" : name==="STOCK_REORDER_PROPOSAL" ? "inventory.reorders.create" : "base.sensitive_originals.create",audit:"signed_scope_interaction_id_and_source_digest_no_raw_message",effect:name==="MARKETING_CAMPAIGN_DRAFT" ? "retained_draft_only_no_campaign_approval_contact_or_delivery" : name==="STOCK_REORDER_PROPOSAL" ? "retained_reorder_proposal_no_order_contact_payment_receipt_or_stock_write" : "retained_pending_preparation_no_approval_or_execution"}));
  globalThis.fetch=async(url,init)=>{const path=String(url),body=init?.body ? JSON.parse(init.body as string) : undefined;calls.push({path,body});assert.equal(body,undefined);if(path.endsWith("/preparation-capabilities"))return reply(registrations);if(path.endsWith("/capabilities"))return reply(discovery());if(path.includes("/audience-captures?")||path.includes("/templates?"))return reply({institute_id:"own",total:0,offset:0,limit:20,items:[]});throw Error("Unexpected domain read");};
  const root=createRoot(document.getElementById("root")!);try{await render(root);await settle();await click("Pr\u00e9parer un brouillon marketing");assert.equal(calls.length,2);await fill("Votre demande de brouillon","Preparer un brouillon marketing");await click("V\u00e9rifier le brouillon marketing");assert.equal(calls.length,2);assert.match(document.body.textContent!,/Choisissez une audience/);await click("Lire les audiences conserv\u00e9es");await click("Lire les mod\u00e8les originaux");assert.ok(calls.some(c=>c.path.endsWith("/marketing/institutes/own/audience-captures?offset=0&limit=20")));assert.ok(calls.some(c=>c.path.endsWith("/marketing/institutes/own/templates?offset=0&limit=20")));assert.equal(document.querySelector('[aria-label="Brouillon marketing conserv\u00e9"]'),null);}
  finally{await act(async()=>root.unmount());}
});
