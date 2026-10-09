import {certificationInstant as instant} from "./certification-utils";
import {validRevenueSlot,type RevenueSlot} from "./revenue-slot-utils";
import {validReturnOpportunities,type ReturnOpportunities} from "./copilot-return-opportunity-utils";
import {validFollowUps,type FollowUps} from "./copilot-follow-up-utils";
export type OpportunitySelection={opportunity_source:"capacity";service_id:string;horizon_end:string}|{opportunity_source:"rebooking"}|{opportunity_source:"closures";start:string;end:string};
export type OpportunityFacts=RevenueSlot|ReturnOpportunities|FollowUps;
const keys=(v:unknown,names:string):v is Record<string,unknown>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===names.split(" ").sort().join(" ");
export function validOpportunitySelection(v:unknown):v is OpportunitySelection{
  if(keys(v,"opportunity_source"))return v.opportunity_source==="rebooking";
  if(keys(v,"opportunity_source service_id horizon_end"))return v.opportunity_source==="capacity" && typeof v.service_id==="string" && !!v.service_id && v.service_id.trim()===v.service_id && Array.from(v.service_id).length<=80 && !/[\x00-\x1f]/.test(v.service_id) && instant(v.horizon_end)!==undefined;
  if(!keys(v,"opportunity_source start end") || v.opportunity_source!=="closures")return false;
  const first=instant(v.start),last=instant(v.end);return first!==undefined && last!==undefined && first<last;
}
export function validOpportunityFacts(v:unknown,institute:string,selection:unknown,capture:string):v is OpportunityFacts{
  if(!validOpportunitySelection(selection) || instant(capture)===undefined)return false;
  if(selection.opportunity_source==="rebooking")return validReturnOpportunities(v,institute,capture);
  if(selection.opportunity_source==="closures")return validFollowUps(v,institute,selection,capture);
  return validRevenueSlot(v,institute,selection.service_id,selection.horizon_end) && instant(v.captured_at)===instant(capture);
}
