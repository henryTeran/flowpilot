import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { instituteSlot } from "../institute-calendar";
import { instituteTimeZone } from "../institute-time";
import { validEmployeeDay, type EmployeeDay } from "../employee-calendar-utils";
import type { Employee } from "../types";
import { CertificationReadOnly } from "./CertificationPanel";
import { EmployeeRevenuePanel } from "./EmployeeRevenuePanel";
import { EmployeeObjectivesPanel } from "./EmployeeObjectivesPanel";
import { EmployeeWorkHoursPanel } from "./EmployeeWorkHoursPanel";
import { EmployeeOccupationPanel } from "./EmployeeOccupationPanel";

type Props = { institute: string; timezone?: string; employees: Employee[] };
const reasons: Record<string, string> = { available_now: "Disponible maintenant", in_progress_session: "Prestation en cours",
  upcoming_appointment: "Rendez-vous engagé", employee_pause: "En pause", employee_absent: "Absente", employee_offline: "Hors service",
  busy_until: "Occupée", session_overdue: "Prestation en retard, fin inconnue", capacity_unknown: "Disponibilité inconnue",
  skills_missing: "Compétences requises manquantes", resource_capacity_unknown: "Capacité des ressources inconnue",
  resource_reserved: "Ressource réservée", scheduled_absence: "Absence ou congé enregistré" };
export function EmployeeCalendarPanel(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Profile key={JSON.stringify([props.institute, instituteTimeZone(props.timezone), getAccessToken()])} {...props} />;
}
function Profile({ institute, timezone, employees }: Props) {
  const revenueSection = useRef<HTMLDivElement>(null);
  const objectiveSection = useRef<HTMLDivElement>(null);
  const hoursSection = useRef<HTMLDivElement>(null);
  const occupationSection = useRef<HTMLDivElement>(null);
  const token = getAccessToken(), staff = employees.filter(employee => employee.institute_id === institute);
  const [employee, select] = useState(""), [day, setDay] = useState(() => instituteSlot(new Date(), timezone)!.date);
  const [offset, page] = useState(0), [revision, refresh] = useState(0), [result, setResult] = useState<EmployeeDay>();
  const [loading, setLoading] = useState(false), [error, setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(false);
    if (!employee) return;
    const civil = new Date(`${day}T12:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || day.startsWith("0000") || !Number.isFinite(civil.getTime()) || civil.toISOString().slice(0, 10) !== day) { setError("Choisissez une date valide."); return; }
    setLoading(true);
    void apiGet<EmployeeDay>(`/workforce/institutes/${encodeURIComponent(institute)}/employees/${encodeURIComponent(employee)}/day?day=${day}&limit=50&offset=${offset}`)
      .then(value => { if (!current()) return; if (!validEmployeeDay(value, institute, employee, day, offset)) throw new Error("Lecture du calendrier à vérifier."); setResult(value); })
      .catch(error => { if (current()) setError(error instanceof Error ? error.message : "Calendrier indisponible."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [employee, day, offset, revision]);
  const display = (value: string | null) => {
    if (!value) return "Non enregistré";
    const zone = result?.timezone || instituteTimeZone(timezone), slot = instituteSlot(value, zone)!;
    const minutes = Math.abs(slot.offset)/60000, sign = slot.offset < 0 ? "−" : "+";
    return `${new Date(value).toLocaleString("fr-CH", { timeZone: zone, dateStyle: "short", timeStyle: "short" })} (UTC${sign}${String(Math.floor(minutes/60)).padStart(2, "0")}:${String(minutes%60).padStart(2, "0")})`;
  };
  return <section className="workforce-panel employee-calendar" aria-label="Profil et calendrier individuel">
    <header><h2>Profil et calendrier individuel</h2><button disabled={!employee || loading} onClick={() => refresh(value => value+1)}>Actualiser le calendrier individuel</button></header>
    <div className="employee-calendar-controls"><label>Collaboratrice du calendrier<select value={employee} onChange={event => { select(event.target.value); page(0); }}><option value="">Choisir une collaboratrice</option>{staff.map(row => <option key={row.id} value={row.id}>{row.first_name}</option>)}</select></label>
      <label>Jour du calendrier individuel<input type="date" value={day} onChange={event => { setDay(event.target.value); page(0); }} /></label></div>
    {!employee && <p>Choisissez une collaboratrice pour consulter ses compétences, sa disponibilité et ses intervalles enregistrés.</p>}
    {loading && <p role="status">Lecture du calendrier individuel…</p>}{error && <p role="alert">{error} <button onClick={() => refresh(value => value+1)}>Réessayer le calendrier individuel</button></p>}
    {result && result.day === day && result.employee.id === employee && result.event_page.offset === offset && <><h3>{result.employee.first_name}</h3>
      <button onClick={() => revenueSection.current?.scrollIntoView({ block: "start", behavior: "smooth" })}>Consulter le CA attribué</button>
      <button onClick={() => objectiveSection.current?.scrollIntoView({ block: "start", behavior: "smooth" })}>Consulter les objectifs</button>
      <button onClick={() => hoursSection.current?.scrollIntoView({ block: "start", behavior: "smooth" })}>Consulter les heures</button>
      <button onClick={() => occupationSection.current?.scrollIntoView({ block: "start", behavior: "smooth" })}>Consulter l’occupation</button>
      <p>Compétences enregistrées : {result.employee.skills.join(", ") || "Aucune enregistrée"}</p>
      <p>Disponibilité au {display(result.generated_at)} : {result.availability.available ? "Disponible maintenant" : reasons[result.availability.current_slot?.reason || "capacity_unknown"]}.
        {!result.availability.available && result.availability.current_slot?.available_from && <> Prochaine fenêtre connue : {display(result.availability.current_slot.available_from)}.</>}</p>
      <p>Calendrier du {result.day} · {result.timezone} · {(Date.parse(result.day_end)-Date.parse(result.day_start))/3600000} heures réelles. La disponibilité ci-dessus décrit l’instant de lecture.</p>
      <ul className="absence-list">{result.events.map(event => <li key={`${event.source_kind}:${event.id}`}>
        <strong>{event.source_kind === "appointment" ? "Rendez-vous" : event.source_kind === "session" ? "Prestation" : event.absence_kind === "leave" ? "Congé" : "Absence"}</strong>
        {event.service_id && <p>{event.service_name || event.service_id}</p>}
        <p>Prévu : {display(event.start_time)} → {display(event.end_time)}</p>
        {event.source_kind !== "absence" && <p>Enregistré : début {display(event.actual_start_time)} · fin {display(event.actual_end_time)}</p>}
        {event.reason && <p>{event.reason}</p>}<p>{event.status === "cancelled" ? "Annulé, historique conservé" : event.status === "completed" ? "Terminé" : event.status === "recorded" ? "Enregistré" : event.status === "planned" || event.status === "scheduled" ? "Planifié" : event.status === "confirmed" ? "Confirmé" : event.status === "arrived" ? "Cliente arrivée" : event.status === "no_show" ? "Cliente absente" : event.status === "delayed" ? "En retard" : event.status === "extended" ? "Prolongé" : "En cours"}</p>
      </li>)}</ul>
      {!result.events.length && <p>Aucun intervalle sur cette page.</p>}<div className="workforce-pages"><span>Intervalles : {result.events.length ? offset+1 : 0}–{offset+result.events.length} / {result.event_page.total}</span>
        <button disabled={loading || !offset} onClick={() => page(offset-50)}>Intervalles précédents</button><button disabled={loading || offset+50 >= result.event_page.total} onClick={() => page(offset+50)}>Intervalles suivants</button></div>
      <CertificationReadOnly institute={institute} employee={employee} timezone={result.timezone} />
      <div ref={hoursSection}><EmployeeWorkHoursPanel institute={institute} employee={employee} day={day} start={result.day_start} end={result.day_end} timezone={result.timezone} /></div>
      <div ref={occupationSection}><EmployeeOccupationPanel institute={institute} employee={employee} day={day} start={result.day_start} end={result.day_end} timezone={result.timezone} /></div>
      <div ref={objectiveSection}><EmployeeObjectivesPanel institute={institute} employee={employee} /></div>
      <div ref={revenueSection}><EmployeeRevenuePanel institute={institute} employee={employee} day={day} start={result.day_start} end={result.day_end} timezone={result.timezone} /></div>
    </>}
  </section>;
}
