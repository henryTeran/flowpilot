import {useEffect,useRef,useState} from "react";
import {apiGet,apiPost} from "../api/client";
import {getAccessToken,getOperatorInstitute,getOperatorRole,getOperatorSubject} from "../api/session";
import {exactKeys,exactId} from "../copilot-read-utils";
import {certificationInstant} from "../certification-utils";
import {instituteInstants} from "../institute-calendar";
import {validCreationDiscovery,validCreationSelection,validCreationPreview,type CreationSelection,type CreationPreview} from "../copilot-creation-utils";
import type {Employee,Service} from "../types";
type Props={institute:string;timezone:string;employees:Employee[];services:Service[]};
type Customer={id:string;name:string;phone:string|null};
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
  const times=local ? instituteInstants(local.slice(0,10),local.slice(11,16),timezone) : [];
  const current=(seq:number)=>mounted.current && sequence.current===seq && token===getAccessToken() && actor===getOperatorSubject() && institute===getOperatorInstitute() && getOperatorRole()==="responsable_institut";
  function edit(){sequence.current++;setPreview(undefined);setError(undefined);}
  useEffect(()=>{mounted.current=true;const seq=++sequence.current;setBusy(true);void apiGet<unknown>("/copilot/preparation-capabilities").then(v=>{if(!current(seq))return;if(!validCreationDiscovery(v))throw Error("Invalid registration");setAllowed(true);}).catch(()=>{if(current(seq))setError("Préparations autorisées indisponibles. Rouvrez ce parcours pour les relire.");}).finally(()=>{if(current(seq))setBusy(false);});return()=>{mounted.current=false;sequence.current++;};},[]);
  async function search(){
    if(flight.current || !allowed || query.trim().length<2)return;flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);setPreview(undefined);setCustomers([]);setCustomer("");setName("");setPhone("");
    try{
      const v=await apiGet<unknown>(`/customers/institutes/${encodeURIComponent(institute)}?q=${encodeURIComponent(query.trim())}&limit=20`);if(!current(seq))return;
      if(!Array.isArray(v) || v.length>20 || new Set(v.map(r=>r?.id)).size!==v.length || !v.every(r=>exactKeys(r,"id institute_id display_name phone created_at") && exactId(r.id) && r.institute_id===institute && typeof r.display_name==="string" && !!r.display_name.trim() && r.display_name.length<=160 && (r.phone===null || typeof r.phone==="string") && certificationInstant(r.created_at)!==undefined))throw Error("Invalid customers");
      setCustomers(v.map(r=>({id:r.id,name:r.display_name,phone:r.phone})));
    }catch{if(current(seq))setError("Recherche cliente indisponible ou à vérifier.");}finally{flight.current=false;if(current(seq))setBusy(false);}
  }
  async function review(){
    if(flight.current || !allowed || !message.trim())return;
    const start=times.length===1 ? times[0] : times.includes(occurrence) ? occurrence : undefined;
    if(!start){setError("Choisissez une heure locale valide et son occurrence si elle se répète.");return;}
    const selection:CreationSelection={employee_id:employee,service_id:service,customer_id:customer||null,customer_name:name,phone:phone||null,notes:notes||null,start_time:start};
    if(!validCreationSelection(selection) || !employees.some(e=>e.id===employee && e.institute_id===institute) || !services.some(s=>s.id===service && s.status==="active") || customer && !customers.some(c=>c.id===customer)){setError("Choisissez les références proposées et relisez le nom, les coordonnées et les notes sans espaces de bord.");return;}
    flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);setPreview(undefined);
    try{const v=await apiPost<unknown>("/copilot/prepare-preview",{message:message.trim(),ui_context:selection});if(!current(seq))return;if(!await validCreationPreview(v,institute,selection,actor))throw Error("Invalid preview");if(current(seq))setPreview(v as CreationPreview);}
    catch{if(current(seq))setError("Créneau indisponible ou lecture à vérifier. Relisez les sélections puis relancez la vérification.");}finally{flight.current=false;if(current(seq))setBusy(false);}
  }
  function date(v:string){return new Intl.DateTimeFormat("fr-CH",{timeZone:timezone,dateStyle:"medium",timeStyle:"short"}).format(new Date(v));}
  return <section className="copilot-panel" aria-label="Copilot"><h2>Créer un rendez-vous avec le Copilot</h2><p>Vérifiez les termes avant de conserver une préparation. Cette vérification ne réserve aucune ressource et ne crée aucun rendez-vous.</p>
    <form onSubmit={e=>{e.preventDefault();void review();}}><fieldset disabled={busy || !allowed}>
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
  </section>;
}
