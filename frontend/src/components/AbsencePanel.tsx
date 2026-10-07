import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { instituteInstants, instituteSlot, nextInstituteSlot } from "../institute-calendar";
import { instituteTimeZone } from "../institute-time";
import type { Employee } from "../types";
import { validAbsence, validAbsenceIntent, matchesAbsence, validCancellation, matchesCancellation,
  type Absence, type AbsenceIntent, type AbsenceCancellation } from "../absence-utils";

type Props = { institute: string; timezone?: string; employees: Employee[]; onChanged?: () => Promise<boolean> };
const message = (error: unknown) => error instanceof Error ? error.message : "Absences indisponibles";
export function AbsencePanel(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Directory key={JSON.stringify([props.institute, instituteTimeZone(props.timezone), getAccessToken()])} {...props} />;
}
function Directory({ institute, timezone, employees, onChanged }: Props) {
  const zone = instituteTimeZone(timezone), token = getAccessToken(), actor = getOperatorSubject();
  const base = `/workforce/institutes/${encodeURIComponent(institute)}`;
  const storageKey = `flowpilot.absence-request:${JSON.stringify([institute, actor])}`;
  const [saved, save] = useState<{ intent?: AbsenceIntent; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storageKey); if (!raw) return {};
      const value = JSON.parse(raw); return validAbsenceIntent(value) ? { intent: value } : { invalid: true };
    } catch { return { invalid: true }; }
  });
  const [rows, setRows] = useState<Absence[]>(), [offset, page] = useState(0), [loading, setLoading] = useState(true);
  const [readError, setReadError] = useState<string>(), [error, setError] = useState<string>(), [success, setSuccess] = useState<string>();
  const [busy, setBusy] = useState(false), [rejected, reject] = useState(false);
  const mounted = useRef(false), sequence = useRef(0), pending = useRef(false), changed = useRef(onChanged); changed.current = onChanged;
  const current = () => mounted.current && token === getAccessToken();
  async function load() {
    const request = ++sequence.current;
    setRows(undefined); setLoading(true); setReadError(undefined);
    try {
      const values = await apiGet<Absence[]>(`${base}/absences?limit=50&offset=${offset}`);
      if (!current() || request !== sequence.current) return false;
      if (!Array.isArray(values) || values.length > 50 || !values.every(row => validAbsence(row, institute))
        || new Set(values.map(row => row.id)).size !== values.length) throw new Error("Lecture des absences à vérifier.");
      setRows(values); return true;
    } catch (error) { if (current() && request === sequence.current) setReadError(message(error)); return false; }
    finally { if (current() && request === sequence.current) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, [offset]);
  const staff = employees.filter(row => row.institute_id === institute);
  const firstSlot = useRef(nextInstituteSlot(zone)).current;
  const [employee, setEmployee] = useState(saved.intent?.type === "create" ? saved.intent.terms.employee_id : staff[0]?.id || "");
  const [kind, setKind] = useState<"absence" | "leave">("absence"), [reason, setReason] = useState("");
  const [startDate, setStartDate] = useState(firstSlot.date), [startTime, setStartTime] = useState(firstSlot.time);
  const [endDate, setEndDate] = useState(firstSlot.date), [endTime, setEndTime] = useState(firstSlot.time);
  const [startChoice, chooseStart] = useState(""), [endChoice, chooseEnd] = useState("");
  const [cancelId, cancel] = useState<string>(), [cancelReason, setCancelReason] = useState("");
  const starts = instituteInstants(startDate, startTime, zone), ends = instituteInstants(endDate, endTime, zone);
  const start = starts.length === 1 ? starts[0] : starts.includes(startChoice) ? startChoice : undefined;
  const end = ends.length === 1 ? ends[0] : ends.includes(endChoice) ? endChoice : undefined;
  const locked = busy || !!saved.intent || !!saved.invalid || loading || !rows || !actor;
  const savedCreate = saved.intent?.type === "create" ? saved.intent.terms : undefined;
  const cancelTarget = rows?.find(row => row.id === cancelId);
  const display = (value: string) => {
    const slot = instituteSlot(value, zone)!;
    const sign = slot.offset < 0 ? "−" : "+", minutes = Math.abs(slot.offset) / 60000;
    return `${slot.date} ${slot.time} (UTC${sign}${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")})`;
  };
  async function run(intent: AbsenceIntent) {
    if (pending.current || !current() || !actor || saved.invalid || loading || !rows) return;
    pending.current = true; sequence.current++; setBusy(true); setError(undefined); setSuccess(undefined); reject(false);
    let posting = false, postReturned = false;
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(intent)); save({ intent });
      if (intent.type === "create") {
        const path = `${base}/absences/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<Absence | null>(path);
        if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<Absence>(`${base}/absences`, intent.terms); postReturned = true; }
        if (!current()) return;
        if (!validAbsence(original, institute) || !matchesAbsence(original, intent.terms, actor)) throw new Error("Absence originale à vérifier.");
        const verified = await apiGet<Absence | null>(path);
        if (!current()) return;
        if (!validAbsence(verified, institute) || verified.id !== original.id || verified.created_at !== original.created_at
          || !matchesAbsence(verified, intent.terms, actor)) throw new Error("Lecture originale de l’absence à vérifier.");
      } else {
        const path = `${base}/absence-cancellations/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<AbsenceCancellation | null>(path);
        if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<AbsenceCancellation>(`${base}/absences/${encodeURIComponent(intent.absence_id)}/cancel`, intent.terms); postReturned = true; }
        if (!current()) return;
        if (!validCancellation(original, institute, intent.absence_id) || !matchesCancellation(original, intent.absence_id, intent.terms, actor)) throw new Error("Annulation originale à vérifier.");
        const verified = await apiGet<Absence>(`${base}/absences/${encodeURIComponent(intent.absence_id)}`);
        if (!current()) return;
        if (!validAbsence(verified, institute) || verified.id !== intent.absence_id || !verified.cancellation
          || verified.cancellation.id !== original.id || verified.cancellation.created_at !== original.created_at
          || !matchesCancellation(verified.cancellation, intent.absence_id, intent.terms, actor)) throw new Error("Lecture originale de l’annulation à vérifier.");
      }
      if (!await load() || !current()) throw new Error("Actualisez les absences avant de poursuivre.");
      if (changed.current && !await changed.current()) throw new Error("Actualisez le planning avant de poursuivre.");
      if (!current()) return;
      sessionStorage.removeItem(storageKey); save({}); cancel(undefined); setReason(""); setCancelReason("");
      setSuccess(intent.type === "create" ? "Absence enregistrée." : "Absence annulée ; historique conservé.");
    } catch (error) { if (current()) { setError(message(error)); reject(posting && !postReturned && error instanceof ApiError && [400, 422].includes(error.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function create(event: FormEvent) {
    event.preventDefault(); if (locked) return;
    if (!start || !end || Date.parse(end) <= Date.parse(start) || !staff.some(row => row.id === employee)) { setError("Choisissez une collaboratrice et une fin après le début, avec les occurrences requises."); return; }
    const intent: AbsenceIntent = { type: "create", terms: { employee_id: employee, kind, start_time: start, end_time: end, reason: reason.trim(), idempotency_key: crypto.randomUUID() } };
    if (!validAbsenceIntent(intent)) { setError("Un motif valide est requis."); return; } void run(intent);
  }
  const clock = (label: string, date: string, time: string, candidates: string[], choice: string,
    setDate: (value: string) => void, setTime: (value: string) => void, choose: (value: string) => void) => <div className="absence-clock">
    <label>Date de {label}<input type="date" required value={date} onChange={event => { setDate(event.target.value); choose(""); }} /></label>
    <label>Heure de {label}<input type="time" required value={time} onChange={event => { setTime(event.target.value); choose(""); }} /></label>
    {!candidates.length && <p>Cette heure n’existe pas à la date choisie.</p>}
    {candidates.length > 1 && <label>Occurrence de {label}<select required value={choice} onChange={event => choose(event.target.value)}><option value="">Choisir une occurrence</option>{candidates.map(value => <option key={value} value={value}>{display(value)}</option>)}</select></label>}
  </div>;
  return <section className="workforce-panel absence-panel" aria-label="Absences et congés de l’équipe">
    <header><h2>Absences et congés</h2><button disabled={busy || loading} onClick={() => void load()}>Actualiser les absences</button></header>
    <p>Horaires de l’institut · {zone}. Les intervalles enregistrés protègent les affectations et les rendez-vous.</p>
    {loading && <p role="status">Lecture des absences…</p>}{readError && <p role="alert">{readError} <button disabled={busy} onClick={() => void load()}>Réessayer les absences</button></p>}
    {rows && <><ul className="absence-list">{rows.map(row => <li key={row.id}><strong>{staff.find(employee => employee.id === row.employee_id)?.first_name || row.employee_id} · {row.kind === "leave" ? "Congé" : "Absence"}</strong>
      <p>{display(row.start_time)} → {display(row.end_time)}</p><p>{row.reason} · {row.actor_id}</p>
      {row.cancellation ? <p>Annulée : {row.cancellation.reason} · {row.cancellation.actor_id}</p> : <button disabled={locked} onClick={() => { cancel(row.id); setCancelReason(""); }}>Annuler cette absence</button>}</li>)}</ul>
      {!rows.length && <p>Aucune absence sur cette page.</p>}<div className="workforce-pages"><button disabled={busy || loading || !offset} onClick={() => page(offset - 50)}>Absences précédentes</button><button disabled={busy || loading || rows.length < 50} onClick={() => page(offset + 50)}>Absences suivantes</button></div></>}
    <form onSubmit={create} aria-label="Enregistrer une absence"><h3>Enregistrer une absence</h3><fieldset disabled={locked}>
      <label>Collaboratrice de l’absence<select required value={employee} onChange={event => setEmployee(event.target.value)}><option value="">Choisir</option>{staff.map(row => <option value={row.id} key={row.id}>{row.first_name}</option>)}</select></label>
      <label>Type d’absence<select value={kind} onChange={event => setKind(event.target.value as typeof kind)}><option value="absence">Absence</option><option value="leave">Congé</option></select></label>
      {clock("début", startDate, startTime, starts, startChoice, setStartDate, setStartTime, chooseStart)}
      {clock("fin", endDate, endTime, ends, endChoice, setEndDate, setEndTime, chooseEnd)}
      <label>Motif de l’absence<input required maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label><button type="submit">Enregistrer l’absence</button>
    </fieldset></form>
    {cancelTarget && <form aria-label="Annuler l’absence sélectionnée" onSubmit={event => { event.preventDefault(); if (locked) return;
      const intent: AbsenceIntent = { type: "cancel", absence_id: cancelTarget.id, terms: { reason: cancelReason.trim(), idempotency_key: crypto.randomUUID() } };
      if (!validAbsenceIntent(intent)) { setError("Un motif d’annulation valide est requis."); return; } void run(intent); }}>
      <p>Annuler : {staff.find(row => row.id === cancelTarget.employee_id)?.first_name || cancelTarget.employee_id} · {display(cancelTarget.start_time)} → {display(cancelTarget.end_time)}</p><fieldset disabled={locked}>
      <label>Motif d’annulation<input required maxLength={240} value={cancelReason} onChange={event => setCancelReason(event.target.value)} /></label><button type="submit">Confirmer l’annulation</button><button type="button" onClick={() => cancel(undefined)}>Fermer l’annulation</button>
    </fieldset></form>}
    {saved.intent && <><p>Demande conservée : {saved.intent.type === "create" ? "enregistrement d’une absence" : "annulation d’une absence"}. Reprenez son résultat original avant une nouvelle demande.</p>
      {savedCreate && <p>{staff.find(row => row.id === savedCreate.employee_id)?.first_name || savedCreate.employee_id} · {display(savedCreate.start_time)} → {display(savedCreate.end_time)} · {savedCreate.reason}</p>}
      {saved.intent.type === "cancel" && <p>Absence {saved.intent.absence_id} · {saved.intent.terms.reason}</p>}
      <button disabled={busy || loading || !rows} onClick={() => void run(saved.intent!)}>Reprendre la demande d’absence conservée</button></>}
    {rejected && saved.intent && <button disabled={busy} onClick={() => { try { sessionStorage.removeItem(storageKey); save({}); reject(false); setError(undefined); } catch (error) { setError(message(error)); } }}>Corriger la demande d’absence refusée</button>}
    {saved.invalid && <p role="alert">La demande conservée ne peut pas être lue. Vérifiez son original avant une nouvelle opération.</p>}
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
  </section>;
}
