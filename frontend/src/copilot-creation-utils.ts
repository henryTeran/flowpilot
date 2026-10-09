import {certificationInstant as instant} from "./certification-utils";
import {revenueOriginalFingerprint as hash} from "./revenue-scenario-utils";

export type CreationSelection={employee_id:string;service_id:string;customer_id:string|null;customer_name:string;phone:string|null;notes:string|null;start_time:string};
export type CreationPreview={principal:{actor_id:string;institute_id:string;role:"responsable_institut"};capability:{name:"APPOINTMENT_CREATE";prepare_level:2;roles:["responsable_institut"];application_service:"appointments.service.preview_creation";approval:"explicit_human_approval_of_exact_retained_operation_required";execution_registered:boolean};selection:CreationSelection;captured_at:string;end_time:string;resource_ids:string[];state_fingerprint:string;basis:"exact_creation_terms_and_current_eligible_interval_resources_not_full_database_digest";effect:"creation_preview_only_no_reservation_approval_or_execution"};
export type CreationRequest={capability:"APPOINTMENT_CREATE";selection:CreationSelection;expected_state_fingerprint:string;valid_until:string;reason:string;idempotency_key:string};
export type CreationOriginal=CreationRequest & {id:string;institute_id:string;actor_id:string;created_at:string;preview:CreationPreview;effect:"prepared_sensitive_operation_only_pending_human_approval_no_execution"};
export type CreationEnvelope={original:CreationOriginal;fingerprint:string};
export function validCreationDiscovery(v:unknown):boolean{
  const registrations:Record<string,[string,string]>={APPOINTMENT_CREATE:["base.sensitive_originals.create","retained_pending_preparation_no_approval_or_execution"],APPOINTMENT_MOVE:["base.sensitive_originals.create","retained_pending_preparation_no_approval_or_execution"],MARKETING_CAMPAIGN_DRAFT:["marketing.campaign_originals.execute_create_only","retained_draft_only_no_campaign_approval_contact_or_delivery"],STOCK_REORDER_PROPOSAL:["inventory.reorders.create","retained_reorder_proposal_no_order_contact_payment_receipt_or_stock_write"]};
  return Array.isArray(v) && v.length===4 && new Set(v.map(r=>r?.name)).size===4 && v.every(r=>keys(r,"name level permission input_schema preview_input_schema output_schema application_service audit effect") && Object.prototype.hasOwnProperty.call(registrations,r.name) && r.level===2 && r.permission==="signed_institute_manager" && [r.input_schema,r.preview_input_schema,r.output_schema].every(s=>!!s && typeof s==="object" && !Array.isArray(s)) && r.application_service===registrations[r.name][0] && r.effect===registrations[r.name][1] && r.audit==="signed_scope_interaction_id_and_source_digest_no_raw_message");
}
const keys=(v:unknown,names:string):v is Record<string,any>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===names.split(" ").sort().join(" ");
const text=(v:unknown,max:number,min=1):v is string=>typeof v==="string" && v.trim()===v && Array.from(v).length>=min && Array.from(v).length<=max && !/[\x00-\x1f]/.test(v);
const id=(v:unknown):v is string=>text(v,80);
const digest=(v:unknown):v is string=>typeof v==="string" && /^[0-9a-f]{64}$/.test(v);
const utc=(v:unknown):v is string=>typeof v==="string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(?!000000)\d{6})?Z$/.test(v) && instant(v)!==undefined;

// Pydantic emits UTC seconds or six nonzero fractional digits; preserve microseconds.
export function creationUTC(value:string):string|undefined{
  const parsed=instant(value);if(parsed===undefined)return;
  const fraction=(parsed%1000000n+1000000n)%1000000n,seconds=(parsed-fraction)/1000000n;
  const prefix=new Date(Number(seconds*1000n)).toISOString().slice(0,19);
  return `${prefix}${fraction ? `.${fraction.toString().padStart(6,"0")}` : ""}Z`;
}
export function validCreationSelection(v:unknown):v is CreationSelection{
  return keys(v,"employee_id service_id customer_id customer_name phone notes start_time") && id(v.employee_id) && id(v.service_id) && (v.customer_id===null || id(v.customer_id)) && text(v.customer_name,160,2) && (v.phone===null || text(v.phone,40,0)) && (v.notes===null || text(v.notes,500,0)) && typeof v.start_time==="string" && v.start_time.includes("T") && instant(v.start_time)!==undefined;
}
export function canonicalCreationSelection(v:CreationSelection):CreationSelection{
  return {...v,start_time:creationUTC(v.start_time)!};
}
async function sameSelection(a:CreationSelection,b:CreationSelection){return validCreationSelection(a) && validCreationSelection(b) && await hash(canonicalCreationSelection(a))===await hash(canonicalCreationSelection(b));}

export async function validCreationPreview(v:unknown,institute:string,selected?:CreationSelection,actor?:string):Promise<boolean>{
  try{
    if(!keys(v,"principal capability selection captured_at end_time resource_ids state_fingerprint basis effect") || !keys(v.principal,"actor_id institute_id role") || !id(institute) || v.principal.institute_id!==institute || !text(v.principal.actor_id,160) || actor!==undefined && v.principal.actor_id!==actor || v.principal.role!=="responsable_institut" || !validCreationSelection(v.selection) || !utc(v.selection.start_time) || selected && !await sameSelection(v.selection,selected) || !utc(v.captured_at) || !utc(v.end_time) || instant(v.end_time)!<=instant(v.selection.start_time)! || !digest(v.state_fingerprint) || v.basis!=="exact_creation_terms_and_current_eligible_interval_resources_not_full_database_digest" || v.effect!=="creation_preview_only_no_reservation_approval_or_execution")return false;
    if(!keys(v.capability,"name prepare_level roles application_service approval execution_registered"))return false;
    const c=v.capability;
    if(c.name!=="APPOINTMENT_CREATE" || c.prepare_level!==2 || !Array.isArray(c.roles) || c.roles.length!==1 || c.roles[0]!=="responsable_institut" || c.application_service!=="appointments.service.preview_creation" || c.approval!=="explicit_human_approval_of_exact_retained_operation_required" || typeof c.execution_registered!=="boolean")return false;
    if(!Array.isArray(v.resource_ids) || !v.resource_ids.every(id) || v.resource_ids.some((r:string,index:number)=>index>0 && pythonCompare(v.resource_ids[index-1],r)>=0))return false;
    return await hash({institute_id:institute,selection:v.selection,end_time:v.end_time.replace(/Z$/,"+00:00"),resource_ids:v.resource_ids})===v.state_fingerprint;
  }catch{return false;}
}
// Python sorts Unicode code points, while JS default sorting uses UTF-16 units.
function pythonCompare(a:string,b:string):number{
  const left=Array.from(a,ch=>ch.codePointAt(0)!),right=Array.from(b,ch=>ch.codePointAt(0)!);
  for(let i=0;i<Math.min(left.length,right.length);i++)if(left[i]!==right[i])return left[i]-right[i];
  return left.length-right.length;
}
export function validCreationRequest(v:unknown):v is CreationRequest{
  return keys(v,"capability selection expected_state_fingerprint valid_until reason idempotency_key") && v.capability==="APPOINTMENT_CREATE" && validCreationSelection(v.selection) && digest(v.expected_state_fingerprint) && typeof v.valid_until==="string" && v.valid_until.includes("T") && instant(v.valid_until)!==undefined && text(v.reason,240,3) && text(v.idempotency_key,120);
}
export async function validCreationEnvelope(v:unknown,institute:string,expected?:CreationRequest,actor?:string):Promise<boolean>{
  try{
    if(!keys(v,"original fingerprint") || !digest(v.fingerprint) || !keys(v.original,"capability selection expected_state_fingerprint valid_until reason idempotency_key id institute_id actor_id created_at preview effect"))return false;
    const o=v.original;
    if(!validCreationSelection(o.selection) || !utc(o.selection.start_time))return false;
    if(!validCreationRequest({capability:o.capability,selection:o.selection,expected_state_fingerprint:o.expected_state_fingerprint,valid_until:o.valid_until,reason:o.reason,idempotency_key:o.idempotency_key}) || !id(o.id) || o.institute_id!==institute || !text(o.actor_id,160) || actor!==undefined && o.actor_id!==actor || !utc(o.created_at) || !utc(o.valid_until) || o.effect!=="prepared_sensitive_operation_only_pending_human_approval_no_execution" || !await validCreationPreview(o.preview,institute,o.selection,o.actor_id) || o.expected_state_fingerprint!==o.preview.state_fingerprint || instant(o.preview.captured_at)!>instant(o.created_at)! || instant(o.created_at)!>=instant(o.valid_until)!)return false;
    if(expected && (!validCreationRequest(expected) || !await sameSelection(o.selection,expected.selection) || o.capability!==expected.capability || o.expected_state_fingerprint!==expected.expected_state_fingerprint || instant(o.valid_until)!==instant(expected.valid_until) || o.reason!==expected.reason || o.idempotency_key!==expected.idempotency_key))return false;
    return await hash(o)===v.fingerprint;
  }catch{return false;}
}
