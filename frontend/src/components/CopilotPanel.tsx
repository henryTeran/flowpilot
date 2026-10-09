import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getAccessToken, getOperatorInstitute, getOperatorRole } from "../api/session";
import { exactId, exactKeys, readLabels, validReadDiscovery, validReadResponse, type ReadName, type ReadResponse, type ReadSelection, type CustomerFacts, type PlanningFacts, type Gaps, type Slot } from "../copilot-read-utils";
import { certificationInstant } from "../certification-utils";
import { stockDisplay, stockUnits } from "../inventory-utils";
import type { Outlook } from "../outlook-utils";
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
    const selection: ReadSelection = name === "CLIENT_READ" ? { customer_id:customer } : name === "PLANNING_GAPS" && service ? { service_id:service } : {};
    if (name === "CLIENT_READ" && !choices.some(row => row.id === customer) || name === "PLANNING_GAPS" && service && !services.some(row => row.id === service)) {
      setError("Choisissez une référence proposée avant de consulter."); return;
    }
    flight.current = true; const seq = ++sequence.current;
    setBusy(true); setError(undefined); setResponse(undefined);
    try {
      const value = await apiPost<unknown>("/copilot/query",{ message:question.trim(),ui_context:selection });
      if (!current(seq)) return;
      if (!await validReadResponse(value,institute,name,selection)) throw new Error("Invalid evidence");
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
        {name === "CLIENT_READ" && <><label>Rechercher une cliente<input value={customerQuery} maxLength={160} onChange={event => { edit(); setCustomerQuery(event.target.value); setChoices([]); setCustomer(""); }} /></label>
          <button type="button" disabled={customerQuery.trim().length < 2} onClick={() => void search()}>Rechercher les clientes</button>
          <label>Cliente<select value={customer} onChange={event => { edit(); setCustomer(event.target.value); }}><option value="">Choisir une cliente</option>{choices.map(row => <option key={row.id} value={row.id}>{row.display_name}</option>)}</select></label>
          <p>Jusqu’à 20 résultats. Affinez la recherche si nécessaire.</p></>}
        {name === "PLANNING_GAPS" && <label>Prestation à vérifier<select value={service} onChange={event => { edit(); setService(event.target.value); }}><option value="">Sans prestation particulière</option>{services.filter(row => row.status === "active").map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>}
        <label>Votre question<textarea required value={question} maxLength={2000} onChange={event => { edit(); setQuestion(event.target.value); }} placeholder={name === "CLIENT_READ" ? "Consulter la fiche cliente" : name === "PLANNING_READ" ? "Consulter le planning du jour" : name === "PLANNING_GAPS" ? "Consulter les creneaux libres" : name === "STOCK_READ" ? "Consulter les stocks enregistres" : "Saisissez votre question"} /></label>
        <button disabled={!name || !question.trim() || name === "CLIENT_READ" && !customer}>Consulter</button>
      </fieldset>
    </form>{busy && <p role="status">Lecture en cours…</p>}{error && <p role="alert">{error}</p>}
    {response && <section aria-label="Réponse du Copilot"><h3>{response.status === "clarification" ? "Précisions nécessaires" : "Réponse"}</h3><p>{response.answer}</p>
      {response.evidence && <><p>Sources lues le {date(response.evidence.captured_at)} ({timezone}).</p>{facts()}</>}</section>}
  </section>;
}
