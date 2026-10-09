import {useEffect,useRef,useState} from "react";
import {apiGet,apiPost} from "../api/client";
import {getAccessToken,getOperatorInstitute,getOperatorRole,getOperatorSubject} from "../api/session";
import {exactKeys,exactId} from "../copilot-read-utils";
import {certificationInstant} from "../certification-utils";
import {instituteInstants} from "../institute-calendar";
import {creationUTC,validCreationRequest,validCreationEnvelope,validCreationDiscovery,validCreationSelection,validCreationPreview,type CreationSelection,type CreationPreview,type CreationEnvelope} from "../copilot-creation-utils";
import {createCreationPreparationIntent,createCreationDecisionIntent,createCreationExecutionIntent} from "../copilot-creation-intent";
import {validBaseDecisionRequest,validBaseExecutionRequest} from "../base-cancellation-utils";
import {validCreationExecutionDiscovery,validCreationApprovalState,validCreationExecution,type CreationApprovalState,type CreationExecutionEnvelope} from "../copilot-creation-lifecycle";
import type {Employee,Service} from "../types";
type Props={institute:string;timezone:string;employees:Employee[];services:Service[]};
type Customer={id:string;name:string;phone:string|null};
const storage={getItem:(k:string)=>sessionStorage.getItem(k),setItem:(k:string,v:string)=>sessionStorage.setItem(k,v),removeItem:(k:string)=>sessionStorage.removeItem(k)};
export function CopilotCreationPanel(props:Props){
  if(getOperatorRole()!=="responsable_institut" || !getOperatorSubject() || props.institute!==getOperatorInstitute())return null;
  return <Panel key={JSON.stringify([props.institute,props.timezone,getAccessToken()])} {...props}/>;
}
function Panel({institute,timezone,employees,services}:Props){
  const token=getAccessToken(),actor=getOperatorSubject()!,mounted=useRef(false),sequence=useRef(0),flight=useRef(false);
  const [allowed,setAllowed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<string>();
  const [message,setMessage]=useState(""),[employee,setEmployee]=useState(""),[service,setService]=useState(""),[local,setLocal]=useState(""),[occurrence,setOccurrence]=useState("");
  const [query,setQuery]=useState(""),[customers,setCustomers]=useState<Customer[]>([]),[customer,setCustomer]=useState(""),[name,setName]=useState(""),[phone,setPhone]=useState(""),[notes,setNotes]=useState("");
  const [preview,setPreview]=useState<CreationPreview>();
  const [deadline,setDeadline]=useState(""),[deadlineOccurrence,setDeadlineOccurrence]=useState(""),[reason,setReason]=useState(""),[identifier,setIdentifier]=useState("");
  const [operation,setOperation]=useState<CreationEnvelope>();
  const [history,setHistory]=useState<CreationApprovalState>(),[execution,setExecution]=useState<CreationExecutionEnvelope>();
  function clearLifecycle(){setHistory(undefined);setExecution(undefined);}
  const scopeCurrent=()=>mounted.current && token===getAccessToken() && actor===getOperatorSubject() && institute===getOperatorInstitute() && getOperatorRole()==="responsable_institut";
  const [driver]=useState(()=>createCreationPreparationIntent({institute,actor,storage,current:scopeCurrent,get:path=>apiGet(path),post:(path,body)=>apiPost(path,body)}));
  const [saved,setSaved]=useState(()=>driver.state());
  const [decisionDriver]=useState(()=>createCreationDecisionIntent({institute,actor,storage,current:scopeCurrent,get:path=>apiGet(path),post:(path,body)=>apiPost(path,body)}));
  const [decisionSaved,setDecisionSaved]=useState(()=>decisionDriver.state()),[decisionReason,setDecisionReason]=useState("");
  const [executionDriver]=useState(()=>createCreationExecutionIntent({institute,actor,storage,current:scopeCurrent,get:path=>apiGet(path),post:(path,body)=>apiPost(path,body)}));
  const [executionSaved,setExecutionSaved]=useState(()=>executionDriver.state()),[executionReason,setExecutionReason]=useState(""),[executionAllowed,setExecutionAllowed]=useState(false);
  const pending=saved.status!=="empty" || decisionSaved.status!=="empty" || executionSaved.status!=="empty";
  const deadlines=deadline ? instituteInstants(deadline.slice(0,10),deadline.slice(11,16),timezone) : [];
  const times=local ? instituteInstants(local.slice(0,10),local.slice(11,16),timezone) : [];
  const current=(seq:number)=>mounted.current && sequence.current===seq && token===getAccessToken() && actor===getOperatorSubject() && institute===getOperatorInstitute() && getOperatorRole()==="responsable_institut";
  function edit(){sequence.current++;setPreview(undefined);setOperation(undefined);clearLifecycle();setIdentifier("");setError(undefined);}
  useEffect(()=>{mounted.current=true;const seq=++sequence.current;setBusy(true);void apiGet<unknown>("/copilot/preparation-capabilities").then(v=>{if(!current(seq))return;if(!validCreationDiscovery(v))throw Error("Invalid registration");setAllowed(true);}).catch(()=>{if(current(seq))setError("Préparations autorisées indisponibles. Rouvrez ce parcours pour les relire.");}).finally(()=>{if(current(seq))setBusy(false);});return()=>{mounted.current=false;sequence.current++;};},[]);
  async function search(){
    if(flight.current || pending || !allowed || query.trim().length<2)return;flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);setPreview(undefined);setCustomers([]);setCustomer("");setName("");setPhone("");
    try{
      const v=await apiGet<unknown>(`/customers/institutes/${encodeURIComponent(institute)}?q=${encodeURIComponent(query.trim())}&limit=20`);if(!current(seq))return;
      if(!Array.isArray(v) || v.length>20 || new Set(v.map(r=>r?.id)).size!==v.length || !v.every(r=>exactKeys(r,"id institute_id display_name phone created_at") && exactId(r.id) && r.institute_id===institute && typeof r.display_name==="string" && !!r.display_name.trim() && r.display_name.length<=160 && (r.phone===null || typeof r.phone==="string") && certificationInstant(r.created_at)!==undefined))throw Error("Invalid customers");
      setCustomers(v.map(r=>({id:r.id,name:r.display_name,phone:r.phone})));
    }catch{if(current(seq))setError("Recherche cliente indisponible ou à vérifier.");}finally{flight.current=false;if(current(seq))setBusy(false);}
  }
  async function review(){
    if(flight.current || pending || !allowed || !message.trim())return;
    const start=times.length===1 ? times[0] : times.includes(occurrence) ? occurrence : undefined;
    if(!start){setError("Choisissez une heure locale valide et son occurrence si elle se répète.");return;}
    const selection:CreationSelection={employee_id:employee,service_id:service,customer_id:customer||null,customer_name:name,phone:phone||null,notes:notes||null,start_time:start};
    if(!validCreationSelection(selection) || !employees.some(e=>e.id===employee && e.institute_id===institute) || !services.some(s=>s.id===service && s.status==="active") || customer && !customers.some(c=>c.id===customer)){setError("Choisissez les références proposées et relisez le nom, les coordonnées et les notes sans espaces de bord.");return;}
    flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);setPreview(undefined);
    try{const v=await apiPost<unknown>("/copilot/prepare-preview",{message:message.trim(),ui_context:selection});if(!current(seq))return;if(!await validCreationPreview(v,institute,selection,actor))throw Error("Invalid preview");if(current(seq))setPreview(v as CreationPreview);}
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
        const terms={capability:"APPOINTMENT_CREATE" as const,selection:preview!.selection,expected_state_fingerprint:preview!.state_fingerprint,valid_until:creationUTC(selected)!,reason,idempotency_key:crypto.randomUUID()};
        if(!validCreationRequest(terms))throw Error("Invalid preparation reason");
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
    try{const v=await apiGet<unknown>(`/base/institutes/${encodeURIComponent(institute)}/sensitive-operations/${encodeURIComponent(identifier)}`);if(!current(seq))return;if(!await validCreationEnvelope(v,institute) || (v as CreationEnvelope).original.id!==identifier)throw Error("Invalid original");if(current(seq))setOperation(v as CreationEnvelope);}
    catch{if(current(seq))setError("Préparation indisponible ou à vérifier. Relisez sa référence.");}finally{flight.current=false;if(current(seq))setBusy(false);}
  }
  async function readLifecycle(){
    if(flight.current || pending || !allowed || !operation)return;
    flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);clearLifecycle();
    try{await loadLifecycle(operation,seq);}
    catch{if(current(seq))setError("Décisions ou preuve d’exécution indisponibles ou à vérifier. Relisez la préparation puis son historique.");}
    finally{flight.current=false;if(current(seq))setBusy(false);}
  }
  async function loadLifecycle(selected:CreationEnvelope,seq:number){
    const base=`/base/institutes/${encodeURIComponent(institute)}/sensitive-operations/${encodeURIComponent(selected.original.id)}`;
      const original=await apiGet<unknown>(base);if(!current(seq))return;
      if(!await validCreationEnvelope(original,institute) || (original as CreationEnvelope).original.id!==selected.original.id || (original as CreationEnvelope).fingerprint!==selected.fingerprint)throw Error("Changed selected original");
      const state=await apiGet<unknown>(`${base}/approval-state`);if(!current(seq))return;
      if(!await validCreationApprovalState(state,institute,selected))throw Error("Invalid approval history");
      const receipt=await apiGet<unknown>(`${base}/execution`);if(!current(seq))return;
      if(receipt!==null && !await validCreationExecution(receipt,institute,state as CreationApprovalState))throw Error("Invalid creation receipt");
      if(current(seq)){setHistory(state as CreationApprovalState);setExecution(receipt===null ? undefined : receipt as CreationExecutionEnvelope);}
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
        if(!await validCreationApprovalState(history,institute,operation))throw Error("Invalid selected state");
        const last=history!.decisions[history!.decisions.length-1];
        const terms={operation_id:operation!.original.id,operation_fingerprint:operation!.fingerprint,previous_id:last?.original.id??null,previous_fingerprint:last?.fingerprint??null,decision:decision!,reason:decisionReason,idempotency_key:crypto.randomUUID()};
        if(!validBaseDecisionRequest(terms))throw Error("Invalid decision");result=await decisionDriver.submit(terms);
      }
      if(!current(seq))return;clearLifecycle();
      if(result.status==="confirmed"){
        const id=result.receipt.original.operation_id;setIdentifier(id);setPreview(undefined);setDecisionReason("");
        const original=await apiGet<unknown>(`/base/institutes/${encodeURIComponent(institute)}/sensitive-operations/${encodeURIComponent(id)}`);if(!current(seq))return;
        if(!await validCreationEnvelope(original,institute) || (original as CreationEnvelope).original.id!==id)throw Error("Invalid original");
        setOperation(original as CreationEnvelope);await loadLifecycle(original as CreationEnvelope,seq);
      }else if(result.status==="correctable"){setOperation(undefined);setDecisionReason("");setError("Rejet vérifié. Relisez la préparation et les décisions avant une nouvelle décision.");}
      else if(result.status==="busy")setError("Une reprise de décision est déjà en cours.");
    }catch{if(current(seq)){clearLifecycle();setError("Décision à vérifier. Reprenez la demande conservée ou relisez l’historique avant une nouvelle action.");}}
    finally{flight.current=false;if(current(seq)){setDecisionSaved(decisionDriver.state());setBusy(false);}}
  }
  async function readExecutionCapabilities(){
    if(flight.current || pending || !allowed)return;flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);setExecutionAllowed(false);
    try{const v=await apiGet<unknown>("/copilot/execution-capabilities");if(!current(seq))return;if(!validCreationExecutionDiscovery(v))throw Error("Invalid execution registration");setExecutionAllowed(true);}
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
        if(!await validCreationApprovalState(history,institute,operation))throw Error("Invalid approved source");
        const last=history!.decisions[history!.decisions.length-1];
        const terms={operation_id:operation!.original.id,operation_fingerprint:operation!.fingerprint,approval_id:last.original.id,approval_fingerprint:last.fingerprint,reason:executionReason,idempotency_key:crypto.randomUUID()};
        if(!validBaseExecutionRequest(terms))throw Error("Invalid execution");result=await executionDriver.submit(terms);
      }
      if(!current(seq))return;clearLifecycle();
      if(result.status==="confirmed"){
        const id=result.receipt.original.operation_id;setIdentifier(id);setPreview(undefined);setExecutionReason("");
        const original=await apiGet<unknown>(`/base/institutes/${encodeURIComponent(institute)}/sensitive-operations/${encodeURIComponent(id)}`);if(!current(seq))return;
        if(!await validCreationEnvelope(original,institute) || (original as CreationEnvelope).original.id!==id)throw Error("Invalid original");setOperation(original as CreationEnvelope);await loadLifecycle(original as CreationEnvelope,seq);
      }else if(result.status==="correctable"){setOperation(undefined);setExecutionReason("");setError("Rejet vérifié. Relisez la préparation, ses décisions et le reçu avant une nouvelle exécution.");}
      else if(result.status==="busy")setError("Une reprise d’exécution est déjà en cours.");
    }catch{if(current(seq)){clearLifecycle();setError("Exécution à vérifier. Reprenez la demande conservée ou relisez le reçu avant une nouvelle action.");}}
    finally{flight.current=false;if(current(seq)){setExecutionSaved(executionDriver.state());setBusy(false);}}
  }
  function date(v:string){return new Intl.DateTimeFormat("fr-CH",{timeZone:timezone,dateStyle:"medium",timeStyle:"short"}).format(new Date(v));}
  return <section className="copilot-panel" aria-label="Copilot"><h2>Créer un rendez-vous avec le Copilot</h2><p>Vérifiez les termes avant de conserver une préparation. Cette vérification ne réserve aucune ressource et ne crée aucun rendez-vous.</p>
    {saved.status==="invalid" && <p role="alert">Demande locale illisible. Nouvelle préparation bloquée ; vérifiez la preuve conservée.</p>}
    {decisionSaved.status==="invalid" && <p role="alert">Demande de décision illisible. Nouvelles actions bloquées ; vérifiez la preuve conservée.</p>}
    {executionSaved.status==="invalid" && <p role="alert">Demande d’exécution illisible. Nouvelles actions bloquées ; vérifiez la preuve conservée.</p>}
    {executionSaved.status==="frozen" && <article aria-label="Demande d’exécution conservée"><h3>Exécution à reprendre</h3><p>Préparation {executionSaved.value.terms.operation_id} · {executionSaved.value.terms.reason}.</p><button type="button" disabled={busy || !allowed} onClick={()=>void execute()}>Reprendre l’exécution</button>{executionDriver.canCorrect() && <button type="button" disabled={busy || !allowed} onClick={()=>void execute(true)}>Vérifier le rejet d’exécution et corriger</button>}</article>}
    {decisionSaved.status==="frozen" && <article aria-label="Demande de décision conservée"><h3>Décision à reprendre</h3><p>{{approve:"Approbation",decline:"Refus",revoke:"Révocation"}[decisionSaved.value.terms.decision]} · préparation {decisionSaved.value.terms.operation_id} · {decisionSaved.value.terms.reason}.</p><button type="button" disabled={busy || !allowed} onClick={()=>void decide()}>Reprendre la décision</button>{decisionDriver.canCorrect() && <button type="button" disabled={busy || !allowed} onClick={()=>void decide(undefined,true)}>Vérifier le rejet de décision et corriger</button>}</article>}
    {saved.status==="frozen" && <article aria-label="Demande de préparation conservée"><h3>Demande à reprendre</h3><p>{saved.value.terms.operation.selection.customer_name} · {date(saved.value.terms.operation.selection.start_time)} · {saved.value.terms.operation.reason}.</p><button type="button" disabled={busy || !allowed} onClick={()=>void prepare()}>Reprendre la préparation</button>{driver.canCorrect() && <button type="button" disabled={busy || !allowed} onClick={()=>void prepare(true)}>Vérifier le rejet et corriger</button>}</article>}
    <form onSubmit={e=>{e.preventDefault();void review();}}><fieldset disabled={busy || pending || !allowed}>
      <label>Votre demande de création<textarea maxLength={2000} value={message} onChange={e=>{edit();setMessage(e.target.value);}} placeholder="Preparer la creation du rendez-vous"/></label>
      <label>Collaboratrice sélectionnée<select value={employee} onChange={e=>{edit();setEmployee(e.target.value);}}><option value="">Choisir une collaboratrice</option>{employees.filter(e=>e.institute_id===institute).map(e=><option key={e.id} value={e.id}>{e.first_name}</option>)}</select></label>
      <label>Prestation sélectionnée<select value={service} onChange={e=>{edit();setService(e.target.value);}}><option value="">Choisir une prestation</option>{services.filter(s=>s.status==="active").map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>Début local du rendez-vous<input type="datetime-local" value={local} onChange={e=>{edit();setLocal(e.target.value);setOccurrence("");}}/></label><p>Heure locale de l’institut : {timezone}.</p>
      {times.length>1 && <label>Occurrence de l’heure répétée<select value={occurrence} onChange={e=>{edit();setOccurrence(e.target.value);}}><option value="">Choisir une occurrence</option>{times.map((t,i)=><option key={t} value={t}>{i===0 ? "Première occurrence" : "Seconde occurrence"}</option>)}</select></label>}
      <label>Rechercher une cliente<input maxLength={160} value={query} onChange={e=>{edit();setQuery(e.target.value);setCustomers([]);setCustomer("");setName("");setPhone("");}}/></label><button type="button" disabled={query.trim().length<2} onClick={()=>void search()}>Rechercher les clientes</button>
      <label>Cliente enregistrée (facultatif)<select value={customer} onChange={e=>{edit();const c=customers.find(c=>c.id===e.target.value);setCustomer(c?.id||"");setName(c?.name||"");setPhone(c?.phone||"");}}><option value="">Sans lien à une fiche</option>{customers.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label><p>Jusqu’à 20 résultats ; affinez la recherche si nécessaire.</p>
      <label>Nom revu pour le rendez-vous<input maxLength={160} value={name} onChange={e=>{edit();setName(e.target.value);}}/></label><label>Téléphone revu (facultatif)<input type="tel" maxLength={40} value={phone} onChange={e=>{edit();setPhone(e.target.value);}}/></label><label>Notes revues (facultatif)<textarea maxLength={500} value={notes} onChange={e=>{edit();setNotes(e.target.value);}}/></label>
      <button disabled={!message.trim()}>Vérifier les termes de création</button>
    </fieldset></form>{busy && <p role="status">Vérification en cours…</p>}{error && <p role="alert">{error}</p>}
    {preview && <article aria-label="Termes de création vérifiés"><h3>Termes vérifiés</h3><p>{preview.selection.customer_name} · {services.find(s=>s.id===preview.selection.service_id)?.name} · {employees.find(e=>e.id===preview.selection.employee_id)?.first_name}.</p><p>{date(preview.selection.start_time)} — {date(preview.end_time)} ({timezone}).</p><p>{preview.resource_ids.length} ressource(s) vérifiée(s), aucune réservation effectuée. Lecture du {date(preview.captured_at)}.</p><p>Aucune préparation conservée, approbation, création ou communication effectuée à cette étape.</p></article>}
    {preview && <fieldset disabled={busy || pending || !allowed}><legend>Conserver les termes vérifiés</legend><label>Motif de préparation<input maxLength={240} value={reason} onChange={e=>setReason(e.target.value)}/></label><label>Échéance locale de préparation<input type="datetime-local" value={deadline} onChange={e=>{setDeadline(e.target.value);setDeadlineOccurrence("");}}/></label><p>Heure locale de l’institut : {timezone}.</p>{deadlines.length>1 && <label>Occurrence de l’échéance répétée<select value={deadlineOccurrence} onChange={e=>setDeadlineOccurrence(e.target.value)}><option value="">Choisir une occurrence</option>{deadlines.map((t,i)=><option key={t} value={t}>{i===0 ? "Première occurrence" : "Seconde occurrence"}</option>)}</select></label>}<button type="button" onClick={()=>void prepare()}>Conserver la préparation</button></fieldset>}
    <fieldset disabled={busy || pending || !allowed}><legend>Relire une préparation</legend><label>Référence de préparation<input maxLength={80} value={identifier} onChange={e=>{sequence.current++;setIdentifier(e.target.value);setOperation(undefined);clearLifecycle();setPreview(undefined);}}/></label><button type="button" disabled={!exactId(identifier)} onClick={()=>void readOperation()}>Relire la préparation</button></fieldset>
    {operation && <article aria-label="Préparation de création relue"><h3>Préparation conservée et relue</h3><p>Référence : {operation.original.id}.</p><p>{operation.original.selection.customer_name} · {date(operation.original.selection.start_time)} — {date(operation.original.preview.end_time)} ({timezone}).</p><p>Prestation : {services.find(s=>s.id===operation.original.selection.service_id)?.name||"Prestation enregistrée"}. Collaboratrice : {employees.find(e=>e.id===operation.original.selection.employee_id)?.first_name||"Collaboratrice enregistrée"}.</p><p>{operation.original.selection.customer_id ? "Fiche cliente reliée" : "Sans lien à une fiche cliente"}. Téléphone conservé : {operation.original.selection.phone||"non renseigné"}. Notes conservées : {operation.original.selection.notes||"non renseignées"}.</p><p>Motif : {operation.original.reason}. Auteur : {operation.original.actor_id}. Validité : {date(operation.original.valid_until)}.</p><p>Cette préparation ne vaut ni approbation ni création de rendez-vous.{!history && " L’état des décisions n’a pas encore été relu."}</p></article>}
    {operation && <button type="button" disabled={busy || pending || !allowed} onClick={()=>void readLifecycle()}>Relire les décisions et l’exécution</button>}
    {history && <article aria-label="Décisions de création relues"><h3>Décisions relues</h3><p>État : {{pending:"en attente",approved:"approuvée",declined:"refusée",revoked:"révoquée"}[history.status]}{history.expired ? " · validité expirée" : ""}. Lecture du {date(history.captured_at)}.</p><ol>{history.decisions.map(d=><li key={d.original.id}>{{approve:"Approbation",decline:"Refus",revoke:"Révocation"}[d.original.decision]} · {d.original.actor_id} · {date(d.original.created_at)} · {d.original.reason}.</li>)}</ol><p>Cette relecture historique ne confirme pas la disponibilité actuelle du créneau. Une décision ne crée pas de rendez-vous.</p>{!execution && <p>Aucun reçu d’exécution retourné lors de cette lecture.</p>}</article>}
    {operation && history && !execution && (history.status==="pending" || history.status==="approved") && <fieldset disabled={busy || pending || !allowed}><legend>Décider sur les termes conservés</legend><label>Motif de décision<input maxLength={240} value={decisionReason} onChange={e=>setDecisionReason(e.target.value)}/></label>{history.status==="pending" && <><button type="button" disabled={history.expired || Date.parse(operation.original.valid_until)<=Date.now()} onClick={()=>void decide("approve")}>Approuver cette préparation</button><button type="button" onClick={()=>void decide("decline")}>Refuser cette préparation</button></>}{history.status==="approved" && <button type="button" onClick={()=>void decide("revoke")}>Révoquer l’approbation</button>}<p>L’approbation vérifie de nouveau le créneau côté serveur. Elle ne crée pas de rendez-vous.</p></fieldset>}
    {operation && history?.status==="approved" && !execution && <fieldset disabled={busy || pending || !allowed}><legend>Exécuter la création approuvée</legend><button type="button" onClick={()=>void readExecutionCapabilities()}>Lire les exécutions autorisées</button><label>Motif d’exécution<input maxLength={240} value={executionReason} onChange={e=>setExecutionReason(e.target.value)}/></label><button type="button" disabled={!executionAllowed || history.expired || Date.parse(operation.original.valid_until)<=Date.now()} onClick={()=>void execute()}>Exécuter la création approuvée</button><p>Ce clic crée le rendez-vous et réserve les ressources vérifiées dans la même transaction. Le serveur relit la préparation et sa dernière approbation.</p></fieldset>}
    {execution && <article aria-label="Preuve de création relue"><h3>Création exécutée et preuve relue</h3><p>Rendez-vous {execution.original.appointment_id}, créé le {date(execution.original.created_at)} par {execution.original.actor_id}.</p><p>Intervalle conservé : {date(execution.original.after.start_time)} — {date(execution.original.after.end_time)} ({timezone}).</p><p>Ressources vérifiées et réservées dans la transaction de création ; occupation actuelle non établie. Aucun contact ni paiement effectué par cette création.</p></article>}
  </section>;
}
