import { certificationInstant as instant } from "./certification-utils";
import { capacityDayWindow } from "./revenue-capacity-utils";

export type Commitment = {kind:"appointment"|"session"|"absence"|"reservation";id:string;start_at:string;end_at:string};
export type Conflict = {left:Commitment;right:Commitment;start_at:string;end_at:string;duration_us:string};
export type ConflictRead = {institute_id:string;employee_id?:string;resource_id?:string;day:string;captured_at:string;start_at:string;end_at:string;
  source_digest:string;source_count:number;invalid_source_count:number;overdue_open_source_count?:number;overdue_unreleased_source_count?:number;
  overlap_count:number;overlaps:Conflict[];page_limit:50;basis:string;physical_activity_proven:false;
  resource_conflicts_covered?:false;complete_institute_conflict_coverage?:false;booking_authorized?:false;resource_status?:string};
const keys=(v:unknown,names:string):v is Record<string,unknown>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===names.split(" ").sort().join(" ");
const id=(v:unknown):v is string=>typeof v==="string" && !!v && v.trim()===v && Array.from(v).length<=80 && !/[\x00-\x1f]/.test(v);
const count=(v:unknown):v is number=>Number.isSafeInteger(v) && (v as number)>=0;
function commitment(v:unknown,resource:boolean):v is Commitment {
  if(!keys(v,"kind id start_at end_at") || !id(v.id) || !(resource ? v.kind==="reservation" : ["appointment","session","absence"].includes(v.kind as string)))return false;
  const start=instant(v.start_at),end=instant(v.end_at);return start!==undefined && end!==undefined && start<end;
}
export function validConflictRead(v:unknown,institute:string,day:string,timezone:string,selection:{employee_id?:string;resource_id?:string},capture:string):v is ConflictRead {
  const resource=selection.resource_id!==undefined,selected=resource ? selection.resource_id : selection.employee_id;
  if(!id(selected) || Object.keys(selection).join()!==(resource ? "resource_id" : "employee_id"))return false;
  const common="institute_id day captured_at start_at end_at source_digest source_count invalid_source_count overlap_count overlaps page_limit basis physical_activity_proven";
  if(!keys(v,common+(resource ? " resource_id resource_status overdue_unreleased_source_count complete_institute_conflict_coverage booking_authorized" : " employee_id overdue_open_source_count resource_conflicts_covered")))return false;
  const window=capacityDayWindow(day,timezone),captured=instant(capture);
  if(!window || captured===undefined || v.institute_id!==institute || v.day!==day || v[resource ? "resource_id" : "employee_id"]!==selected
    || instant(v.captured_at)!==captured || instant(v.start_at)!==instant(window.start) || instant(v.end_at)!==instant(window.end)
    || v.page_limit!==50 || v.physical_activity_proven!==false || typeof v.source_digest!=="string" || !/^[0-9a-f]{64}$/.test(v.source_digest)
    || !count(v.source_count) || v.source_count>1000 || !count(v.invalid_source_count) || !count(v.overlap_count)
    || !count(v[resource ? "overdue_unreleased_source_count" : "overdue_open_source_count"]))return false;
  if(resource ? v.basis!=="current_unreleased_resource_reservations_half_open" || v.complete_institute_conflict_coverage!==false || v.booking_authorized!==false || !["active","inactive","maintenance"].includes(v.resource_status as string)
    : v.basis!=="current_recorded_employee_commitments_half_open" || v.resource_conflicts_covered!==false)return false;
  if(!Array.isArray(v.overlaps) || v.overlaps.length!==Math.min(50,v.overlap_count))return false;
  const seen=new Set<string>(),first=instant(window.start)!,last=instant(window.end)!;
  return v.overlaps.every(o=>{
    if(!keys(o,"left right start_at end_at duration_us") || !commitment(o.left,resource) || !commitment(o.right,resource)
      || o.left.kind===o.right.kind && o.left.id===o.right.id || o.left.kind==="absence" && o.right.kind==="absence")return false;
    const start=instant(o.start_at),end=instant(o.end_at);
    const expectedStart=[first,instant(o.left.start_at)!,instant(o.right.start_at)!].reduce((a,b)=>a>b?a:b);
    const expectedEnd=[last,instant(o.left.end_at)!,instant(o.right.end_at)!].reduce((a,b)=>a<b?a:b);
    const pair=[`${o.left.kind}:${o.left.id}`,`${o.right.kind}:${o.right.id}`].sort().join("|");
    if(start===undefined || end===undefined || start>=end || start!==expectedStart || end!==expectedEnd || o.duration_us!==String(end-start) || seen.has(pair))return false;
    seen.add(pair);return true;
  });
}
