import {validCreationRequest,validCreationEnvelope,type CreationRequest,type CreationEnvelope} from "./copilot-creation-utils";
import {validCreationApprovalState,validCreationDecision,validCreationExecution,type CreationApprovalState,type CreationExecutionEnvelope} from "./copilot-creation-lifecycle";
import {validBaseDecisionRequest,validBaseExecutionRequest,type BaseDecisionRequest,type BaseDecisionEnvelope,type BaseExecutionRequest} from "./base-cancellation-utils";

type Storage=Pick<globalThis.Storage,"getItem"|"setItem"|"removeItem">;
type Mode="operation"|"decision"|"execution";
export type CreationPreparationRequest={message:string;operation:CreationRequest};
type Terms=CreationPreparationRequest|BaseDecisionRequest|BaseExecutionRequest;
type Receipt=CreationEnvelope|BaseDecisionEnvelope|CreationExecutionEnvelope;
type Saved<T>={institute:string;actor:string;mode:Mode;terms:T};
export type CreationIntentState<T>={status:"empty"|"invalid"}|{status:"frozen";value:Saved<T>};
export type CreationIntentResult<R>={status:"stale"|"busy"|"correctable"}|{status:"confirmed";receipt:R};
type Options<T>={institute:string;actor:string;storage:Storage;current:()=>boolean;get:(path:string)=>Promise<unknown>;post:(path:string,terms:T)=>Promise<unknown>};
const flights=new WeakMap<Storage,Set<string>>();
const keys=(v:unknown,names:string):v is Record<string,any>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===names.split(" ").sort().join(" ");
export function validCreationPreparation(v:unknown):v is CreationPreparationRequest{
  return keys(v,"message operation") && typeof v.message==="string" && !!v.message && v.message.trim()===v.message && Array.from(v.message).length<=2000 && validCreationRequest(v.operation);
}
const routes={operation:{recover:"sensitive-operation-by-key",valid:validCreationPreparation},decision:{recover:"approval-by-key",valid:validBaseDecisionRequest},execution:{recover:"execution-by-key",valid:validBaseExecutionRequest}};
export const creationIntentKey=(institute:string,actor:string,mode:Mode)=>`flowpilot.copilot-creation.v1:${JSON.stringify([institute,actor,mode])}`;
function createIntent<T extends Terms,R extends Receipt>(mode:Mode,options:Options<T>){
  const {institute,actor,storage,current,get,post}=options;
  if([institute,actor].some(v=>!v || v.trim()!==v || /[\x00-\x1f]/.test(v)) || Array.from(institute).length>80 || Array.from(actor).length>160)throw Error("Invalid creation scope");
  const key=creationIntentKey(institute,actor,mode),base=`/base/institutes/${encodeURIComponent(institute)}`,route=routes[mode];let canCorrect=false;
  const requestKey=(terms:T)=>mode==="operation" ? (terms as CreationPreparationRequest).operation.idempotency_key : (terms as BaseDecisionRequest|BaseExecutionRequest).idempotency_key;
  const byKey=(terms:T)=>`${base}/${route.recover}?${new URLSearchParams({key:requestKey(terms)})}`;
  function state():CreationIntentState<T>{try{const raw=storage.getItem(key);if(raw===null)return {status:"empty"};const v=JSON.parse(raw);return keys(v,"institute actor mode terms") && v.institute===institute && v.actor===actor && v.mode===mode && route.valid(v.terms) ? {status:"frozen",value:v as Saved<T>} : {status:"invalid"};}catch{return {status:"invalid"};}}
  function unchanged(terms:T){const saved=state();if(saved.status!=="frozen" || JSON.stringify(saved.value.terms)!==JSON.stringify(terms))throw Error("Frozen creation terms changed");}
  async function approvalState(operation:string){const v=await get(`${base}/sensitive-operations/${encodeURIComponent(operation)}/approval-state`);if(!await validCreationApprovalState(v,institute))throw Error("Invalid creation approval state");return v as CreationApprovalState;}
  async function verify(v:unknown,terms:T):Promise<R>{
    let valid=false;
    if(mode==="operation")valid=await validCreationEnvelope(v,institute,(terms as CreationPreparationRequest).operation,actor);
    else{
      const history=await approvalState((terms as BaseDecisionRequest|BaseExecutionRequest).operation_id);
      if(mode==="decision")valid=await validCreationDecision(v,institute,history.operation,terms as BaseDecisionRequest,actor) && history.decisions.some(d=>d.original.id===(v as BaseDecisionEnvelope).original.id && d.fingerprint===(v as BaseDecisionEnvelope).fingerprint);
      else valid=await validCreationExecution(v,institute,history,terms as BaseExecutionRequest,actor);
    }
    if(!valid)throw Error("Creation receipt differs from exact frozen terms or history");return v as R;
  }
  async function confirm(v:unknown,terms:T):Promise<CreationIntentResult<R>>{
    const receipt=await verify(v,terms);if(!current())return {status:"stale"};
    const recovered=await verify(await get(byKey(terms)),terms);if(!current())return {status:"stale"};
    if(receipt.original.id!==recovered.original.id || receipt.fingerprint!==recovered.fingerprint)throw Error("Changed recovery receipt");
    let independent:R;
    if(mode==="decision"){const history=await approvalState((terms as BaseDecisionRequest).operation_id);independent=await verify(history.decisions.find(d=>d.original.id===receipt.original.id),terms);}
    else {const path=mode==="operation" ? `/sensitive-operations/${encodeURIComponent(receipt.original.id)}` : `/sensitive-operations/${encodeURIComponent((terms as BaseExecutionRequest).operation_id)}/execution`;independent=await verify(await get(`${base}${path}`),terms);}
    if(!current())return {status:"stale"};
    if(receipt.original.id!==independent.original.id || receipt.fingerprint!==independent.fingerprint)throw Error("Changed independent receipt");
    unchanged(terms);storage.removeItem(key);if(storage.getItem(key)!==null)throw Error("Creation intent cleanup requires verification");canCorrect=false;return {status:"confirmed",receipt:independent};
  }
  async function run(action:()=>Promise<CreationIntentResult<R>>):Promise<CreationIntentResult<R>>{
    if(!current())return {status:"stale"};let active=flights.get(storage);if(!active){active=new Set();flights.set(storage,active);}if(active.has(key))return {status:"busy"};active.add(key);try{return await action();}finally{active.delete(key);}
  }
  async function submit(newTerms?:T):Promise<CreationIntentResult<R>>{return run(async()=>{
    let saved=state();if(saved.status==="invalid")throw Error("Unreadable saved creation intent blocks writes");
    if(saved.status==="empty"){
      if(!route.valid(newTerms))throw Error("Explicit valid creation request required");const value={institute,actor,mode,terms:structuredClone(newTerms!)};storage.setItem(key,JSON.stringify(value));saved=state();if(saved.status!=="frozen")throw Error("Creation intent could not be saved before sending");unchanged(value.terms);
    }
    if(saved.status!=="frozen")throw Error("Missing frozen creation intent");const terms=saved.value.terms;canCorrect=false;
    if(!current())return {status:"stale"};const recovered=await get(byKey(terms));if(!current())return {status:"stale"};unchanged(terms);if(recovered!==null)return confirm(recovered,terms);
    let created:unknown;try{created=await post(mode==="operation" ? "/copilot/prepare" : mode==="execution" ? "/copilot/execute" : `${base}/approvals`,structuredClone(terms));}
    catch(error){if(error && typeof error==="object" && "status" in error && [400,404,422].includes(Number(error.status)))canCorrect=true;throw error;}
    if(!current())return {status:"stale"};return confirm(created,terms);
  });}
  async function correct():Promise<CreationIntentResult<R>>{return run(async()=>{
    const saved=state();if(!canCorrect || saved.status!=="frozen")throw Error("Definitive creation rejection required");const terms=saved.value.terms,recovered=await get(byKey(terms));if(!current())return {status:"stale"};if(recovered!==null)return confirm(recovered,terms);
    unchanged(terms);storage.removeItem(key);if(storage.getItem(key)!==null)throw Error("Creation intent cleanup requires verification");canCorrect=false;return {status:"correctable"};
  });}
  return {state,submit,correct,canCorrect:()=>canCorrect};
}
export const createCreationPreparationIntent=(options:Options<CreationPreparationRequest>)=>createIntent<CreationPreparationRequest,CreationEnvelope>("operation",options);
export const createCreationDecisionIntent=(options:Options<BaseDecisionRequest>)=>createIntent<BaseDecisionRequest,BaseDecisionEnvelope>("decision",options);
export const createCreationExecutionIntent=(options:Options<BaseExecutionRequest>)=>createIntent<BaseExecutionRequest,CreationExecutionEnvelope>("execution",options);
