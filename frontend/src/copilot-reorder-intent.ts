import {validReorderRequest,validReorderReceipt,type ReorderRequest,type ReorderReceipt} from "./copilot-reorder-utils";
import {revenueOriginalFingerprint as hash} from "./revenue-scenario-utils";
export type ReorderPreparationRequest={message:string;proposal:ReorderRequest};
type Storage=Pick<globalThis.Storage,"getItem"|"setItem"|"removeItem">;
type Options={institute:string;actor:string;storage:Storage;current:()=>boolean;get:(path:string)=>Promise<unknown>;post:(path:string,body:ReorderPreparationRequest)=>Promise<unknown>};
export type ReorderIntentState={status:"empty"|"invalid"}|{status:"frozen";terms:ReorderPreparationRequest};
export type ReorderIntentResult={status:"stale"|"busy"|"correctable"}|{status:"confirmed";original:ReorderReceipt};
export const reorderIntentKey=(institute:string,actor:string)=>`flowpilot.copilot-reorder.v1:${JSON.stringify([institute,actor])}`;
const flights=new WeakMap<Storage,Set<string>>();
export function validReorderPreparation(v:unknown):v is ReorderPreparationRequest{return keys(v,"message proposal") && typeof v.message==="string" && !!v.message && v.message.trim()===v.message && Array.from(v.message).length<=2000 && validReorderRequest(v.proposal);}
const keys=(v:unknown,n:string):v is Record<string,any>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===n.split(" ").sort().join(" ");
export function createReorderIntent({institute,actor,storage,current,get,post}:Options){
  if([institute,actor].some(v=>!v || v.trim()!==v || /[\x00-\x1f]/.test(v)) || Array.from(institute).length>80 || Array.from(actor).length>160)throw Error("Invalid reorder scope");
  const key=reorderIntentKey(institute,actor),base="/copilot";let correction=false;
  const recover=(r:ReorderPreparationRequest)=>`${base}/reorder-proposal-by-key?${new URLSearchParams({key:r.proposal.idempotency_key})}`;
  function state():ReorderIntentState{try{const raw=storage.getItem(key);if(raw===null)return {status:"empty"};const v=JSON.parse(raw);return keys(v,"institute actor terms") && v.institute===institute && v.actor===actor && validReorderPreparation(v.terms) ? {status:"frozen",terms:v.terms} : {status:"invalid"};}catch{return {status:"invalid"};}}
  function unchanged(r:ReorderPreparationRequest){const s=state();if(s.status!=="frozen" || JSON.stringify(s.terms)!==JSON.stringify(r))throw Error("Frozen reorder request changed");}
  async function verify(v:unknown,r:ReorderPreparationRequest):Promise<ReorderReceipt>{if(!await validReorderReceipt(v,institute,r.proposal,actor))throw Error("Proposal differs from frozen request");return v as ReorderReceipt;}
  async function confirm(v:unknown,r:ReorderPreparationRequest,compact?:unknown):Promise<ReorderIntentResult>{
    const original=await verify(v,r);if(!current())return {status:"stale"};if(compact!==undefined && await hash(await verify(compact,r))!==await hash(original))throw Error("Changed proposal response");
    const recovered=await verify(await get(recover(r)),r);if(!current())return {status:"stale"};const independent=await verify(await get(`${base}/reorder-proposals/${encodeURIComponent(original.original.id)}`),r);if(!current())return {status:"stale"};
    if(await hash(original)!==await hash(recovered) || await hash(original)!==await hash(independent))throw Error("Independent proposal originals differ");unchanged(r);storage.removeItem(key);if(storage.getItem(key)!==null)throw Error("Reorder cleanup not verified");correction=false;return {status:"confirmed",original:independent};
  }
  async function run(work:()=>Promise<ReorderIntentResult>):Promise<ReorderIntentResult>{if(!current())return {status:"stale"};let active=flights.get(storage);if(!active){active=new Set();flights.set(storage,active);}if(active.has(key))return {status:"busy"};active.add(key);try{return await work();}finally{active.delete(key);}}
  async function submit(terms?:ReorderPreparationRequest){return run(async()=>{
    let s=state();if(s.status==="invalid")throw Error("Unreadable reorder intent blocks writes");if(s.status==="empty"){if(!validReorderPreparation(terms))throw Error("Explicit reorder request required");storage.setItem(key,JSON.stringify({institute,actor,terms:structuredClone(terms)}));s=state();if(s.status!=="frozen")throw Error("Reorder request not saved before POST");unchanged(terms);}
    if(s.status!=="frozen")throw Error("Missing reorder intent");const r=s.terms;correction=false;const old=await get(recover(r));if(!current())return {status:"stale"};unchanged(r);if(old!==null)return confirm(old,r);
    let compact:unknown;try{compact=await post("/copilot/prepare/reorder",structuredClone(r));}catch(e){if(e && typeof e==="object" && "status" in e && [400,404,422].includes(Number(e.status)))correction=true;throw e;}
    if(!current())return {status:"stale"};return confirm(await get(recover(r)),r,compact);
  });}
  async function correct(){return run(async()=>{const s=state();if(!correction || s.status!=="frozen")throw Error("Definitive rejection required");const old=await get(recover(s.terms));if(!current())return {status:"stale"};if(old!==null)return confirm(old,s.terms);unchanged(s.terms);storage.removeItem(key);if(storage.getItem(key)!==null)throw Error("Reorder cleanup not verified");correction=false;return {status:"correctable"};});}
  return {state,submit,correct,canCorrect:()=>correction};
}
