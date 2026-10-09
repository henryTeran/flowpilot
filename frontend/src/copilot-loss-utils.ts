import {certificationInstant as instant} from "./certification-utils";
import {validRevenueAmounts,type RevenueAmounts} from "./revenue-utils";
type Window={institute_id:string;start:string;end:string;captured_at:string};
export type LossRead={institute_id:string;captured_at:string;bookings:{window:Window;source_digest:string;cancelled_count:number;no_show_count:number;unpriced_count:number;institute_terminal_bookings_without_closure_event:number};
  walk_ins:{window:Window;source_digest:string;retained_terms_count:number;legacy_unpriced_count:number;retained_amounts:RevenueAmounts[]};
  causal_loss_proven:false;complete_history:false;financial_loss:null;basis:"recorded_closure_events_not_causal_financial_loss"};
const keys=(v:unknown,names:string):v is Record<string,unknown>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===names.split(" ").sort().join(" ");
const count=(v:unknown):v is number=>Number.isSafeInteger(v) && (v as number)>=0;
const digest=(v:unknown)=>typeof v==="string" && /^[0-9a-f]{64}$/.test(v);
export function validLossRead(v:unknown,institute:string,period:{start:string;end:string},capture:string):v is LossRead{
  if(!keys(v,"institute_id captured_at bookings walk_ins causal_loss_proven complete_history financial_loss basis") || v.institute_id!==institute || instant(v.captured_at)!==instant(capture) || instant(capture)===undefined
    || v.causal_loss_proven!==false || v.complete_history!==false || v.financial_loss!==null || v.basis!=="recorded_closure_events_not_causal_financial_loss"
    || !keys(v.bookings,"window source_digest cancelled_count no_show_count unpriced_count institute_terminal_bookings_without_closure_event")
    || !keys(v.walk_ins,"window source_digest retained_terms_count legacy_unpriced_count retained_amounts"))return false;
  const b=v.bookings,w=v.walk_ins;
  const window=(value:unknown)=>{
    if(!keys(value,"institute_id start end captured_at") || value.institute_id!==institute)return false;
    const first=instant(value.start),last=instant(value.end),clock=instant(value.captured_at);
    return first!==undefined && last!==undefined && clock!==undefined && first<last && last<=clock && clock<=instant(capture)! && first===instant(period.start) && last===instant(period.end);
  };
  if(!window(b.window) || !window(w.window) || !digest(b.source_digest) || !digest(w.source_digest)
    || ![b.cancelled_count,b.no_show_count,b.unpriced_count,b.institute_terminal_bookings_without_closure_event,w.retained_terms_count,w.legacy_unpriced_count].every(count))return false;
  if(BigInt(b.unpriced_count as number)!==BigInt(b.cancelled_count as number)+BigInt(b.no_show_count as number)
    || !Array.isArray(w.retained_amounts) || !w.retained_amounts.every(validRevenueAmounts) || new Set(w.retained_amounts.map(g=>g.currency)).size!==w.retained_amounts.length
    || w.retained_amounts.reduce((n,g)=>n+BigInt(g.source_count),0n)!==BigInt(w.retained_terms_count as number))return false;
  const clocks=[instant((b.window as Window).captured_at)!,instant((w.window as Window).captured_at)!];
  return (clocks[0]>clocks[1]?clocks[0]:clocks[1])===instant(capture);
}
