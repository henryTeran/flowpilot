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


import type {MovePreview,MoveEnvelope} from "../src/copilot-move-utils";
import type {MoveApprovalState,MoveExecution} from "../src/copilot-move-lifecycle";
import type {BaseDecisionEnvelope} from "../src/base-cancellation-utils";
const moveClock=(last:number)=>`2026-10-09T12:00:00.${last}Z`;
const seal=async<T,>(original:T)=>({original,fingerprint:await hash(original)});
async function fixture(){
  const selection={appointment_id:"booking",employee_id:null,service_id:null,start_time:"2026-10-25T01:30:00Z"};
  const appointment={status:"scheduled" as const,employee_id:"employee",service_id:"service",customer_id:"customer",start_time:"2026-10-24T12:00:00Z",end_time:"2026-10-24T12:10:00Z",booked_start_time:"2026-10-24T12:00:00Z",booked_end_time:"2026-10-24T12:10:00Z",actual_start_time:null,actual_end_time:null,checkout_ticket_id:null};
  const proposed={...appointment,start_time:selection.start_time,end_time:"2026-10-25T01:40:00Z",booked_start_time:selection.start_time,booked_end_time:"2026-10-25T01:40:00Z"};
  const preview:MovePreview={principal:{actor_id:"preparer",institute_id:"own",role:"responsable_institut"},capability:{name:"APPOINTMENT_MOVE",prepare_level:2,roles:["responsable_institut"],application_service:"appointments.service.preview_update",approval:"explicit_human_approval_of_exact_retained_operation_required",execution_registered:true},selection,captured_at:moveClock(123456),appointment,proposed,booking_events:1,booking_history_fingerprint:"d".repeat(64),resource_ids:["room"],state_fingerprint:await hash({institute_id:"own",selection,appointment,proposed,booking_events:1,booking_history_fingerprint:"d".repeat(64),resource_ids:["room"]}),effect:"move_preview_only_no_reservation_approval_or_execution"};
  const operation:MoveEnvelope=await seal({capability:"APPOINTMENT_MOVE",selection,expected_state_fingerprint:preview.state_fingerprint,valid_until:"2026-10-09T13:00:00Z",reason:"Créer le rendez-vous revu",idempotency_key:"preparation-key",id:"operation",institute_id:"own",actor_id:"preparer",created_at:moveClock(123457),preview,effect:"prepared_sensitive_operation_only_pending_human_approval_no_execution"});
  const decision:BaseDecisionEnvelope=await seal({operation_id:"operation",operation_fingerprint:operation.fingerprint,previous_id:null,previous_fingerprint:null,decision:"approve",reason:"Approuver les termes revus",idempotency_key:"approval-key",id:"approval",institute_id:"own",actor_id:"approver",created_at:moveClock(123459),source_checked_at:moveClock(123458),checked_state_fingerprint:preview.state_fingerprint,effect:"explicit_signed_human_decision_only_no_execution"});
  const state:MoveApprovalState={operation,captured_at:moveClock(123462),decisions:[decision],status:"approved",expired:false,execution:"not_performed_by_approval_manager",current_source:"not_revalidated_by_historical_state_read"};
  const before={...preview,principal:{...preview.principal,actor_id:"executor"},captured_at:moveClock(123460)};
  const receipt=await seal<MoveExecution>({operation_id:"operation",operation_fingerprint:operation.fingerprint,approval_id:"approval",approval_fingerprint:decision.fingerprint,reason:"Exécuter la création approuvée",idempotency_key:"execution-key",id:"execution",institute_id:"own",actor_id:"executor",created_at:moveClock(123461),before,after:proposed,appointment_id:selection.appointment_id,before_metadata_digest:"b".repeat(64),after_metadata_digest:"b".repeat(64),booking_event_id:"created-event",booking_event_fingerprint:"e".repeat(64),effect:"appointment_moved_through_existing_service_no_contact_or_payment",resource_basis:"checked_and_reserved_in_execution_transaction_not_current_occupancy"});
  return {operation,decision,state,receipt};
}
test("DOM: move uses explicit booking and DST occurrence, previews without mutation, clears edited evidence",async()=>{
  sessionStorage.clear();setAccessToken(token());const {operation}=await fixture();const calls:{path:string;body:any}[]=[];
  const registrations=["APPOINTMENT_CREATE","APPOINTMENT_MOVE","MARKETING_CAMPAIGN_DRAFT","STOCK_REORDER_PROPOSAL"].map(name=>({name,level:2,permission:"signed_institute_manager",input_schema:{},preview_input_schema:{},output_schema:{},application_service:name==="MARKETING_CAMPAIGN_DRAFT" ? "marketing.campaign_originals.execute_create_only" : name==="STOCK_REORDER_PROPOSAL" ? "inventory.reorders.create" : "base.sensitive_originals.create",audit:"signed_scope_interaction_id_and_source_digest_no_raw_message",effect:name==="MARKETING_CAMPAIGN_DRAFT" ? "retained_draft_only_no_campaign_approval_contact_or_delivery" : name==="STOCK_REORDER_PROPOSAL" ? "retained_reorder_proposal_no_order_contact_payment_receipt_or_stock_write" : "retained_pending_preparation_no_approval_or_execution"}));
  globalThis.fetch=async(url,init)=>{const path=String(url),body=init?.body ? JSON.parse(init.body as string) : undefined;calls.push({path,body});if(path.endsWith("/preparation-capabilities"))return reply(registrations);if(path.endsWith("/capabilities"))return reply(discovery());if(path.endsWith("/copilot/prepare-preview")){assert.deepEqual(body.ui_context,{appointment_id:"booking",start_time:"2026-10-25T01:30:00.000Z",employee_id:null,service_id:null});return reply({...operation.original.preview,principal:{...operation.original.preview.principal,actor_id:"manager"}});}throw Error("Unexpected domain call");};
  const root=createRoot(document.getElementById("root")!);
  try{await render(root);await settle();await click("D\u00e9placer un rendez-vous avec le Copilot");assert.equal(calls.filter(c=>c.body).length,0);await fill("R\u00e9f\u00e9rence du rendez-vous","booking");await fill("Votre demande de d\u00e9placement","Preparer le deplacement du rendez-vous");await fill("D\u00e9but local du rendez-vous","2026-03-29T02:30");await click("V\u00e9rifier les termes de d\u00e9placement");assert.equal(calls.filter(c=>c.body).length,0);await fill("D\u00e9but local du rendez-vous","2026-10-25T02:30");await click("V\u00e9rifier les termes de d\u00e9placement");assert.equal(calls.filter(c=>c.body).length,0);await fill("Occurrence de l\u2019heure r\u00e9p\u00e9t\u00e9e","2026-10-25T01:30:00.000Z");await click("V\u00e9rifier les termes de d\u00e9placement");assert.ok(document.querySelector('[aria-label="Termes de d\u00e9placement v\u00e9rifi\u00e9s"]'));assert.match(document.body.textContent!,/booking/);assert.equal(calls.filter(c=>c.body).length,1);await fill("R\u00e9f\u00e9rence du rendez-vous","other-booking");assert.equal(document.querySelector('[aria-label="Termes de d\u00e9placement v\u00e9rifi\u00e9s"]'),null);assert.equal(calls.filter(c=>c.body).length,1);}
  finally{await act(async()=>root.unmount());}
});
