import {validMarketingRequest,validMarketingDraft,type MarketingRequest} from "./copilot-marketing-utils";
import {certificationInstant as instant} from "./certification-utils";
import {campaignDigest,validCampaignOriginal,sameCampaignOriginal,type CampaignOriginal} from "./marketing-campaign-utils";
type Storage=Pick<globalThis.Storage,"getItem"|"setItem"|"removeItem">;
type Options={institute:string;actor:string;storage:Storage;current:()=>boolean;get:(path:string)=>Promise<unknown>;post:(path:string,body:MarketingRequest)=>Promise<unknown>};
export type MarketingIntentState={status:"empty"|"invalid"}|{status:"frozen";terms:MarketingRequest};
export type MarketingIntentResult={status:"stale"|"busy"|"correctable"}|{status:"confirmed";original:CampaignOriginal};
export const marketingIntentKey=(institute:string,actor:string)=>`flowpilot.copilot-marketing.v1:${JSON.stringify([institute,actor])}`;
const flights=new WeakMap<Storage,Set<string>>();
const keys=(v:unknown,n:string):v is Record<string,any>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===n.split(" ").sort().join(" ");
export function createMarketingIntent({institute,actor,storage,current,get,post}:Options){
  if([institute,actor].some(v=>!v || v.trim()!==v || /[\x00-\x1f]/.test(v)) || Array.from(institute).length>80 || Array.from(actor).length>160)throw Error("Invalid marketing scope");
  const key=marketingIntentKey(institute,actor),base=`/marketing/institutes/${encodeURIComponent(institute)}/campaigns`;let correction=false;
  const recover=(r:MarketingRequest)=>`${base}/original/${encodeURIComponent(r.idempotency_key)}`;
  function state():MarketingIntentState{try{const raw=storage.getItem(key);if(raw===null)return {status:"empty"};const v=JSON.parse(raw);return keys(v,"institute actor terms") && v.institute===institute && v.actor===actor && validMarketingRequest(v.terms) ? {status:"frozen",terms:v.terms} : {status:"invalid"};}catch{return {status:"invalid"};}}
  function unchanged(r:MarketingRequest){const s=state();if(s.status!=="frozen" || JSON.stringify(s.terms)!==JSON.stringify(r))throw Error("Frozen marketing request changed");}
  async function verify(v:unknown,r:MarketingRequest):Promise<CampaignOriginal>{
    if(!await validCampaignOriginal(v,institute))throw Error("Invalid campaign original");const o=v as CampaignOriginal,q=o.request,d=o.revision,c=d.content;
    if(q.action!=="create" || q.campaign_id!==null || q.expected_revision_id!==null || d.previous_id!==null || d.state!=="DRAFT" || d.actor_id!==actor || q.reason!==r.reason || q.idempotency_key!==r.idempotency_key || c.audience.id!==r.ui_context.audience_id || c.template_original_id!==r.ui_context.template_original_id || instant(c.audience.captured_at)!>instant(d.created_at)! || await campaignDigest(c)!==r.expected_state_fingerprint)throw Error("Campaign differs from frozen draft terms");return o;
  }
  async function confirm(v:unknown,r:MarketingRequest,compact?:unknown):Promise<MarketingIntentResult>{
    const original=await verify(v,r);if(!current())return {status:"stale"};if(compact!==undefined && !await validMarketingDraft(compact,institute,original,r,actor))throw Error("Invalid compact draft response");
    const recovered=await verify(await get(recover(r)),r);if(!current())return {status:"stale"};const independent=await verify(await get(`${base}/${encodeURIComponent(original.revision.id)}`),r);if(!current())return {status:"stale"};
    if(!await sameCampaignOriginal(original,recovered,institute) || !await sameCampaignOriginal(original,independent,institute))throw Error("Independent campaign originals differ");unchanged(r);storage.removeItem(key);if(storage.getItem(key)!==null)throw Error("Marketing cleanup not verified");correction=false;return {status:"confirmed",original:independent};
  }
  async function run(work:()=>Promise<MarketingIntentResult>):Promise<MarketingIntentResult>{if(!current())return {status:"stale"};let active=flights.get(storage);if(!active){active=new Set();flights.set(storage,active);}if(active.has(key))return {status:"busy"};active.add(key);try{return await work();}finally{active.delete(key);}}
  async function submit(terms?:MarketingRequest){return run(async()=>{
    let s=state();if(s.status==="invalid")throw Error("Unreadable marketing intent blocks writes");if(s.status==="empty"){if(!validMarketingRequest(terms))throw Error("Explicit marketing request required");storage.setItem(key,JSON.stringify({institute,actor,terms:structuredClone(terms)}));s=state();if(s.status!=="frozen")throw Error("Marketing request not saved before POST");unchanged(terms);}
    if(s.status!=="frozen")throw Error("Missing marketing intent");const r=s.terms;correction=false;const old=await get(recover(r));if(!current())return {status:"stale"};unchanged(r);if(old!==null)return confirm(old,r);
    let compact:unknown;try{compact=await post("/copilot/prepare/marketing",structuredClone(r));}catch(e){if(e && typeof e==="object" && "status" in e && [400,404,422].includes(Number(e.status)))correction=true;throw e;}
    if(!current())return {status:"stale"};return confirm(await get(recover(r)),r,compact);
  });}
  async function correct(){return run(async()=>{const s=state();if(!correction || s.status!=="frozen")throw Error("Definitive rejection required");const old=await get(recover(s.terms));if(!current())return {status:"stale"};if(old!==null)return confirm(old,s.terms);unchanged(s.terms);storage.removeItem(key);if(storage.getItem(key)!==null)throw Error("Marketing cleanup not verified");correction=false;return {status:"correctable"};});}
  return {state,submit,correct,canCorrect:()=>correction};
}
