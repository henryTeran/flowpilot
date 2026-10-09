import {certificationInstant as instant} from "./certification-utils";
import {revenueOriginalFingerprint as hash} from "./revenue-scenario-utils";
import {creationUTC} from "./copilot-creation-utils";
import {validBaseSnapshot,type BaseSnapshot} from "./base-cancellation-utils";

export type MoveSelection={appointment_id:string;start_time:string;employee_id:string|null;service_id:string|null};
export type MovePreview={principal:{actor_id:string;institute_id:string;role:"responsable_institut"};capability:{name:"APPOINTMENT_MOVE";prepare_level:2;roles:["responsable_institut"];application_service:"appointments.service.preview_update";approval:"explicit_human_approval_of_exact_retained_operation_required";execution_registered:boolean};selection:MoveSelection;captured_at:string;appointment:BaseSnapshot;proposed:BaseSnapshot;booking_events:number;booking_history_fingerprint:string;resource_ids:string[];state_fingerprint:string;effect:"move_preview_only_no_reservation_approval_or_execution"};
export type MoveRequest={capability:"APPOINTMENT_MOVE";selection:MoveSelection;expected_state_fingerprint:string;valid_until:string;reason:string;idempotency_key:string};
export type MoveOriginal=MoveRequest & {id:string;institute_id:string;actor_id:string;created_at:string;preview:MovePreview;effect:"prepared_sensitive_operation_only_pending_human_approval_no_execution"};
export type MoveEnvelope={original:MoveOriginal;fingerprint:string};
const keys=(v:unknown,n:string):v is Record<string,any>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===n.split(" ").sort().join(" ");
const text=(v:unknown,max=80,min=1):v is string=>typeof v==="string" && v.trim()===v && Array.from(v).length>=min && Array.from(v).length<=max && !/[\x00-\x1f]/.test(v);
const digest=(v:unknown):v is string=>typeof v==="string" && /^[0-9a-f]{64}$/.test(v);
const utc=(v:unknown):v is string=>typeof v==="string" && instant(v)!==undefined && creationUTC(v)===v;
export function validMoveSelection(v:unknown):v is MoveSelection{return keys(v,"appointment_id start_time employee_id service_id") && text(v.appointment_id) && typeof v.start_time==="string" && v.start_time.includes("T") && instant(v.start_time)!==undefined && [v.employee_id,v.service_id].every(x=>x===null || text(x));}
export const canonicalMoveSelection=(v:MoveSelection):MoveSelection=>({...v,start_time:creationUTC(v.start_time)!});
const sameSelection=async(a:MoveSelection,b:MoveSelection)=>validMoveSelection(a) && validMoveSelection(b) && await hash(canonicalMoveSelection(a))===await hash(canonicalMoveSelection(b));
const compare=(a:string,b:string)=>{const x=Array.from(a,c=>c.codePointAt(0)!),y=Array.from(b,c=>c.codePointAt(0)!);for(let i=0;i<Math.min(x.length,y.length);i++)if(x[i]!==y[i])return x[i]-y[i];return x.length-y.length;};
export async function validMovePreview(v:unknown,institute:string,selected?:MoveSelection,actor?:string):Promise<boolean>{
  try{
    if(!keys(v,"principal capability selection captured_at appointment proposed booking_events booking_history_fingerprint resource_ids state_fingerprint effect") || !keys(v.principal,"actor_id institute_id role") || !text(institute) || v.principal.institute_id!==institute || !text(v.principal.actor_id,160) || actor!==undefined && actor!==v.principal.actor_id || v.principal.role!=="responsable_institut" || !validMoveSelection(v.selection) || !utc(v.selection.start_time) || selected && !await sameSelection(v.selection,selected) || !utc(v.captured_at) || !digest(v.state_fingerprint) || !digest(v.booking_history_fingerprint) || !Number.isSafeInteger(v.booking_events) || v.booking_events<0 || v.effect!=="move_preview_only_no_reservation_approval_or_execution")return false;
    const c=v.capability;if(!keys(c,"name prepare_level roles application_service approval execution_registered") || c.name!=="APPOINTMENT_MOVE" || c.prepare_level!==2 || !Array.isArray(c.roles) || c.roles.length!==1 || c.roles[0]!=="responsable_institut" || c.application_service!=="appointments.service.preview_update" || c.approval!=="explicit_human_approval_of_exact_retained_operation_required" || typeof c.execution_registered!=="boolean")return false;
    if(!validBaseSnapshot(v.appointment) || !validBaseSnapshot(v.proposed))return false;
    const b=v.appointment,a=v.proposed,s=v.selection;
    if(!["scheduled","confirmed"].includes(b.status) || b.actual_start_time!==null || b.actual_end_time!==null || b.checkout_ticket_id!==null || a.status!==b.status || a.customer_id!==b.customer_id || a.actual_start_time!==null || a.actual_end_time!==null || a.checkout_ticket_id!==null || a.start_time!==s.start_time || a.employee_id!==(s.employee_id??b.employee_id) || a.service_id!==(s.service_id??b.service_id) || a.booked_start_time!==a.start_time || a.booked_end_time!==a.end_time || a.service_id===b.service_id && instant(a.end_time)!-instant(a.start_time)!!==instant(b.end_time)!-instant(b.start_time)! || a.start_time===b.start_time && a.employee_id===b.employee_id && a.service_id===b.service_id)return false;
    if(!Array.isArray(v.resource_ids) || !v.resource_ids.every((r:unknown)=>text(r)) || v.resource_ids.some((r:string,i:number)=>i>0 && compare(v.resource_ids[i-1],r)>=0))return false;
    return await hash({institute_id:institute,selection:s,appointment:b,proposed:a,booking_history_fingerprint:v.booking_history_fingerprint,booking_events:v.booking_events,resource_ids:v.resource_ids})===v.state_fingerprint;
  }catch{return false;}
}
export function validMoveRequest(v:unknown):v is MoveRequest{return keys(v,"capability selection expected_state_fingerprint valid_until reason idempotency_key") && v.capability==="APPOINTMENT_MOVE" && validMoveSelection(v.selection) && digest(v.expected_state_fingerprint) && typeof v.valid_until==="string" && v.valid_until.includes("T") && instant(v.valid_until)!==undefined && text(v.reason,240,3) && text(v.idempotency_key,120);}
export async function validMoveEnvelope(v:unknown,institute:string,expected?:MoveRequest,actor?:string):Promise<boolean>{
  try{
    if(!keys(v,"original fingerprint") || !digest(v.fingerprint) || !keys(v.original,"capability selection expected_state_fingerprint valid_until reason idempotency_key id institute_id actor_id created_at preview effect"))return false;
    const o=v.original,request={capability:o.capability,selection:o.selection,expected_state_fingerprint:o.expected_state_fingerprint,valid_until:o.valid_until,reason:o.reason,idempotency_key:o.idempotency_key};
    if(!validMoveRequest(request) || !utc(o.selection.start_time) || !text(o.id) || o.institute_id!==institute || !text(o.actor_id,160) || actor!==undefined && actor!==o.actor_id || !utc(o.created_at) || !utc(o.valid_until) || o.effect!=="prepared_sensitive_operation_only_pending_human_approval_no_execution" || !await validMovePreview(o.preview,institute,o.selection,o.actor_id) || o.expected_state_fingerprint!==o.preview.state_fingerprint || instant(o.preview.captured_at)!>instant(o.created_at)! || instant(o.created_at)!>=instant(o.valid_until)!)return false;
    if(expected && (!validMoveRequest(expected) || !await sameSelection(o.selection,expected.selection) || o.expected_state_fingerprint!==expected.expected_state_fingerprint || instant(o.valid_until)!==instant(expected.valid_until) || o.reason!==expected.reason || o.idempotency_key!==expected.idempotency_key))return false;
    return await hash(o)===v.fingerprint;
  }catch{return false;}
}
