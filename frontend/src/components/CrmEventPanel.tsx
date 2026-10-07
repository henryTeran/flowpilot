import { useEffect,useRef,useState,type FormEvent } from "react";
import { apiGet,apiPost,ApiError } from "../api/client";
import { getAccessToken,getOperatorRole,getOperatorSubject } from "../api/session";
import { validEventRequest,validEventPage,matchesEventCapture,sameEventCapture,type EventRequest,type EventPage,type EventRevision,type EventCapture } from "../crm-event-utils";
export function CrmEventPanel({institute,customer}:{institute:string;customer:string}){
 if(!institute || !customer || getOperatorRole()!=="responsable_institut")return null;
 return <Editor key={JSON.stringify([institute,customer,getAccessToken()])} institute={institute} customer={customer}/>;
}
const states={scheduled:"Planifié",due:"À traiter",blocked:"Source à vérifier",cancelled:"Annulé",expired:"Expiré",processed:"Traité en interne"};
const triggers={birthday:"Anniversaire",post_service:"Suivi de soin",rebooking:"Rebooking",inactivity:"Inactivité",package_expiry:"Expiration package",subscription_renewal:"Renouvellement abonnement"};
const actions={reconcile:"Réconcilier les sources",cancel:"Annuler l'occurrence",process:"Traiter l'occurrence",process_due:"Traiter les échéances"};
const reasons={candidate:"Selon la source observée",source_uncertain:"Source insuffisante",rule_disabled:"Règle désactivée",package_exhausted:"Package épuisé",occurrence_expired:"Période terminée",superseded:"Remplacé par une occurrence plus récente",birthday_declared_unknown:"Anniversaire déclaré inconnu",explicit_cancellation:"Annulation explicite",already_processed:"Traitement interne enregistré"};
function Editor({institute,customer}:{institute:string;customer:string}){
 const token=getAccessToken(),actor=getOperatorSubject(),base=`/crm/institutes/${encodeURIComponent(institute)}/customers/${encodeURIComponent(customer)}`;
 const storage=`flowpilot.crm-event-request:${JSON.stringify([institute,customer,actor])}`;
 const [saved,save]=useState<{terms?:EventRequest;invalid?:boolean}>(()=>{try{const raw=sessionStorage.getItem(storage);if(!raw)return {};const v=JSON.parse(raw);return validEventRequest(v) && Object.keys(v).length===5 ? {terms:v} : {invalid:true};}catch{return {invalid:true};}});
 const [page,setPage]=useState<EventPage>(),[offset,setOffset]=useState(0),[loading,setLoading]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<string>(),[success,setSuccess]=useState<string>(),[rejected,setRejected]=useState(false);
 const [choice,setChoice]=useState<{action:EventRequest["action"];revision?:EventRevision}>(),[reason,setReason]=useState("");
 const alive=useRef(false),sequence=useRef(0),pending=useRef(false);
 const current=()=>alive.current && token===getAccessToken();const frozen=busy || !!saved.terms || !!saved.invalid;
 async function read(next=offset){const seq=++sequence.current;setLoading(true);setPage(undefined);
  try{const v=await apiGet<unknown>(`${base}/events?offset=${next}&limit=20`);if(!current() || seq!==sequence.current)return false;
   if(!await validEventPage(v,institute,customer,next,20))throw new Error("Page des événements à vérifier.");if(!current() || seq!==sequence.current)return false;
   setPage(v as EventPage);setOffset(next);return true;
  }catch(e){if(current() && seq===sequence.current)setError(e instanceof Error?e.message:"Lecture indisponible.");return false;}
  finally{if(current() && seq===sequence.current)setLoading(false);}
 }
 useEffect(()=>{alive.current=true;void read(0);return()=>{alive.current=false;sequence.current++;};},[]);
 async function run(terms:EventRequest){if(!current() || pending.current || !actor || saved.invalid || !validEventRequest(terms))return;
  pending.current=true;setBusy(true);setError(undefined);setSuccess(undefined);setRejected(false);let posting=false,returned=false;
  try{const raw=JSON.stringify(terms);sessionStorage.setItem(storage,raw);save({terms});const path=`${base}/event-captures/original/${encodeURIComponent(terms.idempotency_key)}`;
   let receipt=await apiGet<unknown>(path);if(!current())return;
   if(receipt===null){posting=true;receipt=await apiPost<unknown>(`${base}/event-captures`,terms);returned=true;}if(!current())return;
   if(!await matchesEventCapture(receipt,institute,customer,terms,actor))throw new Error("Capture originale à vérifier.");if(!current())return;
   const verified=await apiGet<unknown>(path);if(!current())return;
   if(!await sameEventCapture(receipt,verified,institute,customer))throw new Error("Original relu à vérifier.");if(!current())return;
   const byId=await apiGet<unknown>(`${base}/event-captures/${encodeURIComponent((receipt as EventCapture).id)}`);if(!current())return;
   if(!await sameEventCapture(receipt,byId,institute,customer))throw new Error("Capture par identifiant à vérifier.");if(!current())return;
   if(!await read(0) || !current())throw new Error("Relisez les événements courants avant de clore la demande.");
   if(sessionStorage.getItem(storage)!==raw)throw new Error("Demande conservée à vérifier.");
   sessionStorage.removeItem(storage);save({});setChoice(undefined);setSuccess("Capture originale vérifiée et événements courants relus.");
  }catch(e){if(current()){setError(e instanceof Error?e.message:"Demande à reprendre.");setRejected(posting && !returned && e instanceof ApiError && [400,422].includes(e.status));}}
  finally{pending.current=false;if(current())setBusy(false);}
 }
 function prepare(action:EventRequest["action"],revision?:EventRevision){if(frozen || loading || !page)return;setChoice({action,revision});setReason("");setSuccess(undefined);setError(undefined);}
 function submit(e:FormEvent){e.preventDefault();if(!choice || frozen || loading || !page)return;
  if(choice.revision && !page.revisions.some(r=>r.id===choice.revision!.id && r.event_key===choice.revision!.event_key)){setError("La révision a changé : relisez puis choisissez l'action.");return;}
  const terms={action:choice.action,event_key:choice.revision?.event_key || null,expected_revision_id:choice.revision?.id || null,reason:reason.trim(),idempotency_key:crypto.randomUUID()};
  if(validEventRequest(terms))void run(terms);
 }
 return <section aria-label="Événements CRM" style={{overflowWrap:"anywhere"}}><h3>Événements du cycle de vie</h3><p>Traitement interne uniquement. Aucun message envoyé. Les sources incomplètes restent à vérifier.</p>
  <button disabled={busy || loading} onClick={()=>{setError(undefined);void read();}}>Actualiser les événements</button>
  {loading && <p role="status">Lecture des événements...</p>}{error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
  {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
  {saved.terms && <><p>Demande conservée : {saved.terms.reason}</p><button disabled={busy} onClick={()=>void run(saved.terms!)}>Reprendre l'action conservée</button></>}
  {rejected && <button onClick={()=>{sessionStorage.removeItem(storage);save({});setRejected(false);setChoice(undefined);}}>Corriger l'action refusée</button>}
  {page && <><p>{page.total} événements internes | affichage {page.revisions.length ? offset+1 : 0} à {offset+page.revisions.length}</p>
   <button disabled={frozen || loading} onClick={()=>prepare("reconcile")}>Réconcilier les sources</button><button disabled={frozen || loading} onClick={()=>prepare("process_due")}>Traiter les échéances internes (20 maximum)</button>
   {page.revisions.map(r=><article key={r.id}><h4>{triggers[r.decision.candidate.rule.trigger]} : {states[r.decision.state]}</h4><p>Échéance : {r.decision.candidate.due_at} | source : {r.decision.candidate.source.source_id}</p><p>Occurrence {r.event_key} | révision {r.id} | capture {r.capture_id}</p><p>Motif : {reasons[r.decision.reason]} | évaluation : {r.decision.evaluated_at}</p>
    <button disabled={frozen || loading || r.decision.state!=="due"} onClick={()=>prepare("process",r)}>Traiter cette occurrence</button><button disabled={frozen || loading || r.decision.state==="processed"} onClick={()=>prepare("cancel",r)}>Annuler cette occurrence</button></article>)}
   <button disabled={busy || loading || offset===0} onClick={()=>void read(Math.max(0,offset-20))}>Événements précédents</button><button disabled={busy || loading || offset+20>=page.total} onClick={()=>void read(offset+20)}>Événements suivants</button>
  </>}
  {choice && <form onSubmit={submit}><fieldset disabled={frozen || loading}><legend>Action interne explicite : {actions[choice.action]}</legend>{choice.revision && <p>Révision ciblée : {choice.revision.id}</p>}<label>Motif de l'action<input required minLength={3} maxLength={240} value={reason} onChange={e=>setReason(e.target.value)}/></label><button disabled={!actor || !page}>Enregistrer l'action interne</button></fieldset></form>}
 </section>;
}
