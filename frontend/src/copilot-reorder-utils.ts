import {certificationInstant as instant} from "./certification-utils";
import {creationUTC} from "./copilot-creation-utils";
import {revenueOriginalFingerprint as hash} from "./revenue-scenario-utils";
import {validScenario,type Scenario} from "./outlook-utils";
export type ReorderSelection={supplier_id:string;item_ids:string[];pending_order_assumption:"ignore_pending_orders"|"all_pending_orders_received";scenario:Scenario|null};
export type ReorderItem={item_id:string;unit:"ml"|"g"|"unit";on_hand:string;threshold:string;pending_order_quantity:string;known_demand:string;complete_demand:string|null;proposed_quantity:string};
export type ReorderPreview={institute_id:string;selection:ReorderSelection;captured_at:string;coverage:"not_applicable"|"complete_selected_norms"|"partial_selected_norms";items:ReorderItem[];source_digest:string;state_fingerprint:string;basis:"original_stock_shortfalls_selected_scenario_and_explicit_pending_assumption_not_supplier_quote";effect:"reorder_proposal_only_no_order_contact_payment_receipt_or_stock_write"};
export type ReorderRequest={selection:ReorderSelection;expected_state_fingerprint:string;reason:string;idempotency_key:string};
export type ReorderOriginal=ReorderRequest & {id:string;institute_id:string;actor_id:string;created_at:string;preview:ReorderPreview};
export type ReorderReceipt={original:ReorderOriginal;fingerprint:string};
const keys=(v:unknown,n:string):v is Record<string,any>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===n.split(" ").sort().join(" ");
const id=(v:unknown):v is string=>typeof v==="string" && !!v && v.trim()===v && Array.from(v).length<=80 && !/[\x00-\x1f]/.test(v);
const digest=(v:unknown)=>typeof v==="string" && /^[0-9a-f]{64}$/.test(v);
const text=(v:unknown,max:number,min=1):v is string=>typeof v==="string" && v.trim()===v && Array.from(v).length>=min && Array.from(v).length<=max && !/[\x00-\x1f]/.test(v);
export function validReorderRequest(v:unknown):v is ReorderRequest{return keys(v,"selection expected_state_fingerprint reason idempotency_key") && validReorderSelection(v.selection) && digest(v.expected_state_fingerprint) && text(v.reason,240,3) && text(v.idempotency_key,120);}
export async function validReorderReceipt(v:unknown,institute:string,expected?:ReorderRequest,actor?:string):Promise<boolean>{
  try{
    if(!keys(v,"original fingerprint") || !digest(v.fingerprint) || !keys(v.original,"selection expected_state_fingerprint reason idempotency_key id institute_id actor_id created_at preview"))return false;
    const o=v.original,r={selection:o.selection,expected_state_fingerprint:o.expected_state_fingerprint,reason:o.reason,idempotency_key:o.idempotency_key};
    if(!validReorderRequest(r) || !id(o.id) || o.institute_id!==institute || !text(o.actor_id,160) || actor!==undefined && o.actor_id!==actor || typeof o.created_at!=="string" || instant(o.created_at)===undefined || creationUTC(o.created_at)!==o.created_at || !await validReorderPreview(o.preview,institute,o.selection) || o.expected_state_fingerprint!==o.preview.state_fingerprint || instant(o.created_at)!<instant(o.preview.captured_at)! || await hash(o.selection)!==await hash(canonicalReorderSelection(o.selection)))return false;
    if(expected && (!validReorderRequest(expected) || await hash(o.selection)!==await hash(canonicalReorderSelection(expected.selection)) || o.expected_state_fingerprint!==expected.expected_state_fingerprint || o.reason!==expected.reason || o.idempotency_key!==expected.idempotency_key))return false;
    return await hash(o)===v.fingerprint;
  }catch{return false;}
}
export function validReorderSelection(v:unknown):v is ReorderSelection{
  return keys(v,"supplier_id item_ids pending_order_assumption scenario") && id(v.supplier_id) && Array.isArray(v.item_ids) && v.item_ids.length>=1 && v.item_ids.length<=50 && v.item_ids.every(id) && new Set(v.item_ids).size===v.item_ids.length && ["ignore_pending_orders","all_pending_orders_received"].includes(v.pending_order_assumption) && (v.scenario===null || keys(v.scenario,"starts_at ends_at demands") && validScenario(v.scenario) && v.scenario.demands.every((d:unknown)=>keys(d,"service_id recipe_id quantity") && id(d.service_id) && (d.recipe_id===null || id(d.recipe_id))));
}
export const canonicalReorderSelection=(v:ReorderSelection):ReorderSelection=>({...v,scenario:v.scenario===null ? null : {...v.scenario,starts_at:creationUTC(v.scenario.starts_at)!,ends_at:creationUTC(v.scenario.ends_at)!}});
const milli=(v:string)=>BigInt(v.replace(".",""));
export async function validReorderPreview(v:unknown,institute:string,selected?:ReorderSelection):Promise<boolean>{
  try{
    if(!keys(v,"institute_id selection captured_at coverage items source_digest state_fingerprint basis effect") || !id(institute) || v.institute_id!==institute || !validReorderSelection(v.selection) || typeof v.captured_at!=="string" || instant(v.captured_at)===undefined || creationUTC(v.captured_at)!==v.captured_at || !digest(v.source_digest) || !digest(v.state_fingerprint) || v.basis!=="original_stock_shortfalls_selected_scenario_and_explicit_pending_assumption_not_supplier_quote" || v.effect!=="reorder_proposal_only_no_order_contact_payment_receipt_or_stock_write")return false;
    const s=v.selection as ReorderSelection;if(await hash(s)!==await hash(canonicalReorderSelection(s)) || selected && (!validReorderSelection(selected) || await hash(s)!==await hash(canonicalReorderSelection(selected))))return false;
    const complete=s.scenario!==null && s.scenario.demands.every(d=>d.recipe_id!==null),coverage=s.scenario===null ? "not_applicable" : complete ? "complete_selected_norms" : "partial_selected_norms";
    if(v.coverage!==coverage || !Array.isArray(v.items) || v.items.length!==s.item_ids.length || new Set(v.items.map(r=>r?.item_id)).size!==v.items.length)return false;
    for(const r of v.items){if(!keys(r,"item_id unit on_hand threshold pending_order_quantity known_demand complete_demand proposed_quantity") || !s.item_ids.includes(r.item_id) || !["ml","g","unit"].includes(r.unit))return false;
      for(const q of [r.on_hand,r.threshold,r.pending_order_quantity,r.known_demand,r.proposed_quantity,...(r.complete_demand===null ? [] : [r.complete_demand])])if(typeof q!=="string" || !/^(0|[1-9][0-9]*)\.[0-9]{3}$/.test(q) || r.unit==="unit" && !q.endsWith(".000"))return false;
      if(r.complete_demand!==(complete ? r.known_demand : null) || s.scenario===null && r.known_demand!=="0.000")return false;
      const need=milli(r.threshold)+milli(r.known_demand)-milli(r.on_hand)-(s.pending_order_assumption==="all_pending_orders_received" ? milli(r.pending_order_quantity) : 0n);
      if(milli(r.proposed_quantity)!==(need>0n ? need : 0n))return false;
    }
    const {captured_at,state_fingerprint,...raw}=v;return await hash(raw)===state_fingerprint;
  }catch{return false;}
}
