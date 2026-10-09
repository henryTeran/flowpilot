import test from "node:test";
import assert from "node:assert/strict";
import {revenueOriginalFingerprint as hash} from "../src/revenue-scenario-utils";
import {createCreationPreparationIntent,createCreationDecisionIntent,createCreationExecutionIntent,creationIntentKey,type CreationPreparationRequest} from "../src/copilot-creation-intent";
import type {CreationEnvelope,CreationPreview} from "../src/copilot-creation-utils";
import type {CreationApprovalState,CreationExecution} from "../src/copilot-creation-lifecycle";
import type {BaseDecisionEnvelope} from "../src/base-cancellation-utils";
const seal=async<T>(original:T)=>({original,fingerprint:await hash(original)});
const clock=(last:number)=>`2026-10-09T12:00:00.${last}Z`;
const storage=()=>{const values=new Map<string,string>();return {getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v);},removeItem:(k:string)=>{values.delete(k);}};};
async function fixture(){
  const selection={employee_id:"employee",service_id:"service",customer_id:"customer",customer_name:"Cliente revue",phone:"+33999000000",notes:"Note revue",start_time:"2026-10-25T01:30:00Z"};
  const preview:CreationPreview={principal:{actor_id:"manager",institute_id:"own",role:"responsable_institut"},capability:{name:"APPOINTMENT_CREATE",prepare_level:2,roles:["responsable_institut"],application_service:"appointments.service.preview_creation",approval:"explicit_human_approval_of_exact_retained_operation_required",execution_registered:true},selection,captured_at:clock(123456),end_time:"2026-10-25T01:40:00Z",resource_ids:["room"],state_fingerprint:await hash({institute_id:"own",selection,end_time:"2026-10-25T01:40:00+00:00",resource_ids:["room"]}),basis:"exact_creation_terms_and_current_eligible_interval_resources_not_full_database_digest",effect:"creation_preview_only_no_reservation_approval_or_execution"};
  const request:CreationPreparationRequest={message:"Preparer la creation du rendez-vous",operation:{capability:"APPOINTMENT_CREATE",selection,expected_state_fingerprint:preview.state_fingerprint,valid_until:"2026-10-09T13:00:00Z",reason:"Préparation relue",idempotency_key:"preparation-key"}};
  const operation:CreationEnvelope=await seal({...request.operation,id:"operation",institute_id:"own",actor_id:"manager",created_at:clock(123457),preview,effect:"prepared_sensitive_operation_only_pending_human_approval_no_execution"});
  const decisionRequest={operation_id:"operation",operation_fingerprint:operation.fingerprint,previous_id:null,previous_fingerprint:null,decision:"approve" as const,reason:"Approbation relue",idempotency_key:"approval-key"};
  const decision:BaseDecisionEnvelope=await seal({...decisionRequest,id:"approval",institute_id:"own",actor_id:"manager",created_at:clock(123459),source_checked_at:clock(123458),checked_state_fingerprint:preview.state_fingerprint,effect:"explicit_signed_human_decision_only_no_execution"});
  const state:CreationApprovalState={operation,captured_at:clock(123462),decisions:[decision],status:"approved",expired:false,execution:"not_performed_by_approval_manager",current_source:"not_revalidated_by_historical_state_read"};
  const executionRequest={operation_id:"operation",operation_fingerprint:operation.fingerprint,approval_id:"approval",approval_fingerprint:decision.fingerprint,reason:"Exécution relue",idempotency_key:"execution-key"};
  const execution=await seal<CreationExecution>({...executionRequest,id:"execution",institute_id:"own",actor_id:"manager",created_at:clock(123461),before:{...preview,captured_at:clock(123460)},after:{status:"scheduled",employee_id:"employee",service_id:"service",customer_id:"customer",start_time:selection.start_time,end_time:preview.end_time,booked_start_time:selection.start_time,booked_end_time:preview.end_time,actual_start_time:null,actual_end_time:null,checkout_ticket_id:null},appointment_id:"created-appointment",saved_metadata_digest:await hash({customer_name:selection.customer_name,phone:selection.phone,notes:selection.notes}),booking_event_id:"event",booking_event_fingerprint:"e".repeat(64),effect:"appointment_created_through_existing_service_no_contact_or_payment",resource_basis:"checked_and_reserved_in_execution_transaction_not_current_occupancy"});
  return {request,operation,decisionRequest,decision,state,executionRequest,execution};
}
test("lost creation response is recovered after reload without changing frozen BASE message or operation",async()=>{
  const {request,operation}=await fixture(),saved=storage();let retained:unknown=null,writes=0;const reads:string[]=[];
  const options={institute:"own",actor:"manager",storage:saved,current:()=>true,get:async(path:string)=>{reads.push(path);return path.includes("by-key") ? retained : operation;},post:async(path:string,body:CreationPreparationRequest)=>{assert.equal(path,"/copilot/prepare");assert.deepEqual(body,request);writes++;retained=operation;throw Error("Lost response");}};
  const first=createCreationPreparationIntent(options);await assert.rejects(first.submit(request));assert.equal(first.state().status,"frozen");assert.equal(first.canCorrect(),false);
  const reload=createCreationPreparationIntent(options);const result=await reload.submit({...request,message:"Different message",operation:{...request.operation,reason:"Different reason"}});assert.equal(result.status,"confirmed");assert.equal(writes,1);assert.equal(reload.state().status,"empty");assert.ok(reads.some(p=>p.endsWith("/sensitive-operations/operation")));
});
test("creation recovery confirms decision membership and execution receipt independently",async()=>{
  const f=await fixture();
  for(const mode of ["decision","execution"] as const){
    const saved=storage(),paths:string[]=[];let retained:unknown=null;
    const receipt=mode==="decision" ? f.decision : f.execution;
    const options={institute:"own",actor:"manager",storage:saved,current:()=>true,get:async(path:string)=>{paths.push(path);if(path.endsWith("/approval-state"))return f.state;if(path.includes("by-key"))return retained;return receipt;},post:async(path:string,body:unknown)=>{assert.equal(path,mode==="decision" ? "/base/institutes/own/approvals" : "/copilot/execute");assert.deepEqual(body,mode==="decision" ? f.decisionRequest : f.executionRequest);retained=receipt;return receipt;}};
    const driver=mode==="decision" ? createCreationDecisionIntent(options) : createCreationExecutionIntent(options);
    const result=await driver.submit(mode==="decision" ? f.decisionRequest : f.executionRequest);assert.equal(result.status,"confirmed");assert.equal(driver.state().status,"empty");assert.ok(paths.filter(p=>p.endsWith("/approval-state")).length>=2);if(mode==="execution")assert.ok(paths.some(p=>p.endsWith("/operation/execution")));
  }
});
test("definitive creation rejection needs a fresh absent-key read; ambiguity and damaged originals remain frozen",async()=>{
  const {request,operation}=await fixture();
  for(const status of [400,500]){
    const saved=storage();let reads=0;const driver=createCreationPreparationIntent({institute:"own",actor:"manager",storage:saved,current:()=>true,get:async()=>{reads++;return null;},post:async()=>{throw Object.assign(Error("Rejected"),{status});}});
    await assert.rejects(driver.submit(request));assert.equal(driver.canCorrect(),status===400);
    if(status===400){assert.equal((await driver.correct()).status,"correctable");assert.equal(reads,2);assert.equal(driver.state().status,"empty");}else {await assert.rejects(driver.correct());assert.equal(driver.state().status,"frozen");}
  }
  const saved=storage();let writes=0;const damaged={...operation.original,selection:{...operation.original.selection,phone:null}};const receipt=await seal(damaged);
  const driver=createCreationPreparationIntent({institute:"own",actor:"manager",storage:saved,current:()=>true,get:async()=>receipt,post:async()=>{writes++;return operation;}});await assert.rejects(driver.submit(request));assert.equal(writes,0);assert.equal(driver.state().status,"frozen");
});
test("creation storage damage, changed session and concurrent reload cannot send a replacement request",async()=>{
  const {request,operation}=await fixture(),saved=storage();let writes=0;
  saved.setItem(creationIntentKey("own","manager","operation"),"not-json");const broken=createCreationPreparationIntent({institute:"own",actor:"manager",storage:saved,current:()=>true,get:async()=>null,post:async()=>{writes++;return operation;}});await assert.rejects(broken.submit(request));assert.equal(writes,0);
  const clean=storage();let live=true,resolveRead:(v:unknown)=>void=()=>{};const options={institute:"own",actor:"manager",storage:clean,current:()=>live,get:async()=>new Promise(resolve=>{resolveRead=resolve;}),post:async()=>{writes++;return operation;}};
  const first=createCreationPreparationIntent(options),second=createCreationPreparationIntent(options),pending=first.submit(request);assert.equal((await second.submit(request)).status,"busy");live=false;resolveRead(null);assert.equal((await pending).status,"stale");assert.equal(writes,0);assert.equal(first.state().status,"frozen");
  const other=createCreationPreparationIntent({...options,actor:"other",current:()=>false});assert.equal(other.state().status,"empty");assert.equal((await other.submit(request)).status,"stale");
});
