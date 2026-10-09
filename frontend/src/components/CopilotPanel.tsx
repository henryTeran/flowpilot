import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getAccessToken, getOperatorInstitute, getOperatorRole } from "../api/session";
import { exactId, exactKeys, readLabels, validReadDiscovery, validReadResponse, type ReadName, type ReadResponse, type ReadSelection, type CustomerFacts, type PlanningFacts, type Gaps, type Slot } from "../copilot-read-utils";
import { certificationInstant } from "../certification-utils";
import { stockDisplay, stockUnits } from "../inventory-utils";
import type { Outlook } from "../outlook-utils";
import type { SegmentProfile } from "../crm-segment-utils";
import type { RebookingFacts } from "../copilot-read-utils";
import { crmMoney } from "./CustomerCrmPanel";
import type { RevenueCapacity } from "../revenue-capacity-utils";
import { formatWorkDuration } from "../work-hours-utils";
import type { ConflictRead } from "../copilot-conflict-utils";
import { revenueMoney, type RevenueBilling } from "../revenue-utils";
import { instituteMidnight } from "../outlook-utils";
import type { LossRead } from "../copilot-loss-utils";
import type { Employee, Service } from "../types";

type Props = { institute: string; timezone: string; employees: Employee[]; services: Service[] };
type Choice = { id: string; display_name: string };
const statuses: Record<string,string> = { available: "Disponible", busy: "En soin", pause: "En pause", absent: "Absente", paused: "En pause", unavailable: "Indisponible", offline: "Hors service", active: "En cours", completed: "Terminé", cancelled: "Annulé", planned: "Planifié", scheduled: "Planifié", in_progress: "En cours" };
const reasons: Record<string,string> = { available_now: "Disponible maintenant", in_progress_session: "Soin en cours", upcoming_appointment: "Rendez-vous enregistré", employee_pause: "Collaboratrice en pause", employee_absent: "Collaboratrice absente", employee_offline: "Collaboratrice hors service", busy_until: "Disponibilité différée", session_overdue: "Fin du soin en cours non confirmée", capacity_unknown: "Capacité non établie", skills_missing: "Qualification nécessaire manquante", resource_capacity_unknown: "Disponibilité de ressource non établie", resource_reserved: "Ressource réservée", scheduled_absence: "Absence enregistrée" };
export function CopilotPanel(props: Props) {
  if (!props.institute || props.institute !== getOperatorInstitute() || !["accueil","responsable_institut"].includes(getOperatorRole() || "")) return null;
  return <Consultations key={JSON.stringify([props.institute,getAccessToken(),props.timezone])} {...props} />;
}
function Consultations({ institute, timezone, employees, services }: Props) {
  const token = getAccessToken(), role = getOperatorRole() || "";
  const mounted = useRef(false), sequence = useRef(0), flight = useRef(false);
  const [available,setAvailable] = useState<ReadName[]>([]), [name,setName] = useState<ReadName | "">("");
  const [question,setQuestion] = useState(""), [customerQuery,setCustomerQuery] = useState(""), [choices,setChoices] = useState<Choice[]>([]);
  const [customer,setCustomer] = useState(""), [service,setService] = useState("");
  const [day,setDay] = useState("");
  const [periodStart,setPeriodStart]=useState(""),[periodEnd,setPeriodEnd]=useState("");
  const [target,setTarget]=useState(""),[resourceChoices,setResourceChoices]=useState<{id:string;name:string}[]>([]);
  async function loadResources(){
    if(flight.current)return;flight.current=true;const seq=++sequence.current;setBusy(true);setError(undefined);setResponse(undefined);
    try{const rows=await apiGet<unknown>(`/resources/institutes/${encodeURIComponent(institute)}`);
      if(!current(seq))return;
      if(!Array.isArray(rows) || new Set(rows.map(r=>r?.id)).size!==rows.length || !rows.every(r=>exactKeys(r,"id institute_id name kind capabilities status") && exactId(r.id) && r.institute_id===institute && typeof r.name==="string" && !!r.name.trim() && r.name.length<=120 && ["active","inactive","maintenance"].includes(r.status as string) && ["room","equipment","bed","chair","device"].includes(r.kind as string) && Array.isArray(r.capabilities) && r.capabilities.every(c=>typeof c==="string")))throw Error("Invalid resources");
      setResourceChoices(rows.map(r=>({id:r.id,name:r.name})));
    }catch{if(current(seq))setError("Ressources indisponibles. Relancez la lecture.");}finally{flight.current=false;if(current(seq))setBusy(false);}
  }
  const customerMode = name === "CLIENT_READ" || name === "CLIENT_SUMMARY" || name === "CLIENT_REBOOKING_OPPORTUNITIES";
  const [response,setResponse] = useState<ReadResponse>(), [busy,setBusy] = useState(false), [error,setError] = useState<string>();
  const current = (seq: number) => mounted.current && sequence.current === seq && token === getAccessToken() && institute === getOperatorInstitute();
  function edit() { sequence.current++; setResponse(undefined); setError(undefined); }
  useEffect(() => {
    mounted.current = true;
    const seq = ++sequence.current;
    setBusy(true);
    void apiGet<unknown>("/copilot/capabilities").then(value => {
      if (!current(seq)) return;
      if (!validReadDiscovery(value,role)) throw new Error("Invalid discovery");
      setAvailable(value.map(row => row.name).filter((value): value is ReadName => Object.prototype.hasOwnProperty.call(readLabels,value)));
    }).catch(() => { if (current(seq)) setError("Les consultations autorisées sont indisponibles. Rouvrez le Copilot pour les relire."); })
      .finally(() => { if (current(seq)) setBusy(false); });
    return () => { mounted.current = false; sequence.current++; };
  }, []);
  async function search() {
    if (flight.current || !mounted.current || token !== getAccessToken() || customerQuery.trim().length < 2) return;
    flight.current = true; const seq = ++sequence.current;
    setBusy(true); setError(undefined); setResponse(undefined); setChoices([]); setCustomer("");
    try {
      const value = await apiGet<unknown>(`/customers/institutes/${encodeURIComponent(institute)}?q=${encodeURIComponent(customerQuery.trim())}&limit=20`);
      if (!current(seq)) return;
      if (!Array.isArray(value) || value.length > 20 || new Set(value.map(row => row?.id)).size !== value.length || !value.every(row => exactKeys(row,"id institute_id display_name phone created_at")
        && exactId(row.id) && row.institute_id === institute && typeof row.display_name === "string" && !!row.display_name.trim() && row.display_name.length <= 160
        && (row.phone === null || typeof row.phone === "string") && certificationInstant(row.created_at) !== undefined)) throw new Error("Invalid customers");
      setChoices(value.map(row => ({ id:row.id,display_name:row.display_name })));
    } catch { if (current(seq)) setError("Recherche cliente à vérifier. Affinez le nom et relancez la recherche."); }
    finally { flight.current = false; if (current(seq)) setBusy(false); }
  }
  async function consult() {
    if (flight.current || !name || !available.includes(name) || !question.trim() || token !== getAccessToken()) return;
    const selection: ReadSelection = customerMode ? { customer_id:customer } : name === "PLANNING_CONFLICTS" ? {day,...(target.startsWith("resource:") ? {resource_id:target.slice(9)} : {employee_id:target.slice(9)})} : name === "EMPLOYEE_CAPACITY" ? {day} : name === "PLANNING_GAPS" && service ? { service_id:service } : {};
    if(name==="REVENUE_SUMMARY" || name==="REVENUE_LOSS_ANALYSIS"){
      const start=instituteMidnight(periodStart,timezone),end=instituteMidnight(periodEnd,timezone);
      if(!start || !end || certificationInstant(start)!>=certificationInstant(end)!){setError("Choisissez une date de fin postérieure au début de la période.");return;}
      selection.start=start;selection.end=end;
    }
    if(name==="PLANNING_CONFLICTS" && !(selection.resource_id ? resourceChoices.some(r=>r.id===selection.resource_id) : employees.some(r=>r.id===selection.employee_id && r.institute_id===institute)))return;
    if (customerMode && !choices.some(row => row.id === customer) || name === "PLANNING_GAPS" && service && !services.some(row => row.id === service)) {
      setError("Choisissez une référence proposée avant de consulter."); return;
    }
    flight.current = true; const seq = ++sequence.current;
    setBusy(true); setError(undefined); setResponse(undefined);
    try {
      const value = await apiPost<unknown>("/copilot/query",{ message:question.trim(),ui_context:selection });
      if (!current(seq)) return;
      if (!await validReadResponse(value,institute,name,selection,timezone)) throw new Error("Invalid evidence");
      if (current(seq)) setResponse(value as ReadResponse);
    } catch { if (current(seq)) setError("Réponse indisponible ou à vérifier. Relisez les sélections puis relancez la consultation."); }
    finally { flight.current = false; if (current(seq)) setBusy(false); }
  }
  function date(value: string) { try { return new Intl.DateTimeFormat("fr-CH",{ timeZone:timezone,dateStyle:"medium",timeStyle:"short" }).format(new Date(value)); } catch { return "Date à vérifier"; } }
  function employee(id: string) { return employees.find(row => row.id === id && row.institute_id === institute)?.first_name || "Collaboratrice enregistrée"; }
  function serviceName(id: string) { return services.find(row => row.id === id)?.name || "Prestation enregistrée"; }
  function slot(value: Slot) {
    return <><p>{reasons[value.reason] || "Motif de disponibilité à vérifier"}.</p>{value.available_from && <p>À partir du {date(value.available_from)}{value.available_until ? `, jusqu’au ${date(value.available_until)}` : ", fin de disponibilité non établie"}.</p>}
      {!value.available_from && <p>Début de disponibilité non établi.</p>}
      {(value.blocking_session_id || value.blocking_appointment_id || value.blocking_resource_id || value.blocking_absence_id) && <p>Contraintes enregistrées : {[value.blocking_session_id && "soin",value.blocking_appointment_id && "rendez-vous",value.blocking_resource_id && "ressource",value.blocking_absence_id && "absence"].filter(Boolean).join(", ")}.</p>}</>;
  }
  function facts() {
    const evidence = response?.evidence;
    if (!evidence) return null;
    if(evidence.capability==="REVENUE_LOSS_ANALYSIS"){
      const value=evidence.result as LossRead;
      return <><p>Événements enregistrés sur la période sélectionnée. Historique complet et perte financière causale non établis.</p>
        <h4>Rendez-vous</h4><p>Sources lues le {date(value.bookings.window.captured_at)}.</p>
        <p>{value.bookings.cancelled_count} annulation(s), {value.bookings.no_show_count} absence(s) au rendez-vous, {value.bookings.unpriced_count} événement(s) sans prix retenu.</p>
        <p>{value.bookings.institute_terminal_bookings_without_closure_event} rendez-vous terminé(s) sans événement de clôture dans l’institut.</p>
        <h4>Passages sans rendez-vous</h4><p>Sources lues le {date(value.walk_ins.window.captured_at)}.</p>
        <p>{value.walk_ins.retained_terms_count} annulation(s) avec conditions commerciales conservées ; {value.walk_ins.legacy_unpriced_count} annulation(s) historique(s) sans prix.</p>
        {value.walk_ins.retained_amounts.map(group=><p key={group.currency || "unknown"}>{group.currency || "Devise inconnue"} : {revenueMoney(group.known_gross_minor)} de valeur commerciale connue, {group.missing_amount_count} montant(s) manquant(s), {group.invalid_amount_count} montant(s) invalide(s).</p>)}
        <p>Ces valeurs commerciales ne prouvent ni un revenu encaissé ni une perte récupérable.</p></>;
    }
    if(evidence.capability==="REVENUE_SUMMARY"){
      const value=evidence.result as RevenueBilling;
      return <><p>Du {date(value.window.start)} au {date(value.window.end)} (fin exclue). Historique complet et encaissement bancaire non établis.</p>
        <p>{value.ticket_count} ticket(s) payé(s) enregistré(s), {value.active_line_count} ligne(s) active(s).</p>
        {value.ticket_amounts.map(group=><section key={group.currency || "unknown"}><h4>{group.currency || "Devise inconnue"}</h4><p>Montant connu : {revenueMoney(group.known_gross_minor)}{group.currency ? ` ${group.currency}` : " (devise non établie)"}.</p><p>{group.missing_amount_count} montant(s) manquant(s), {group.invalid_amount_count} montant(s) invalide(s).</p><p>Total complet : {group.complete_gross_minor===null ? "non établi" : `${revenueMoney(group.complete_gross_minor)} ${group.currency}`}.</p></section>)}
        <p>{value.institute_undated_paid_tickets} ticket(s) payé(s) sans date dans l’institut ; {value.tickets_without_active_lines} ticket(s) sans ligne active sur la période.</p></>;
    }
    if(evidence.capability==="PLANNING_CONFLICTS"){
      const value=evidence.result as ConflictRead;
      return <><p>Conflits enregistrés pour {value.employee_id ? employee(value.employee_id) : resourceChoices.find(r=>r.id===value.resource_id)?.name || "Ressource sélectionnée"}, le {value.day}. La couverture complète de l’institut et l’activité physique ne sont pas établies.</p>
        <p>{value.source_count} source(s), {value.invalid_source_count} source(s) invalide(s), {value.overdue_open_source_count ?? value.overdue_unreleased_source_count} engagement(s) expiré(s) encore ouvert(s).</p>
        <p>{value.overlap_count} conflit(s) observé(s), jusqu’à 50 affichés.</p><ul>{value.overlaps.map((o,index)=><li key={index}>{date(o.start_at)} — {date(o.end_at)} · {formatWorkDuration(o.duration_us)}</li>)}</ul></>;
    }
    if (evidence.capability === "EMPLOYEE_CAPACITY") {
      const value=evidence.result as RevenueCapacity;
      return <><p>Journée sélectionnée : {value.day} ({value.timezone}). Horaires déclarés et activité finalisée enregistrée ; la présence complète et la capacité réservable ne sont pas établies.</p>
        <dl><dt>Collaboratrices</dt><dd>{value.employee_count}</dd><dt>Sans horaires exploitables</dt><dd>{value.employees_without_usable_hours}</dd><dt>Activité incertaine</dt><dd>{value.employees_with_uncertain_activity}</dd>
          <dt>Durée déclarée connue</dt><dd>{formatWorkDuration(value.known_declared_union_duration_us)}</dd><dt>Activité couverte connue</dt><dd>{formatWorkDuration(value.known_covered_busy_duration_us)}</dd>
          <dt>Durée inoccupée enregistrée</dt><dd>{value.recorded_unoccupied_duration_us===null ? "Non établie" : formatWorkDuration(value.recorded_unoccupied_duration_us)}</dd></dl>
        <p>Première page : jusqu’à 20 collaboratrices sur {value.employee_count}. Les totaux portent sur la population observée.</p>
        {value.rows.map(row=><section key={row.employee_id}><h4>{employee(row.employee_id)}</h4><p>Durée inoccupée enregistrée : {row.recorded_unoccupied_duration_us===null ? "non établie" : formatWorkDuration(row.recorded_unoccupied_duration_us)}.</p></section>)}</>;
    }
    if (evidence.capability === "CLIENT_REBOOKING_OPPORTUNITIES") {
      const value = evidence.result as RebookingFacts;
      const reviews = {available:"Reprise à examiner avec la cliente",already_booked:"Rendez-vous actif déjà enregistré",not_due:"Échéance de reprise non atteinte",disabled:"Règle de reprise désactivée",unavailable:"Opportunité non établie"};
      const diagnostics:Record<string,string> = {policy_absent:"Politique CRM non configurée",future_policy:"Date de politique à vérifier",future_registration:"Date d’inscription à vérifier",care_unavailable:"Dernier soin non établi",care_unlinked_ticket:"Ticket du soin non relié",care_invalid_owner_or_service:"Cliente ou prestation du soin à vérifier",care_invalid_actual_times:"Dates réelles du soin à vérifier",invalid_event_timing:"Échéance CRM à vérifier"};
      return <><h4>{reviews[value.review]}</h4><p>Selon la règle CRM et le soin enregistrés. L’historique complet reste indisponible. Vérifiez avec la cliente avant toute réservation.</p>
        {value.candidate && <dl><dt>Soin observé</dt><dd>{date(value.candidate.source.occurred_at)}</dd><dt>Échéance selon la règle</dt><dd>{date(value.candidate.due_at)}</dd></dl>}
        {!!value.active_bookings.length && <><h4>Rendez-vous actifs enregistrés</h4><ul>{value.active_bookings.map(booking=><li key={booking.appointment_id}>{serviceName(booking.service_id)} · {date(booking.start_at)} — {date(booking.end_at)}</li>)}</ul></>}
        {!!value.invalid_booking_count && <p>{value.invalid_booking_count} rendez-vous à vérifier ; aucune opportunité confirmée.</p>}
        <ul>{Object.entries(value.diagnostics).filter(([,count])=>count>0).map(([key,count])=><li key={key}>{diagnostics[key]} ({count}).</li>)}</ul>
        <p>Cette consultation n’envoie aucun message et n’autorise aucune réservation.</p></>;
    }
    if (evidence.capability === "CLIENT_SUMMARY") {
      const value = evidence.result as SegmentProfile, segment = value.segment;
      const labels: Record<string,string> = { NEW:"Nouvelle cliente",ACTIVE:"Active",LOYAL:"Fidèle",VIP:"VIP",AT_RISK:"À risque",DORMANT:"Inactive" };
      const unavailable: Record<string,string> = { policy_absent:"Politique CRM non configurée",future_policy:"Date de politique à vérifier",future_registration:"Date d’inscription à vérifier",future_closings:"Dates de paiement à vérifier",unrepresentable_horizon:"Période de politique à vérifier" };
      return <><p>Profil calculé selon la politique CRM enregistrée et les tickets clôturés observés. L’historique complet de la cliente reste indisponible.</p>
        {!segment ? <p>{unavailable[value.unavailable_reason || ""] || "Profil indisponible"}.</p> : <><h4>{segment.state ? labels[segment.state] : "Segment non établi"}</h4>
          <p>Période observée : du {date(segment.billing.window.start)} au {date(segment.billing.window.end)}.</p>
          <p>{segment.billing.closed_tickets} ticket(s) clôturé(s). {segment.billing.last_recorded_closed_at ? `Dernière clôture observée : ${date(segment.billing.last_recorded_closed_at)}.` : "Aucune clôture datée observée."}</p>
          {segment.billing.currencies.map(row => <p key={row.currency}>{crmMoney(row.known_gross_minor,row.currency)} de montants connus ; {row.missing_amount_tickets} montant(s) manquant(s), {row.invalid_amount_tickets} montant(s) invalide(s).</p>)}
          <p>{segment.billing.unknown_currency_tickets} ticket(s) de devise inconnue.</p></>}
        <p>{value.undated_paid_tickets} ticket(s) payé(s) sans date de clôture ; {value.future_paid_tickets} clôture(s) datée(s) dans le futur.</p></>;
    }
    if (evidence.capability === "CLIENT_READ") {
      const value = evidence.result as CustomerFacts;
      return <dl><dt>Cliente sélectionnée</dt><dd>{value.display_name}</dd><dt>Inscription enregistrée</dt><dd>{date(value.created_at)}</dd></dl>;
    }
    if (evidence.capability === "PLANNING_READ") {
      const value = evidence.result as PlanningFacts;
      return <><p>Sessions enregistrées du jour. Les rendez-vous et contraintes de réservation se consultent dans le planning.</p>
        {!value.rows.length && <p>Aucune collaboratrice retournée par le planning.</p>}
        {value.rows.map(row => <section key={row.employee_id}><h4>{employee(row.employee_id)} · {statuses[row.employee_status] || "État à vérifier"}</h4>
          {!row.sessions.length && <p>Aucune session enregistrée.</p>}<ul>{row.sessions.map(session => <li key={session.id}>{serviceName(session.service_id)} · {date(session.start_time)} — {date(session.planned_end_time)} · {statuses[session.status] || "État à vérifier"}</li>)}</ul></section>)}</>;
    }
    if (evidence.capability === "PLANNING_GAPS") {
      const value = evidence.result as Gaps;
      return <><p>Créneaux du moteur de planning, à actualiser avant une réservation. La totalité des horaires de travail n’est pas établie par cette consultation.</p>
        {!value.rows.length && <p>Aucun créneau retourné.</p>}{value.rows.map(row => <section key={row.employee_id}><h4>{employee(row.employee_id)} · {row.available ? "Disponible selon le planning" : "Indisponible maintenant"}</h4>
          {row.current_slot ? slot(row.current_slot) : <p>Créneau courant non établi.</p>}
          {!!row.upcoming_slots.length && <details><summary>Créneaux suivants ({row.upcoming_slots.length})</summary>{row.upcoming_slots.map((value,index) => <div key={index}>{slot(value)}</div>)}</details>}</section>)}</>;
    }
    const value = evidence.result as Outlook;
    return <><p>Jusqu’à 50 articles de la première page du catalogue. Les commandes en attente restent distinctes du stock reçu.</p>
      {!value.items.length && <p>Aucun article retourné.</p>}<div className="copilot-table"><table><caption>Stock enregistré et seuils</caption><thead><tr><th>Article</th><th>Unité</th><th>Stock reçu</th><th>Seuil</th><th>Déficit au seuil</th><th>Commandes en attente</th><th>Déficit si toutes arrivent</th></tr></thead>
        <tbody>{value.items.map(item => <tr key={item.item_id}><th scope="row">{item.item_name} · {item.item_sku}</th><td>{stockUnits[item.unit]}</td>
          {[item.on_hand,item.threshold,item.threshold_shortfall,item.pending_order_quantity,item.conditional_shortfall_after_all_orders].map((quantity,index) => <td key={index}>{stockDisplay(quantity)}</td>)}</tr>)}</tbody></table></div></>;
  }
  return <section className="copilot-panel" aria-label="Copilot"><h2>Consulter avec le Copilot</h2>
    <form onSubmit={event => { event.preventDefault(); void consult(); }}>
      <fieldset disabled={busy || !available.length}><label>Consultation<select value={name} onChange={event => { edit(); setName(event.target.value as ReadName | ""); setCustomer(""); setChoices([]); setService(""); }}>
        <option value="">Choisir une consultation</option>{available.map(value => <option key={value} value={value}>{readLabels[value]}</option>)}</select></label>
        {customerMode && <><label>Rechercher une cliente<input value={customerQuery} maxLength={160} onChange={event => { edit(); setCustomerQuery(event.target.value); setChoices([]); setCustomer(""); }} /></label>
          <button type="button" disabled={customerQuery.trim().length < 2} onClick={() => void search()}>Rechercher les clientes</button>
          <label>Cliente<select value={customer} onChange={event => { edit(); setCustomer(event.target.value); }}><option value="">Choisir une cliente</option>{choices.map(row => <option key={row.id} value={row.id}>{row.display_name}</option>)}</select></label>
          <p>Jusqu’à 20 résultats. Affinez la recherche si nécessaire.</p></>}
        {name === "PLANNING_GAPS" && <label>Prestation à vérifier<select value={service} onChange={event => { edit(); setService(event.target.value); }}><option value="">Sans prestation particulière</option>{services.filter(row => row.status === "active").map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>}
        <label>Votre question<textarea required value={question} maxLength={2000} onChange={event => { edit(); setQuestion(event.target.value); }} placeholder={name === "CLIENT_READ" ? "Consulter la fiche cliente" : name === "PLANNING_READ" ? "Consulter le planning du jour" : name === "PLANNING_GAPS" ? "Consulter les creneaux libres" : name === "STOCK_READ" ? "Consulter les stocks enregistres" : "Saisissez votre question"} /></label>
        {name === "EMPLOYEE_CAPACITY" && <label>Journée terminée<input type="date" required value={day} onChange={event=>{edit();setDay(event.target.value);}} /></label>}
        {(name === "REVENUE_SUMMARY" || name === "REVENUE_LOSS_ANALYSIS") && <><label>Début de période<input type="date" required value={periodStart} onChange={event=>{edit();setPeriodStart(event.target.value);}} /></label><label>Fin de période exclue<input type="date" required value={periodEnd} onChange={event=>{edit();setPeriodEnd(event.target.value);}} /></label><p>Dates à minuit dans le fuseau {timezone}. Choisissez une période terminée.</p></>}
        {name === "PLANNING_CONFLICTS" && <><label>Journée à examiner<input type="date" required value={day} onChange={event=>{edit();setDay(event.target.value);}} /></label>
          <button type="button" onClick={()=>void loadResources()}>Lire les ressources</button>
          <label>Collaboratrice ou ressource<select value={target} onChange={event=>{edit();setTarget(event.target.value);}}><option value="">Choisir une référence</option>{employees.filter(r=>r.institute_id===institute).map(r=><option key={r.id} value={`employee:${r.id}`}>{r.first_name}</option>)}{resourceChoices.map(r=><option key={r.id} value={`resource:${r.id}`}>{r.name}</option>)}</select></label></>}
        <button disabled={!name || !question.trim() || customerMode && !customer || name === "EMPLOYEE_CAPACITY" && !day || name === "PLANNING_CONFLICTS" && (!day || !target)}>Consulter</button>
      </fieldset>
    </form>{busy && <p role="status">Lecture en cours…</p>}{error && <p role="alert">{error}</p>}
    {response && <section aria-label="Réponse du Copilot"><h3>{response.status === "clarification" ? "Précisions nécessaires" : "Réponse"}</h3><p>{response.answer}</p>
      {response.evidence && <><p>Sources lues le {date(response.evidence.captured_at)} ({timezone}).</p>{facts()}</>}</section>}
  </section>;
}
