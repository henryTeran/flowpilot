import {certificationInstant as instant} from "./certification-utils";
import {validLossRead,type LossRead} from "./copilot-loss-utils";
export type FollowUps={institute_id:string;captured_at:string;source:"recorded_closure_follow_up";bookings:LossRead["bookings"];walk_ins:LossRead["walk_ins"];booking_total:number;walk_in_total:number;
  booking_candidates:{event_id:string;appointment_id:string;type:"review_cancelled_booking"|"review_no_show_booking";occurred_at:string;estimated_value:null}[];
  walk_in_candidates:{event_id:number;ticket_id:string;type:"review_cancelled_walk_in";occurred_at:string;retained_value:{currency:"CHF"|"EUR";amount_minor:string;basis:"recorded_cancelled_commercial_value"}|null;confidence:"retained_commercial_terms_not_causal_loss"|"legacy_cancellation_unpriced"}[];
  page_limit_per_source:20;estimated_recovered_revenue:null;causal_loss_proven:false;delivery_authorized:false;action_executed:false;complete_history:false};
const keys=(v:unknown,names:string):v is Record<string,unknown>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===names.split(" ").sort().join(" ");
const count=(v:unknown):v is number=>Number.isSafeInteger(v) && (v as number)>=0;
const id=(v:unknown):v is string=>typeof v==="string" && !!v && v.trim()===v && Array.from(v).length<=80 && !/[\x00-\x1f]/.test(v);
export function validFollowUps(v:unknown,institute:string,period:{start:string;end:string},capture:string):v is FollowUps{
  if(!keys(v,"institute_id captured_at source bookings walk_ins booking_total walk_in_total booking_candidates walk_in_candidates page_limit_per_source estimated_recovered_revenue causal_loss_proven delivery_authorized action_executed complete_history")
    || v.source!=="recorded_closure_follow_up" || v.page_limit_per_source!==20 || v.estimated_recovered_revenue!==null || v.causal_loss_proven!==false || v.delivery_authorized!==false || v.action_executed!==false || v.complete_history!==false
    || !validLossRead({institute_id:v.institute_id,captured_at:v.captured_at,bookings:v.bookings,walk_ins:v.walk_ins,causal_loss_proven:false,complete_history:false,financial_loss:null,basis:"recorded_closure_events_not_causal_financial_loss"},institute,period,capture))return false;
  const b=v.bookings as LossRead["bookings"],w=v.walk_ins as LossRead["walk_ins"];
  if(!count(v.booking_total) || !count(v.walk_in_total) || BigInt(v.booking_total)!==BigInt(b.cancelled_count)+BigInt(b.no_show_count) || BigInt(v.walk_in_total)!==BigInt(w.retained_terms_count)+BigInt(w.legacy_unpriced_count))return false;
  const page=(rows:unknown,total:number,window:LossRead["bookings"]["window"],booking:boolean)=>{
    if(!Array.isArray(rows) || rows.length!==Math.min(20,total) || new Set(rows.map(r=>r?.event_id)).size!==rows.length)return false;
    return rows.every(r=>{
      if(!keys(r,booking ? "event_id appointment_id type occurred_at estimated_value" : "event_id ticket_id type occurred_at retained_value confidence"))return false;
      const clock=instant(r.occurred_at);
      if(clock===undefined || clock<instant(window.start)! || clock>=instant(window.end)! || clock>instant(window.captured_at)!)return false;
      if(booking)return id(r.event_id) && id(r.appointment_id) && ["review_cancelled_booking","review_no_show_booking"].includes(r.type as string) && r.estimated_value===null;
      if(!count(r.event_id) || r.event_id===0 || !id(r.ticket_id) || r.type!=="review_cancelled_walk_in" || !["retained_commercial_terms_not_causal_loss","legacy_cancellation_unpriced"].includes(r.confidence as string))return false;
      if(r.retained_value===null)return true;
      return r.confidence==="retained_commercial_terms_not_causal_loss" && keys(r.retained_value,"currency amount_minor basis") && ["CHF","EUR"].includes(r.retained_value.currency as string)
        && typeof r.retained_value.amount_minor==="string" && /^(0|[1-9][0-9]{0,9})$/.test(r.retained_value.amount_minor) && r.retained_value.basis==="recorded_cancelled_commercial_value";
    });
  };
  return page(v.booking_candidates,v.booking_total,b.window,true) && page(v.walk_in_candidates,v.walk_in_total,w.window,false);
}
