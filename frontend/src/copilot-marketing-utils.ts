import {certificationInstant as instant} from "./certification-utils";
import {creationUTC} from "./copilot-creation-utils";
import {revenueOriginalFingerprint as hash} from "./revenue-scenario-utils";
import {campaignDigest,validCampaignContent,validCampaignOriginal,type CampaignContent,type CampaignOriginal} from "./marketing-campaign-utils";

export type MarketingSelection={audience_id:string;template_original_id:string};
type Principal={actor_id:string;institute_id:string;role:"responsable_institut"};
export type MarketingPreview={principal:Principal;capability:"MARKETING_CAMPAIGN_DRAFT";selection:MarketingSelection;captured_at:string;channel:"sms"|"email"|"push";recipient_count:number;state_fingerprint:string;effect:"draft_preview_only_no_campaign_approval_contact_or_delivery"};
export type MarketingRequest={message:string;ui_context:MarketingSelection;expected_state_fingerprint:string;reason:string;idempotency_key:string};
export type MarketingDraft={principal:Principal;capability:"MARKETING_CAMPAIGN_DRAFT";selection:MarketingSelection;original_id:string;campaign_id:string;created_at:string;channel:"sms"|"email"|"push";recipient_count:number;state:"DRAFT";state_fingerprint:string;original_fingerprint:string;effect:"retained_draft_only_no_campaign_approval_contact_or_delivery"};
const keys=(v:unknown,n:string):v is Record<string,any>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===n.split(" ").sort().join(" ");
const text=(v:unknown,max=80,min=1):v is string=>typeof v==="string" && v.trim()===v && Array.from(v).length>=min && Array.from(v).length<=max && !/[\x00-\x1f]/.test(v);
const digest=(v:unknown):v is string=>typeof v==="string" && /^[0-9a-f]{64}$/.test(v);
const utc=(v:unknown):v is string=>typeof v==="string" && instant(v)!==undefined && creationUTC(v)===v;
export function validMarketingSelection(v:unknown):v is MarketingSelection{return keys(v,"audience_id template_original_id") && text(v.audience_id) && text(v.template_original_id);}
export function validMarketingRequest(v:unknown):v is MarketingRequest{return keys(v,"message ui_context expected_state_fingerprint reason idempotency_key") && text(v.message,2000) && validMarketingSelection(v.ui_context) && digest(v.expected_state_fingerprint) && text(v.reason,240,3) && text(v.idempotency_key,120);}
function principal(v:unknown,institute:string,actor?:string){return keys(v,"actor_id institute_id role") && text(institute) && v.institute_id===institute && text(v.actor_id,160) && (actor===undefined || v.actor_id===actor) && v.role==="responsable_institut";}
const selectionMatches=(v:MarketingSelection,s:MarketingSelection)=>v.audience_id===s.audience_id && v.template_original_id===s.template_original_id;
function contentMatches(content:CampaignContent,institute:string,s:MarketingSelection){return validCampaignContent(content,institute) && validMarketingSelection(s) && content.audience.id===s.audience_id && content.template_original_id===s.template_original_id;}
export async function validMarketingPreview(v:unknown,institute:string,selected:MarketingSelection,content:CampaignContent,actor?:string):Promise<boolean>{
  try{return keys(v,"principal capability selection captured_at channel recipient_count state_fingerprint effect") && principal(v.principal,institute,actor) && v.capability==="MARKETING_CAMPAIGN_DRAFT" && validMarketingSelection(v.selection) && selectionMatches(v.selection,selected) && utc(v.captured_at) && contentMatches(content,institute,selected) && instant(content.audience.captured_at)!<=instant(v.captured_at)! && v.channel===content.channel && v.recipient_count===content.audience.customer_ids.length && digest(v.state_fingerprint) && v.state_fingerprint===await campaignDigest(content) && v.effect==="draft_preview_only_no_campaign_approval_contact_or_delivery";}catch{return false;}
}
// The compact Copilot result is accepted only alongside the independent retained campaign original.
export async function validMarketingDraft(v:unknown,institute:string,original:CampaignOriginal,expected?:MarketingRequest,actor?:string):Promise<boolean>{
  try{
    if(!keys(v,"principal capability selection original_id campaign_id created_at channel recipient_count state state_fingerprint original_fingerprint effect") || !principal(v.principal,institute,actor) || v.capability!=="MARKETING_CAMPAIGN_DRAFT" || !validMarketingSelection(v.selection) || !text(v.original_id) || !text(v.campaign_id) || !utc(v.created_at) || !digest(v.state_fingerprint) || !digest(v.original_fingerprint) || v.state!=="DRAFT" || v.effect!=="retained_draft_only_no_campaign_approval_contact_or_delivery" || !await validCampaignOriginal(original,institute))return false;
    const r=original.revision,q=original.request;
    if(q.action!=="create" || r.state!=="DRAFT" || q.campaign_id!==null || q.expected_revision_id!==null || r.previous_id!==null || r.id!==v.original_id || r.campaign_id!==v.campaign_id || r.actor_id!==v.principal.actor_id || r.created_at!==v.created_at || !contentMatches(r.content,institute,v.selection) || instant(r.content.audience.captured_at)!>instant(r.created_at)! || v.channel!==r.content.channel || v.recipient_count!==r.content.audience.customer_ids.length || v.state_fingerprint!==await campaignDigest(r.content) || v.original_fingerprint!==await hash(original))return false;
    if(expected && (!validMarketingRequest(expected) || !selectionMatches(v.selection,expected.ui_context) || v.state_fingerprint!==expected.expected_state_fingerprint || q.reason!==expected.reason || q.idempotency_key!==expected.idempotency_key))return false;
    return true;
  }catch{return false;}
}
