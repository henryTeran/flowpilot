import {useEffect,useRef,useState} from "react";
import {apiGet,apiPost} from "../api/client";
import {getAccessToken,getOperatorInstitute,getOperatorRole,getOperatorSubject} from "../api/session";
import {exactKeys,exactId} from "../copilot-read-utils";
import {creationUTC,validCreationDiscovery} from "../copilot-creation-utils";
import {instituteInstants} from "../institute-calendar";
import {validMoveRequest,validMoveEnvelope,validMoveSelection,validMovePreview,type MoveSelection,type MovePreview,type MoveEnvelope} from "../copilot-move-utils";
import {createMovePreparationIntent,createMoveDecisionIntent,createMoveExecutionIntent} from "../copilot-move-intent";
import {validBaseDecisionRequest,validBaseExecutionRequest} from "../base-cancellation-utils";
import {validMoveExecutionDiscovery,validMoveApprovalState,validMoveExecution,type MoveApprovalState,type MoveExecutionEnvelope} from "../copilot-move-lifecycle";
import type {Employee,Service} from "../types";
type Props={initialMessage?:string;institute:string;timezone:string;employees:Employee[];services:Service[]};
const storage={getItem:(k:string)=>sessionStorage.getItem(k),setItem:(k:string,v:string)=>sessionStorage.setItem(k,v),removeItem:(k:string)=>sessionStorage.removeItem(k)};
export function CopilotMovePanel(props:Props){
  if(getOperatorRole()!=="responsable_institut" || !getOperatorSubject() || props.institute!==getOperatorInstitute())return null;
  return <Panel key={JSON.stringify([props.institute,props.timezone,getAccessToken()])} {...props}/>;
}
function Panel({initialMessage="",institute,timezone,employees,services}:Props){
  const token=getAccessToken(),actor=getOperatorSubject()!,mounted=useRef(false),sequence=useRef(0),flight=useRef(false);
  const [allowed,setAllowed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<string>();
  const [message,setMessage]=useState(initialMessage),[employee,setEmployee]=useState(""),[service,setService]=useState(""),[local,setLocal]=useState(""),[occurrence,setOccurrence]=useState("");
  const [appointment,setAppointment]=useState("");
  const [preview,setPreview]=useState<MovePreview>();
  const [deadline,setDeadline]=useState(""),[deadlineOccurrence,setDeadlineOccurrence]=useState(""),[reason,setReason]=useState(""),[identifier,setIdentifier]=useState("");
  const [operation,setOperation]=useState<MoveEnvelope>();
  const [history,setHistory]=useState<MoveApprovalState>(),[execution,setExecution]=useState<MoveExecutionEnvelope>();
  function clearLifecycle(){setHistory(undefined);setExecution(undefined);}
  const scopeCurrent=()=>mounted.current && token===getAccessToken() && actor===getOperatorSubject() && institute===getOperatorInstitute() && getOperatorRole()==="responsable_institut";
  const [driver]=useState(()=>createMovePreparationIntent({institute,actor,storage,current:scopeCurrent,get:path=>apiGet(path),post:(path,body)=>apiPost(path,body)}));
  const [saved,setSaved]=useState(()=>driver.state());
  const [decisionDriver]=useState(()=>createMoveDecisionIntent({institute,actor,storage,current:scopeCurrent,get:path=>apiGet(path),post:(path,body)=>apiPost(path,body)}));
  const [decisionSaved,setDecisionSaved]=useState(()=>decisionDriver.state()),[decisionReason,setDecisionReason]=useState("");
  const [executionDriver]=useState(()=>createMoveExecutionIntent({institute,actor,storage,current:scopeCurrent,get:path=>apiGet(path),post:(path,body)=>apiPost(path,body)}));
  const [executionSaved,setExecutionSaved]=useState(()=>executionDriver.state()),[executionReason,setExecutionReason]=useState(""),[executionAllowed,setExecutionAllowed]=useState(false);
  const pending=saved.status!=="empty" || decisionSaved.status!=="empty" || executionSaved.status!=="empty";
  const deadlines=deadline ? instituteInstants(deadline.slice(0,10),deadline.slice(11,16),timezone) : [];
  const times=local ? instituteInstants(local.slice(0,10),local.slice(11,16),timezone) : [];
  const current=(seq:number)=>mounted.current && sequence.current===seq && token===getAccessToken() && actor===getOperatorSubject() && institute===getOperatorInstitute() && getOperatorRole()==="responsable_institut";
  function edit(){sequence.current++;setPreview(undefined);setOperation(undefined);clearLifecycle();setIdentifier("");setError(undefined);}
  useEffect(()=>{mounted.current=true;const seq=++sequence.current;setBusy(true);void apiGet<unknown>("/copilot/preparation-capabilities").then(v=>{if(!current(seq))return;if(!validCreationDiscovery(v))throw Error("Invalid registration");setAllowed(true);}).catch(()=>{if(current(seq))setError("Préparations autorisées indisponibles. Rouvrez ce parcours pour les relire.");}).finally(()=>{if(current(seq))setBusy(false);});return()=>{mounted.current=false;sequence.current++;};},[]);
  async function review(){
    if(flight.current || pending || !allowed || !message.trim())return;
    const start=times.length===1 ? times[0] : times.includes(occurrence) ? occurrence : undefined;
    if(!start){setError("Choisissez une heure locale valide et son occurrence si elle se répète.");return;}
    const selection:MoveSelection={appointment_id:appointment,employee_id:employee||null,service_id:service||null,start_time:start};
    if(!validMoveSelection(selection) || employee && !employees.some(e=>e.id===employee && e.institute_id===institute) || service && !services.some(s=>s.id===service && s.status==="active")){setError("Relisez la référence du rendez-vous et les choix proposés.");return;}
    flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);setPreview(undefined);
    try{const v=await apiPost<unknown>("/copilot/prepare-preview/move",{message:message.trim(),ui_context:selection});if(!current(seq))return;if(!await validMovePreview(v,institute,selection,actor))throw Error("Invalid preview");if(current(seq))setPreview(v as MovePreview);}
    catch{if(current(seq))setError("Créneau indisponible ou lecture à vérifier. Relisez les sélections puis relancez la vérification.");}finally{flight.current=false;if(current(seq))setBusy(false);}
  }
  async function prepare(correction=false){
    if(flight.current || decisionSaved.status!=="empty" || executionSaved.status!=="empty" || !allowed || !scopeCurrent())return;
    if(saved.status==="empty"){
      const selected=deadlines.length===1 ? deadlines[0] : deadlines.includes(deadlineOccurrence) ? deadlineOccurrence : undefined;
      if(!preview || !selected || Date.parse(selected)<=Date.now()){setError("Relisez les termes et choisissez une échéance future valide, avec son occurrence si elle se répète.");return;}
      if(reason.trim()!==reason || Array.from(reason).length<3 || Array.from(reason).length>240 || /[\x00-\x1f]/.test(reason)){setError("Saisissez un motif exact de 3 à 240 caractères, sans espaces de bord.");return;}
    }
    flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);setOperation(undefined);clearLifecycle();
    try{
      let result;
      if(correction)result=await driver.correct();
      else if(saved.status!=="empty")result=await driver.submit();
      else{
        const selected=deadlines.length===1 ? deadlines[0] : deadlineOccurrence;
        const terms={capability:"APPOINTMENT_MOVE" as const,selection:preview!.selection,expected_state_fingerprint:preview!.state_fingerprint,valid_until:creationUTC(selected)!,reason,idempotency_key:crypto.randomUUID()};
        if(!validMoveRequest(terms))throw Error("Invalid preparation reason");
        result=await driver.submit({message:message.trim(),operation:terms});
      }
      if(!current(seq))return;
      if(result.status==="confirmed"){setOperation(result.receipt);setIdentifier(result.receipt.original.id);setPreview(undefined);setReason("");}
      else if(result.status==="correctable"){setPreview(undefined);setReason("");setError("Rejet vérifié. Relisez les termes avant une nouvelle préparation.");}
      else if(result.status==="busy")setError("Une reprise est déjà en cours. Conservez la même demande.");
    }catch{if(current(seq))setError("Préparation à vérifier. La demande conservée reste inchangée ; reprenez la preuve avant une nouvelle préparation.");}
    finally{flight.current=false;if(current(seq)){setSaved(driver.state());setBusy(false);}}
  }
  async function readOperation(){
    if(flight.current || pending || !allowed || !exactId(identifier))return;flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);setPreview(undefined);setOperation(undefined);clearLifecycle();
    try{const v=await apiGet<unknown>(`/base/institutes/${encodeURIComponent(institute)}/sensitive-operations/${encodeURIComponent(identifier)}`);if(!current(seq))return;if(!await validMoveEnvelope(v,institute) || (v as MoveEnvelope).original.id!==identifier)throw Error("Invalid original");if(current(seq))setOperation(v as MoveEnvelope);}
    catch{if(current(seq))setError("Préparation indisponible ou à vérifier. Relisez sa référence.");}finally{flight.current=false;if(current(seq))setBusy(false);}
  }
  async function readLifecycle(){
    if(flight.current || pending || !allowed || !operation)return;
    flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);clearLifecycle();
    try{await loadLifecycle(operation,seq);}
    catch{if(current(seq))setError("Décisions ou preuve d’exécution indisponibles ou à vérifier. Relisez la préparation puis son historique.");}
    finally{flight.current=false;if(current(seq))setBusy(false);}
  }
  async function loadLifecycle(selected:MoveEnvelope,seq:number){
    const base=`/base/institutes/${encodeURIComponent(institute)}/sensitive-operations/${encodeURIComponent(selected.original.id)}`;
      const original=await apiGet<unknown>(base);if(!current(seq))return;
      if(!await validMoveEnvelope(original,institute) || (original as MoveEnvelope).original.id!==selected.original.id || (original as MoveEnvelope).fingerprint!==selected.fingerprint)throw Error("Changed selected original");
      const state=await apiGet<unknown>(`${base}/approval-state`);if(!current(seq))return;
      if(!await validMoveApprovalState(state,institute,selected))throw Error("Invalid approval history");
      const receipt=await apiGet<unknown>(`${base}/execution`);if(!current(seq))return;
      if(receipt!==null && !await validMoveExecution(receipt,institute,state as MoveApprovalState))throw Error("Invalid move receipt");
      if(current(seq)){setHistory(state as MoveApprovalState);setExecution(receipt===null ? undefined : receipt as MoveExecutionEnvelope);}
  }
  async function decide(decision?:"approve"|"decline"|"revoke",correction=false){
    if(flight.current || saved.status!=="empty" || executionSaved.status!=="empty" || !allowed || !scopeCurrent())return;
    if(decisionSaved.status==="empty"){
      if(!operation || !history || execution || !decision || !(history.status==="pending" && ["approve","decline"].includes(decision) || history.status==="approved" && decision==="revoke") || decision==="approve" && (history.expired || Date.parse(operation.original.valid_until)<=Date.now())){setError("Relisez la préparation et ses décisions avant de choisir une transition permise.");return;}
      if(decisionReason.trim()!==decisionReason || Array.from(decisionReason).length<3 || Array.from(decisionReason).length>240 || /[\x00-\x1f]/.test(decisionReason)){setError("Saisissez un motif exact de décision de 3 à 240 caractères.");return;}
    }
    flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);
    try{
      let result;
      if(correction)result=await decisionDriver.correct();
      else if(decisionSaved.status!=="empty")result=await decisionDriver.submit();
      else{
        if(!await validMoveApprovalState(history,institute,operation))throw Error("Invalid selected state");
        const last=history!.decisions[history!.decisions.length-1];
        const terms={operation_id:operation!.original.id,operation_fingerprint:operation!.fingerprint,previous_id:last?.original.id??null,previous_fingerprint:last?.fingerprint??null,decision:decision!,reason:decisionReason,idempotency_key:crypto.randomUUID()};
        if(!validBaseDecisionRequest(terms))throw Error("Invalid decision");result=await decisionDriver.submit(terms);
      }
      if(!current(seq))return;clearLifecycle();
      if(result.status==="confirmed"){
        const id=result.receipt.original.operation_id;setIdentifier(id);setPreview(undefined);setDecisionReason("");
        const original=await apiGet<unknown>(`/base/institutes/${encodeURIComponent(institute)}/sensitive-operations/${encodeURIComponent(id)}`);if(!current(seq))return;
        if(!await validMoveEnvelope(original,institute) || (original as MoveEnvelope).original.id!==id)throw Error("Invalid original");
        setOperation(original as MoveEnvelope);await loadLifecycle(original as MoveEnvelope,seq);
      }else if(result.status==="correctable"){setOperation(undefined);setDecisionReason("");setError("Rejet vérifié. Relisez la préparation et les décisions avant une nouvelle décision.");}
      else if(result.status==="busy")setError("Une reprise de décision est déjà en cours.");
    }catch{if(current(seq)){clearLifecycle();setError("Décision à vérifier. Reprenez la demande conservée ou relisez l’historique avant une nouvelle action.");}}
    finally{flight.current=false;if(current(seq)){setDecisionSaved(decisionDriver.state());setBusy(false);}}
  }
  async function readExecutionCapabilities(){
    if(flight.current || pending || !allowed)return;flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);setExecutionAllowed(false);
    try{const v=await apiGet<unknown>("/copilot/execution-capabilities");if(!current(seq))return;if(!validMoveExecutionDiscovery(v))throw Error("Invalid execution registration");setExecutionAllowed(true);}
    catch{if(current(seq))setError("Exécutions autorisées indisponibles ou à vérifier. Relancez la lecture.");}finally{flight.current=false;if(current(seq))setBusy(false);}
  }
  async function execute(correction=false){
    if(flight.current || saved.status!=="empty" || decisionSaved.status!=="empty" || !allowed || !scopeCurrent())return;
    if(executionSaved.status==="empty"){
      if(!executionAllowed || !operation || !history || execution || history.status!=="approved" || history.expired || Date.parse(operation.original.valid_until)<=Date.now()){setError("Relisez les exécutions autorisées et une préparation approuvée encore valide.");return;}
      if(executionReason.trim()!==executionReason || Array.from(executionReason).length<3 || Array.from(executionReason).length>240 || /[\x00-\x1f]/.test(executionReason)){setError("Saisissez un motif exact d’exécution de 3 à 240 caractères.");return;}
    }
    flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);
    try{
      let result;
      if(correction)result=await executionDriver.correct();
      else if(executionSaved.status!=="empty")result=await executionDriver.submit();
      else{
        if(!await validMoveApprovalState(history,institute,operation))throw Error("Invalid approved source");
        const last=history!.decisions[history!.decisions.length-1];
        const terms={operation_id:operation!.original.id,operation_fingerprint:operation!.fingerprint,approval_id:last.original.id,approval_fingerprint:last.fingerprint,reason:executionReason,idempotency_key:crypto.randomUUID()};
        if(!validBaseExecutionRequest(terms))throw Error("Invalid execution");result=await executionDriver.submit(terms);
      }
      if(!current(seq))return;clearLifecycle();
      if(result.status==="confirmed"){
        const id=result.receipt.original.operation_id;setIdentifier(id);setPreview(undefined);setExecutionReason("");
        const original=await apiGet<unknown>(`/base/institutes/${encodeURIComponent(institute)}/sensitive-operations/${encodeURIComponent(id)}`);if(!current(seq))return;
        if(!await validMoveEnvelope(original,institute) || (original as MoveEnvelope).original.id!==id)throw Error("Invalid original");setOperation(original as MoveEnvelope);await loadLifecycle(original as MoveEnvelope,seq);
      }else if(result.status==="correctable"){setOperation(undefined);setExecutionReason("");setError("Rejet vérifié. Relisez la préparation, ses décisions et le reçu avant une nouvelle exécution.");}
      else if(result.status==="busy")setError("Une reprise d’exécution est déjà en cours.");
    }catch{if(current(seq)){clearLifecycle();setError("Exécution à vérifier. Reprenez la demande conservée ou relisez le reçu avant une nouvelle action.");}}
    finally{flight.current=false;if(current(seq)){setExecutionSaved(executionDriver.state());setBusy(false);}}
  }
  function date(v:string){return new Intl.DateTimeFormat("fr-CH",{timeZone:timezone,dateStyle:"medium",timeStyle:"short"}).format(new Date(v));}
  return <section className="copilot-panel" aria-label="Copilot"><h2>Déplacer un rendez-vous avec le Copilot</h2><p>Vérifiez les termes avant de conserver une préparation. Cette vérification ne réserve aucune ressource et ne déplace aucun rendez-vous.</p>
    {saved.status==="invalid" && <p role="alert">Demande locale illisible. Nouvelle préparation bloquée ; vérifiez la preuve conservée.</p>}
    {decisionSaved.status==="invalid" && <p role="alert">Demande de décision illisible. Nouvelles actions bloquées ; vérifiez la preuve conservée.</p>}
    {executionSaved.status==="invalid" && <p role="alert">Demande d’exécution illisible. Nouvelles actions bloquées ; vérifiez la preuve conservée.</p>}
    {executionSaved.status==="frozen" && <article aria-label="Demande d’exécution conservée"><h3>Exécution à reprendre</h3><p>Préparation {executionSaved.value.terms.operation_id} · {executionSaved.value.terms.reason}.</p><button type="button" disabled={busy || !allowed} onClick={()=>void execute()}>Reprendre l’exécution</button>{executionDriver.canCorrect() && <button type="button" disabled={busy || !allowed} onClick={()=>void execute(true)}>Vérifier le rejet d’exécution et corriger</button>}</article>}
    {decisionSaved.status==="frozen" && <article aria-label="Demande de décision conservée"><h3>Décision à reprendre</h3><p>{{approve:"Approbation",decline:"Refus",revoke:"Révocation"}[decisionSaved.value.terms.decision]} · préparation {decisionSaved.value.terms.operation_id} · {decisionSaved.value.terms.reason}.</p><button type="button" disabled={busy || !allowed} onClick={()=>void decide()}>Reprendre la décision</button>{decisionDriver.canCorrect() && <button type="button" disabled={busy || !allowed} onClick={()=>void decide(undefined,true)}>Vérifier le rejet de décision et corriger</button>}</article>}
    {saved.status==="frozen" && <article aria-label="Demande de préparation conservée"><h3>Demande à reprendre</h3><p>{saved.value.terms.operation.selection.appointment_id} · {date(saved.value.terms.operation.selection.start_time)} · {saved.value.terms.operation.reason}.</p><button type="button" disabled={busy || !allowed} onClick={()=>void prepare()}>Reprendre la préparation</button>{driver.canCorrect() && <button type="button" disabled={busy || !allowed} onClick={()=>void prepare(true)}>Vérifier le rejet et corriger</button>}</article>}
    <form onSubmit={e=>{e.preventDefault();void review();}}><fieldset disabled={busy || pending || !allowed}>
      <label>Référence du rendez-vous<input maxLength={80} value={appointment} onChange={e=>{edit();setAppointment(e.target.value);}}/></label>
      <label>Votre demande de déplacement<textarea maxLength={2000} value={message} onChange={e=>{edit();setMessage(e.target.value);}} placeholder="Preparer le deplacement du rendez-vous"/></label>
      <label>Collaboratrice cible (facultatif)<select value={employee} onChange={e=>{edit();setEmployee(e.target.value);}}><option value="">Conserver la collaboratrice d’origine</option>{employees.filter(e=>e.institute_id===institute).map(e=><option key={e.id} value={e.id}>{e.first_name}</option>)}</select></label>
      <label>Prestation cible (facultatif)<select value={service} onChange={e=>{edit();setService(e.target.value);}}><option value="">Conserver la prestation d’origine</option>{services.filter(s=>s.status==="active").map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>Début local du rendez-vous<input type="datetime-local" value={local} onChange={e=>{edit();setLocal(e.target.value);setOccurrence("");}}/></label><p>Heure locale de l’institut : {timezone}.</p>
      {times.length>1 && <label>Occurrence de l’heure répétée<select value={occurrence} onChange={e=>{edit();setOccurrence(e.target.value);}}><option value="">Choisir une occurrence</option>{times.map((t,i)=><option key={t} value={t}>{i===0 ? "Première occurrence" : "Seconde occurrence"}</option>)}</select></label>}
      <button disabled={!message.trim()}>Vérifier les termes de déplacement</button>
    </fieldset></form>{busy && <p role="status">Vérification en cours…</p>}{error && <p role="alert">{error}</p>}
    {preview && <article aria-label="Termes de déplacement vérifiés"><h3>Déplacement vérifié</h3><p>Rendez-vous : {preview.selection.appointment_id}.</p><p>Créneau d’origine : {date(preview.appointment.start_time)} — {date(preview.appointment.end_time)}.</p><p>Créneau proposé : {date(preview.proposed.start_time)} — {date(preview.proposed.end_time)} ({timezone}).</p><p>Collaboratrice cible : {employees.find(e=>e.id===preview.proposed.employee_id)?.first_name||preview.proposed.employee_id}. Prestation cible : {services.find(s=>s.id===preview.proposed.service_id)?.name||preview.proposed.service_id}.</p><p>Cliente et statut conservés. {preview.booking_events} événement(s) d’origine relu(s). {preview.resource_ids.length} ressource(s) vérifiée(s), aucune réservation effectuée. Lecture du {date(preview.captured_at)}.</p><p>Aucune préparation conservée, approbation, déplacement ou communication effectué à cette étape.</p></article>}
    {preview && <fieldset disabled={busy || pending || !allowed}><legend>Conserver les termes vérifiés</legend><label>Motif de préparation<input maxLength={240} value={reason} onChange={e=>setReason(e.target.value)}/></label><label>Échéance locale de préparation<input type="datetime-local" value={deadline} onChange={e=>{setDeadline(e.target.value);setDeadlineOccurrence("");}}/></label><p>Heure locale de l’institut : {timezone}.</p>{deadlines.length>1 && <label>Occurrence de l’échéance répétée<select value={deadlineOccurrence} onChange={e=>setDeadlineOccurrence(e.target.value)}><option value="">Choisir une occurrence</option>{deadlines.map((t,i)=><option key={t} value={t}>{i===0 ? "Première occurrence" : "Seconde occurrence"}</option>)}</select></label>}<button type="button" onClick={()=>void prepare()}>Conserver la préparation</button></fieldset>}
    <fieldset disabled={busy || pending || !allowed}><legend>Relire une préparation</legend><label>Référence de préparation<input maxLength={80} value={identifier} onChange={e=>{sequence.current++;setIdentifier(e.target.value);setOperation(undefined);clearLifecycle();setPreview(undefined);}}/></label><button type="button" disabled={!exactId(identifier)} onClick={()=>void readOperation()}>Relire la préparation</button></fieldset>
    {operation && <article aria-label="Préparation de déplacement relue"><h3>Préparation conservée et relue</h3><p>Référence : {operation.original.id}. Rendez-vous : {operation.original.selection.appointment_id}.</p><p>Créneau d’origine : {date(operation.original.preview.appointment.start_time)} — {date(operation.original.preview.appointment.end_time)}.</p><p>Créneau retenu : {date(operation.original.preview.proposed.start_time)} — {date(operation.original.preview.proposed.end_time)} ({timezone}).</p><p>Collaboratrice : {operation.original.preview.proposed.employee_id}. Prestation : {operation.original.preview.proposed.service_id}. Cliente et statut conservés.</p><p>Motif : {operation.original.reason}. Auteur : {operation.original.actor_id}. Validité : {date(operation.original.valid_until)}.</p><p>Cette préparation ne vaut ni approbation ni déplacement.{!history && " L’état des décisions n’a pas encore été relu."}</p></article>}
    {operation && <button type="button" disabled={busy || pending || !allowed} onClick={()=>void readLifecycle()}>Relire les décisions et l’exécution</button>}
    {history && <article aria-label="Décisions de déplacement relues"><h3>Décisions relues</h3><p>État : {{pending:"en attente",approved:"approuvée",declined:"refusée",revoked:"révoquée"}[history.status]}{history.expired ? " · validité expirée" : ""}. Lecture du {date(history.captured_at)}.</p><ol>{history.decisions.map(d=><li key={d.original.id}>{{approve:"Approbation",decline:"Refus",revoke:"Révocation"}[d.original.decision]} · {d.original.actor_id} · {date(d.original.created_at)} · {d.original.reason}.</li>)}</ol><p>Cette relecture historique ne confirme pas la disponibilité actuelle du créneau. Une décision ne déplace pas de rendez-vous.</p>{!execution && <p>Aucun reçu d’exécution retourné lors de cette lecture.</p>}</article>}
    {operation && history && !execution && (history.status==="pending" || history.status==="approved") && <fieldset disabled={busy || pending || !allowed}><legend>Décider sur les termes conservés</legend><label>Motif de décision<input maxLength={240} value={decisionReason} onChange={e=>setDecisionReason(e.target.value)}/></label>{history.status==="pending" && <><button type="button" disabled={history.expired || Date.parse(operation.original.valid_until)<=Date.now()} onClick={()=>void decide("approve")}>Approuver cette préparation</button><button type="button" onClick={()=>void decide("decline")}>Refuser cette préparation</button></>}{history.status==="approved" && <button type="button" onClick={()=>void decide("revoke")}>Révoquer l’approbation</button>}<p>L’approbation vérifie de nouveau le créneau côté serveur. Elle ne déplace pas de rendez-vous.</p></fieldset>}
    {operation && history?.status==="approved" && !execution && <fieldset disabled={busy || pending || !allowed}><legend>Exécuter le déplacement approuvé</legend><button type="button" onClick={()=>void readExecutionCapabilities()}>Lire les exécutions autorisées</button><label>Motif d’exécution<input maxLength={240} value={executionReason} onChange={e=>setExecutionReason(e.target.value)}/></label><button type="button" disabled={!executionAllowed || history.expired || Date.parse(operation.original.valid_until)<=Date.now()} onClick={()=>void execute()}>Exécuter le déplacement approuvé</button><p>Ce clic déplace le rendez-vous et réserve les ressources vérifiées dans la même transaction. Le serveur relit la préparation et sa dernière approbation.</p></fieldset>}
    {execution && <article aria-label="Preuve de déplacement relue"><h3>Déplacement exécuté et preuve relue</h3><p>Rendez-vous {execution.original.appointment_id}, déplacé le {date(execution.original.created_at)} par {execution.original.actor_id}.</p><p>Intervalle conservé : {date(execution.original.after.start_time)} — {date(execution.original.after.end_time)} ({timezone}).</p><p>Ressources vérifiées et réservées dans la transaction de déplacement ; occupation actuelle non établie. Aucun contact ni paiement effectué par ce déplacement.</p></article>}
  </section>;
}
