import {creationUTC} from "./copilot-creation-utils";
import {certificationInstant as instant} from "./certification-utils";
import {revenueOriginalFingerprint as hash} from "./revenue-scenario-utils";
import {validMoveEnvelope,validMovePreview,type MoveEnvelope,type MovePreview} from "./copilot-move-utils";
import {validBaseDecisionRequest,validBaseExecutionRequest,type BaseDecisionRequest,type BaseDecisionEnvelope,type BaseExecutionRequest,type BaseSnapshot} from "./base-cancellation-utils";

export type MoveApprovalState={operation:MoveEnvelope;captured_at:string;decisions:BaseDecisionEnvelope[];status:"pending"|"approved"|"declined"|"revoked";expired:boolean;execution:"not_performed_by_approval_manager";current_source:"not_revalidated_by_historical_state_read"};
export type MoveExecution=BaseExecutionRequest & {id:string;institute_id:string;actor_id:string;created_at:string;before:MovePreview;after:BaseSnapshot;appointment_id:string;before_metadata_digest:string;after_metadata_digest:string;booking_event_id:string;booking_event_fingerprint:string;effect:"appointment_moved_through_existing_service_no_contact_or_payment";resource_basis:"checked_and_reserved_in_execution_transaction_not_current_occupancy"};
export type MoveExecutionEnvelope={original:MoveExecution;fingerprint:string};
export {validCreationExecutionDiscovery as validMoveExecutionDiscovery} from "./copilot-creation-lifecycle";
const keys=(v:unknown,names:string):v is Record<string,any>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===names.split(" ").sort().join(" ");
const text=(v:unknown,max=80):v is string=>typeof v==="string" && !!v && v.trim()===v && Array.from(v).length<=max && !/[\x00-\x1f]/.test(v);
const digest=(v:unknown):v is string=>typeof v==="string" && /^[0-9a-f]{64}$/.test(v);
const utc=(v:unknown):v is string=>typeof v==="string" && creationUTC(v)===v;
const identity=(v:Record<string,any>,institute:string)=>text(v.id) && v.institute_id===institute && text(institute) && text(v.actor_id,160) && utc(v.created_at);
const decisionRequest=(o:Record<string,any>):BaseDecisionRequest=>({operation_id:o.operation_id,operation_fingerprint:o.operation_fingerprint,previous_id:o.previous_id,previous_fingerprint:o.previous_fingerprint,decision:o.decision,reason:o.reason,idempotency_key:o.idempotency_key});
const executionRequest=(o:Record<string,any>):BaseExecutionRequest=>({operation_id:o.operation_id,operation_fingerprint:o.operation_fingerprint,approval_id:o.approval_id,approval_fingerprint:o.approval_fingerprint,reason:o.reason,idempotency_key:o.idempotency_key});

export async function validMoveDecision(v:unknown,institute:string,operation:MoveEnvelope,expected?:BaseDecisionRequest,actor?:string):Promise<boolean>{
  try{
    if(!await validMoveEnvelope(operation,institute) || !keys(v,"original fingerprint") || !digest(v.fingerprint) || !keys(v.original,"operation_id operation_fingerprint previous_id previous_fingerprint decision reason idempotency_key id institute_id actor_id created_at source_checked_at checked_state_fingerprint effect"))return false;
    const o=v.original,op=operation.original,request=decisionRequest(o);
    if(!identity(o,institute) || actor!==undefined && o.actor_id!==actor || !validBaseDecisionRequest(request) || o.operation_id!==op.id || o.operation_fingerprint!==operation.fingerprint || o.id===o.previous_id || instant(o.created_at)!<instant(op.created_at)! || o.effect!=="explicit_signed_human_decision_only_no_execution")return false;
    if(o.decision==="approve"){
      if(!utc(o.source_checked_at) || o.checked_state_fingerprint!==op.expected_state_fingerprint || instant(o.source_checked_at)!<instant(op.created_at)! || instant(o.source_checked_at)!>instant(o.created_at)! || instant(o.created_at)!>=instant(op.valid_until)!)return false;
    }else if(o.source_checked_at!==null || o.checked_state_fingerprint!==null)return false;
    if(expected && (!validBaseDecisionRequest(expected) || await hash(request)!==await hash(expected)))return false;
    return await hash(o)===v.fingerprint;
  }catch{return false;}
}
export async function validMoveApprovalState(v:unknown,institute:string,selected?:MoveEnvelope):Promise<boolean>{
  try{
    if(!keys(v,"operation captured_at decisions status expired execution current_source") || !utc(v.captured_at) || !await validMoveEnvelope(v.operation,institute) || !Array.isArray(v.decisions) || v.decisions.length>2 || typeof v.expired!=="boolean" || v.execution!=="not_performed_by_approval_manager" || v.current_source!=="not_revalidated_by_historical_state_read")return false;
    const op=v.operation as MoveEnvelope,capture=instant(v.captured_at)!;
    if(selected && (selected.original.id!==op.original.id || selected.fingerprint!==op.fingerprint) || capture<instant(op.original.created_at)! || v.expired!==(capture>=instant(op.original.valid_until)!))return false;
    let status="pending",previous:BaseDecisionEnvelope|undefined;const ids=new Set<string>(),savedKeys=new Set<string>();
    for(const entry of v.decisions as BaseDecisionEnvelope[]){
      if(!await validMoveDecision(entry,institute,op))return false;const o=entry.original;
      if(ids.has(o.id) || savedKeys.has(o.idempotency_key) || instant(o.created_at)!>capture || o.previous_id!==(previous?.original.id??null) || o.previous_fingerprint!==(previous?.fingerprint??null) || previous && instant(o.created_at)!<instant(previous.original.created_at)! || !(status==="pending" && ["approve","decline"].includes(o.decision) || status==="approved" && o.decision==="revoke"))return false;
      ids.add(o.id);savedKeys.add(o.idempotency_key);previous=entry;status={approve:"approved",decline:"declined",revoke:"revoked"}[o.decision];
    }
    return v.status===status;
  }catch{return false;}
}
export async function validMoveExecution(v:unknown,institute:string,state:MoveApprovalState,expected?:BaseExecutionRequest,actor?:string):Promise<boolean>{
  try{
    if(!await validMoveApprovalState(state,institute) || state.status!=="approved" || !keys(v,"original fingerprint") || !digest(v.fingerprint) || !keys(v.original,"operation_id operation_fingerprint approval_id approval_fingerprint reason idempotency_key id institute_id actor_id created_at before after appointment_id before_metadata_digest after_metadata_digest booking_event_id booking_event_fingerprint effect resource_basis"))return false;
    const o=v.original,op=state.operation,approval=state.decisions[state.decisions.length-1],request=executionRequest(o);
    if(!identity(o,institute) || actor!==undefined && o.actor_id!==actor || !validBaseExecutionRequest(request) || o.operation_id!==op.original.id || o.operation_fingerprint!==op.fingerprint || o.approval_id!==approval.original.id || o.approval_fingerprint!==approval.fingerprint || !text(o.appointment_id) || !text(o.booking_event_id) || !digest(o.booking_event_fingerprint) || !digest(o.before_metadata_digest) || !digest(o.after_metadata_digest) || o.effect!=="appointment_moved_through_existing_service_no_contact_or_payment" || o.resource_basis!=="checked_and_reserved_in_execution_transaction_not_current_occupancy" || !await validMovePreview(o.before,institute,op.original.selection,o.actor_id) || o.before.state_fingerprint!==op.original.expected_state_fingerprint)return false;
    const p=o.before;
    if(o.appointment_id!==p.selection.appointment_id || await hash(o.after)!==await hash(p.proposed) || o.before_metadata_digest!==o.after_metadata_digest || instant(approval.original.created_at)!>instant(p.captured_at)! || instant(p.captured_at)!>instant(o.created_at)! || instant(o.created_at)!>=instant(op.original.valid_until)! || instant(o.created_at)!>instant(state.captured_at)!)return false;
    if(expected && (!validBaseExecutionRequest(expected) || await hash(request)!==await hash(expected)))return false;
    return await hash(o)===v.fingerprint;
  }catch{return false;}
}
