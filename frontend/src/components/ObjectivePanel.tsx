import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { instituteSlot } from "../institute-calendar";
import { instituteTimeZone } from "../institute-time";
import type { Employee } from "../types";
import { EmployeeObjectivesPanel } from "./EmployeeObjectivesPanel";
import { validObjective, validObjectiveCancellation, validObjectiveIntent, validObjectivePage, matchesObjective, sameObjectiveOriginal,
  type Objective, type ObjectiveCancellation, type ObjectiveIntent, type ObjectivePage } from "../objective-utils";
const base = (institute: string) => `/workforce/institutes/${encodeURIComponent(institute)}`;
export function ObjectivePanel(props: { institute: string; timezone?: string; employees: Employee[] }) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Directory key={JSON.stringify([props.institute, getAccessToken()])} {...props} />;
}
function Directory({ institute, timezone, employees }: { institute: string; timezone?: string; employees: Employee[] }) {
  const token = getAccessToken(), actor = getOperatorSubject(), zone = instituteTimeZone(timezone);
  const storageKey = `flowpilot.objective-request:${JSON.stringify([institute, actor])}`;
  const [saved, save] = useState<{ intent?: ObjectiveIntent; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storageKey); if (!raw) return {};
      const value = JSON.parse(raw); return validObjectiveIntent(value, institute) ? { intent: value } : { invalid: true };
    } catch { return { invalid: true }; }
  });
  const intentEmployee = (intent: ObjectiveIntent) => intent.type === "create" ? intent.terms.employee_id : intent.original.employee_id;
  const [employee, select] = useState(saved.intent ? intentEmployee(saved.intent) : ""), [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false), [revision, refresh] = useState(0), [error, setError] = useState<string>(), [success, setSuccess] = useState<string>();
  const [rejected, reject] = useState(false), [cancelling, chooseCancel] = useState<Objective>(), [cancelReason, setCancelReason] = useState("");
  const [title, setTitle] = useState(""), [metric, setMetric] = useState<"closed_attributed_gross" | "completed_sessions">("closed_attributed_gross");
  const [currency, setCurrency] = useState<"CHF" | "EUR">("CHF"), [target, setTarget] = useState(""), [reason, setReason] = useState("");
  const day = useRef(instituteSlot(new Date(), zone)!.date).current;
  const [firstDay, setFirstDay] = useState(day), [lastDay, setLastDay] = useState(day);
  const staff = employees.filter(row => row.institute_id === institute), mounted = useRef(false), pending = useRef(false), scope = useRef(employee); scope.current = employee;
  const declaration = useRef<HTMLFormElement>(null);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const current = () => mounted.current && token === getAccessToken() && scope.current === employee;
  const frozen = busy || !!saved.intent || !!saved.invalid, locked = frozen || !employee || !ready || !actor;
  async function run(intent: ObjectiveIntent) {
    if (pending.current || !ready || !actor || saved.invalid || !current() || intentEmployee(intent) !== employee || locked && !saved.intent) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); reject(false);
    let posting = false, returned = false;
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(intent)); save({ intent });
      if (intent.type === "create") {
        const path = `${base(institute)}/objectives/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<Objective | null>(path);
        if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<Objective>(`${base(institute)}/objectives`, intent.terms); returned = true; }
        if (!current()) return;
        if (!validObjective(original, institute, employee) || !matchesObjective(original, intent.terms, actor)) throw new Error("Objectif original à vérifier.");
        const verified = await apiGet<Objective | null>(path);
        if (!current()) return;
        if (!validObjective(verified, institute, employee) || !sameObjectiveOriginal(original, verified)) throw new Error("Lecture originale de l’objectif à vérifier.");
      } else {
        const path = `${base(institute)}/objective-cancellations/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<ObjectiveCancellation | null>(path);
        if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<ObjectiveCancellation>(`${base(institute)}/objectives/${encodeURIComponent(intent.original.id)}/cancel`, intent.terms); returned = true; }
        if (!current()) return;
        const matches = (c: ObjectiveCancellation) => c.actor_id === actor && c.objective_id === intent.original.id
          && c.reason === intent.terms.reason && c.idempotency_key === intent.terms.idempotency_key;
        if (!validObjectiveCancellation(original, institute, intent.original.id) || !matches(original)) throw new Error("Annulation originale à vérifier.");
        const verified = await apiGet<Objective>(`${base(institute)}/objectives/${encodeURIComponent(intent.original.id)}`);
        if (!current()) return;
        if (!validObjective(verified, institute, employee) || !sameObjectiveOriginal(verified, intent.original) || !verified.cancellation
          || verified.cancellation.id !== original.id || verified.cancellation.created_at !== original.created_at || !matches(verified.cancellation)) throw new Error("Lecture originale de l’annulation à vérifier.");
      }
      const page = await apiGet<ObjectivePage>(`${base(institute)}/employees/${encodeURIComponent(employee)}/objectives?limit=20&offset=0`);
      if (!current()) return;
      if (!validObjectivePage(page, institute, employee, 0)) throw new Error("Actualisez les objectifs avant de poursuivre.");
      sessionStorage.removeItem(storageKey); save({}); chooseCancel(undefined); setReason(""); setCancelReason(""); setReady(false); refresh(v => v+1);
      if (intent.type === "create") { setTitle(""); setTarget(""); }
      setSuccess(intent.type === "create" ? "Objectif enregistré." : "Objectif annulé ; original conservé.");
    } catch (error) { if (current()) { setError(error instanceof Error ? error.message : "Objectifs indisponibles."); reject(posting && !returned && error instanceof ApiError && [400, 422].includes(error.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function submit(event: FormEvent) {
    event.preventDefault(); if (locked || !staff.some(row => row.id === employee)) return;
    const intent: ObjectiveIntent = { type: "create", terms: { employee_id: employee, title: title.trim(), metric,
      currency: metric === "completed_sessions" ? null : currency, target: target.trim().replace(",", "."), first_day: firstDay, last_day: lastDay,
      reason: reason.trim(), idempotency_key: crypto.randomUUID() } };
    if (!validObjectiveIntent(intent, institute)) { setError("Complétez la cible positive, l’unité et les jours inclus de la période."); return; } void run(intent);
  }
  return <section className="workforce-panel absence-panel objective-panel" aria-label="Gestion des objectifs">
    <h2>Objectifs</h2><p>Cibles déclarées par la responsable · nouveaux objectifs dans le fuseau {zone}.</p>
    <button disabled={!ready} onClick={() => declaration.current?.scrollIntoView({ block: "start", behavior: "smooth" })}>Déclarer un objectif</button>
    <label>Collaboratrice des objectifs<select disabled={frozen} value={employee} onChange={event => { setReady(false); select(event.target.value); chooseCancel(undefined); setSuccess(undefined); setError(undefined); }}>
      <option value="">Choisir une collaboratrice</option>{staff.map(row => <option key={row.id} value={row.id}>{row.first_name}</option>)}</select></label>
    {employee && <EmployeeObjectivesPanel key={JSON.stringify([employee, revision])} institute={institute} employee={employee} blocked={frozen} onRead={setReady}
      onCancel={row => { chooseCancel(row); setCancelReason(""); }} />}
    <form ref={declaration} aria-label="Enregistrer un objectif" onSubmit={submit}><h3>Enregistrer un objectif</h3><fieldset disabled={locked}>
      <label>Intitulé de l’objectif<input required maxLength={120} value={title} onChange={event => setTitle(event.target.value)} /></label>
      <label>Mesure de l’objectif<select value={metric} onChange={event => setMetric(event.target.value as typeof metric)}><option value="closed_attributed_gross">CA brut attribué clôturé en interne</option><option value="completed_sessions">Prestations effectivement terminées</option></select></label>
      {metric === "closed_attributed_gross" && <label>Devise de l’objectif<select value={currency} onChange={event => setCurrency(event.target.value as typeof currency)}><option>CHF</option><option>EUR</option></select></label>}
      <label>Cible de l’objectif<input required inputMode="decimal" maxLength={32} value={target} onChange={event => setTarget(event.target.value)} /></label>
      <label>Premier jour inclus<input type="date" required value={firstDay} onChange={event => setFirstDay(event.target.value)} /></label>
      <label>Dernier jour inclus<input type="date" required value={lastDay} onChange={event => setLastDay(event.target.value)} /></label>
      <label>Motif de l’objectif<input required maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label><button type="submit">Enregistrer l’objectif</button>
    </fieldset></form>
    {cancelling && <form aria-label="Annuler l’objectif sélectionné" onSubmit={event => { event.preventDefault(); if (locked) return;
      const intent: ObjectiveIntent = { type: "cancel", original: cancelling, terms: { reason: cancelReason.trim(), idempotency_key: crypto.randomUUID() } };
      if (!validObjectiveIntent(intent, institute)) { setError("Un motif d’annulation valide est requis."); return; } void run(intent); }}>
      <h3>Annuler : {cancelling.title}</h3><fieldset disabled={locked}><label>Motif d’annulation de l’objectif<input required maxLength={240} value={cancelReason} onChange={event => setCancelReason(event.target.value)} /></label>
        <button type="submit">Confirmer l’annulation de l’objectif</button><button type="button" onClick={() => chooseCancel(undefined)}>Fermer l’annulation</button></fieldset></form>}
    {saved.intent && <><p>Demande d’objectif conservée pour {staff.find(row => row.id === employee)?.first_name || employee}.</p>
      <p>{saved.intent.type === "create" ? `${saved.intent.terms.title} · ${saved.intent.terms.target} ${saved.intent.terms.currency || "prestations terminées"} · ${saved.intent.terms.first_day} → ${saved.intent.terms.last_day}` : `Annulation : ${saved.intent.original.title} · ${saved.intent.terms.reason}`}</p>
      <button disabled={busy || !ready} onClick={() => void run(saved.intent!)}>Reprendre la demande d’objectif conservée</button></>}
    {rejected && saved.intent && <button disabled={busy} onClick={() => { try { sessionStorage.removeItem(storageKey); save({}); reject(false); setError(undefined); } catch (error) { setError(String(error)); } }}>Corriger la demande d’objectif refusée</button>}
    {saved.invalid && <p role="alert">La demande d’objectif conservée ne peut pas être lue. Vérifiez son original avant une nouvelle opération.</p>}
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
  </section>;
}
