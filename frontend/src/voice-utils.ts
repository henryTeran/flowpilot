export type VoicePreview={principal:{actor_id:string;institute_id:string;role:string};transcript:string;status:"silent"|"review_required";route:null|{status:"routed"|"clarification";process_id:string|null;framework_version:"1.5.1";request_digest:string;context_prepared:boolean};effect:"transcript_intent_only_no_domain_action"};
const keys=(v:any,n:string)=>v&&typeof v==="object"&&!Array.isArray(v)&&Object.keys(v).sort().join(" ")===n.split(" ").sort().join(" ");
export async function validVoicePreview(v:any,institute:string,actor:string):Promise<boolean>{
 if(!keys(v,"principal transcript status route effect")||!keys(v.principal,"actor_id institute_id role")||v.principal.actor_id!==actor||v.principal.institute_id!==institute||v.principal.role!=="responsable_institut"||typeof v.transcript!=="string"||v.effect!=="transcript_intent_only_no_domain_action")return false;
 if(v.status==="silent")return !v.transcript.trim()&&v.route===null;
 const r=v.route;if(v.status!=="review_required"||!v.transcript.trim()||Array.from(v.transcript).length>2000||!keys(r,"status process_id framework_version request_digest context_prepared")||r.framework_version!=="1.5.1")return false;
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(v.transcript)))).map(n=>n.toString(16).padStart(2,"0")).join("");
 return r.request_digest===digest&&(r.status==="routed"?typeof r.process_id==="string"&&!!r.process_id&&r.context_prepared===true:r.status==="clarification"&&r.process_id===null&&r.context_prepared===false);
}
