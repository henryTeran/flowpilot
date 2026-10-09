import test from "node:test";
import assert from "node:assert/strict";
import {revenueOriginalFingerprint as hash} from "../src/revenue-scenario-utils";
import {validCreationDecision,validCreationApprovalState,validCreationExecution,type CreationApprovalState,type CreationExecution} from "../src/copilot-creation-lifecycle";
import type {CreationPreview,CreationEnvelope} from "../src/copilot-creation-utils";
import type {BaseDecisionEnvelope,BaseDecisionRequest} from "../src/base-cancellation-utils";
const clock=(last:number)=>`2026-10-09T12:00:00.${last}Z`;
const seal=async<T>(original:T)=>({original,fingerprint:await hash(original)});
async function fixture(){
  const selection={employee_id:"employee",service_id:"service",customer_id:"customer",customer_name:"Cliente revue",phone:"+33999000000",notes:"Note revue",start_time:"2026-10-25T01:30:00Z"};
  const preview:CreationPreview={principal:{actor_id:"preparer",institute_id:"own",role:"responsable_institut"},capability:{name:"APPOINTMENT_CREATE",prepare_level:2,roles:["responsable_institut"],application_service:"appointments.service.preview_creation",approval:"explicit_human_approval_of_exact_retained_operation_required",execution_registered:true},selection,captured_at:clock(123456),end_time:"2026-10-25T01:40:00Z",resource_ids:["room"],state_fingerprint:await hash({institute_id:"own",selection,end_time:"2026-10-25T01:40:00+00:00",resource_ids:["room"]}),basis:"exact_creation_terms_and_current_eligible_interval_resources_not_full_database_digest",effect:"creation_preview_only_no_reservation_approval_or_execution"};
  const operation:CreationEnvelope=await seal({capability:"APPOINTMENT_CREATE",selection,expected_state_fingerprint:preview.state_fingerprint,valid_until:"2026-10-09T13:00:00Z",reason:"Créer le rendez-vous revu",idempotency_key:"preparation-key",id:"operation",institute_id:"own",actor_id:"preparer",created_at:clock(123457),preview,effect:"prepared_sensitive_operation_only_pending_human_approval_no_execution"});
  const decision:BaseDecisionEnvelope=await seal({operation_id:"operation",operation_fingerprint:operation.fingerprint,previous_id:null,previous_fingerprint:null,decision:"approve",reason:"Approuver les termes revus",idempotency_key:"approval-key",id:"approval",institute_id:"own",actor_id:"approver",created_at:clock(123459),source_checked_at:clock(123458),checked_state_fingerprint:preview.state_fingerprint,effect:"explicit_signed_human_decision_only_no_execution"});
  const state:CreationApprovalState={operation,captured_at:clock(123462),decisions:[decision],status:"approved",expired:false,execution:"not_performed_by_approval_manager",current_source:"not_revalidated_by_historical_state_read"};
  const before={...preview,principal:{...preview.principal,actor_id:"executor"},captured_at:clock(123460)};
  const receipt=await seal<CreationExecution>({operation_id:"operation",operation_fingerprint:operation.fingerprint,approval_id:"approval",approval_fingerprint:decision.fingerprint,reason:"Exécuter la création approuvée",idempotency_key:"execution-key",id:"execution",institute_id:"own",actor_id:"executor",created_at:clock(123461),before,after:{status:"scheduled",employee_id:selection.employee_id,service_id:selection.service_id,customer_id:selection.customer_id,start_time:selection.start_time,end_time:preview.end_time,booked_start_time:selection.start_time,booked_end_time:preview.end_time,actual_start_time:null,actual_end_time:null,checkout_ticket_id:null},appointment_id:"created-appointment",saved_metadata_digest:await hash({customer_name:selection.customer_name,phone:selection.phone,notes:selection.notes}),booking_event_id:"created-event",booking_event_fingerprint:"e".repeat(64),effect:"appointment_created_through_existing_service_no_contact_or_payment",resource_basis:"checked_and_reserved_in_execution_transaction_not_current_occupancy"});
  return {operation,decision,state,receipt};
}
test("creation decisions bind exact original, reviewed request, actor and source chronology",async()=>{
  const {operation,decision}=await fixture(),o=decision.original;
  const request:BaseDecisionRequest={operation_id:o.operation_id,operation_fingerprint:o.operation_fingerprint,previous_id:null,previous_fingerprint:null,decision:"approve",reason:o.reason,idempotency_key:o.idempotency_key};
  assert.ok(await validCreationDecision(decision,"own",operation,request,"approver"));
  assert.equal(await validCreationDecision(decision,"own",operation,{...request,reason:"Another reason"},"approver"),false);
  assert.equal(await validCreationDecision(decision,"own",operation,request,"preparer"),false);
  for(const change of [{operation_id:"other"},{operation_fingerprint:"a".repeat(64)},{source_checked_at:clock(123456)},{source_checked_at:clock(123460)},{checked_state_fingerprint:"a".repeat(64)},{created_at:operation.original.valid_until},{previous_id:"previous"},{effect:"executed"},{institute_id:"foreign"}])assert.equal(await validCreationDecision(await seal({...o,...change}),"own",operation),false);
  const stop={...o,decision:"decline",source_checked_at:null,checked_state_fingerprint:null};assert.ok(await validCreationDecision(await seal(stop),"own",operation));
  assert.equal(await validCreationDecision(await seal({...stop,checked_state_fingerprint:o.checked_state_fingerprint}),"own",operation),false);
});
test("creation historical approval state validates the causal chain without current-source or execution authority",async()=>{
  const {operation,decision,state}=await fixture();assert.ok(await validCreationApprovalState(state,"own",operation));
  const pending={...state,decisions:[],status:"pending"};assert.ok(await validCreationApprovalState(pending,"own",operation));
  for(const change of [{status:"pending"},{expired:true},{execution:"performed"},{current_source:"current_eligible"},{captured_at:clock(123458)},{decisions:[decision,decision]}])assert.equal(await validCreationApprovalState({...state,...change},"own",operation),false);
  const revoked=await seal({...decision.original,id:"revoke",previous_id:decision.original.id,previous_fingerprint:decision.fingerprint,decision:"revoke",reason:"Révoquer la préparation",idempotency_key:"revoke-key",created_at:clock(123460),source_checked_at:null,checked_state_fingerprint:null});
  assert.ok(await validCreationApprovalState({...state,status:"revoked",decisions:[decision,revoked]},"own",operation));
  for(const change of [{previous_fingerprint:"a".repeat(64)},{previous_id:null,previous_fingerprint:null},{decision:"approve",source_checked_at:clock(123458),checked_state_fingerprint:operation.original.expected_state_fingerprint},{idempotency_key:decision.original.idempotency_key}])assert.equal(await validCreationApprovalState({...state,status:"revoked",decisions:[decision,await seal({...revoked.original,...change})]},"own",operation),false);
  const late={...state,captured_at:"2026-10-09T14:00:00Z",expired:true};assert.ok(await validCreationApprovalState(late,"own",operation));
});
test("creation execution receipt binds latest approval, exact saved booking metadata and interval, and historical validity",async()=>{
  const {state,receipt}=await fixture(),o=receipt.original;
  const request={operation_id:o.operation_id,operation_fingerprint:o.operation_fingerprint,approval_id:o.approval_id,approval_fingerprint:o.approval_fingerprint,reason:o.reason,idempotency_key:o.idempotency_key};
  assert.ok(await validCreationExecution(receipt,"own",state,request,"executor"));assert.ok(await validCreationExecution(receipt,"own",{...state,captured_at:"2026-10-09T14:00:00Z",expired:true},request,"executor"));
  assert.equal(await validCreationExecution(receipt,"own",state,{...request,idempotency_key:"another"},"executor"),false);assert.equal(await validCreationExecution(receipt,"own",state,request,"approver"),false);
  for(const change of [{approval_id:"other"},{approval_fingerprint:"a".repeat(64)},{saved_metadata_digest:"a".repeat(64)},{after:{...o.after,booked_end_time:"2026-10-25T01:41:00Z"}},{after:{...o.after,customer_id:null}},{after:{...o.after,status:"confirmed"}},{before:{...o.before,captured_at:clock(123458)}},{created_at:clock(123459)},{created_at:clock(123463)},{created_at:state.operation.original.valid_until},{resource_basis:"current_occupancy"},{effect:"appointment_cancelled_through_existing_service_no_contact_or_refund"},{booking_event_fingerprint:"invalid"}])assert.equal(await validCreationExecution(await seal({...o,...change}),"own",state),false);
  const stop={...state.decisions[0].original,decision:"decline",source_checked_at:null,checked_state_fingerprint:null};assert.equal(await validCreationExecution(receipt,"own",{...state,status:"declined",decisions:[await seal(stop)]} as CreationApprovalState),false);
  assert.equal(await validCreationExecution({...receipt,fingerprint:"0".repeat(64)},"own",state),false);
});
