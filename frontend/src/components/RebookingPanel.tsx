import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { instituteBoundary, instituteSlot } from "../institute-calendar";
import { instituteTimeZone } from "../institute-time";
import { certificationInstant } from "../certification-utils";
import { validRebookingIntent, validRebooking, validRebookingCancellation, validRebookingPage, matchesRebooking, sameRebookingOriginal,
  type RebookingIntent, type Rebooking, type RebookingCancellation, type RebookingPage } from "../rebooking-utils";
import { RebookingChoices, type RebookingSelection } from "./RebookingChoices";
import type { Employee } from "../types";
const base = (institute: string) => `/workforce/institutes/${encodeURIComponent(institute)}`;
export function RebookingPanel(props: { institute: string; timezone?: string; employees: Employee[] }) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Directory key={JSON.stringify([props.institute, instituteTimeZone(props.timezone), getAccessToken()])} {...props} />;
}
function Directory({ institute, timezone, employees }: { institute: string; timezone?: string; employees: Employee[] }) {
  const token = getAccessToken(), actor = getOperatorSubject(), zone = instituteTimeZone(timezone), storageKey = `flowpilot.rebooking-request:${JSON.stringify([institute, actor])}`;
  const [saved, save] = useState<{ intent?: RebookingIntent; employee?: string; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storageKey); if (!raw) return {}; const value = JSON.parse(raw);
      return typeof value.employee_id === "string" && !!value.employee_id && value.employee_id.trim() === value.employee_id && value.employee_id.length <= 80
        && validRebookingIntent(value.intent, institute) && (value.intent.type === "create" || value.intent.original.employee_id === value.employee_id)
        ? { intent: value.intent, employee: value.employee_id } : { invalid: true };
    } catch { return { invalid: true }; }
  });
  const [employee, select] = useState(saved.employee || ""), [offset, paginate] = useState(0), [revision, refresh] = useState(0);
  const [page, setPage] = useState<RebookingPage>(), [loading, setLoading] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, reject] = useState(false);
  const [day, chooseDay] = useState(instituteSlot(new Date(), zone)?.date || ""), [selection, chooseSelection] = useState<RebookingSelection>();
  const [reason, setReason] = useState("");
  const [cancelling, chooseCancel] = useState<Rebooking>(), [cancelReason, setCancelReason] = useState("");
  const mounted = useRef(false), pending = useRef(false), scope = useRef({ employee, offset }); scope.current = { employee, offset };
  const declaration = useRef<HTMLFormElement>(null), staff = employees.filter(row => row.institute_id === institute);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const current = () => mounted.current && token === getAccessToken() && scope.current.employee === employee;
  useEffect(() => {
    let disposed = false; const valid = () => !disposed && current() && scope.current.offset === offset;
    setPage(undefined); setLoading(!!employee); if (!employee) return;
    void apiGet<RebookingPage>(`${base(institute)}/employees/${encodeURIComponent(employee)}/rebookings?limit=20&offset=${offset}`)
      .then(value => { if (!valid()) return; if (!validRebookingPage(value, institute, employee, offset)) throw new Error("Lecture des rebookings originales à vérifier."); setPage(value); })
      .catch(error => { if (valid()) setError(error instanceof Error ? error.message : "Rebookings indisponibles."); })
      .finally(() => { if (valid()) setLoading(false); });
    return () => { disposed = true; };
  }, [employee, offset, revision]);
  const visible = page?.employee_id === employee && page.page.offset === offset ? page : undefined;
  const frozen = busy || !!saved.intent || !!saved.invalid, locked = frozen || !visible || loading || !actor;
  const display = (instant: string) => {
    const slot = instituteSlot(instant, zone)!, minutes = Math.abs(slot.offset)/60000;
    return `${new Date(instant).toLocaleString("fr-CH", { timeZone: zone })} (UTC${slot.offset < 0 ? "−" : "+"}${String(Math.floor(minutes/60)).padStart(2, "0")}:${String(minutes%60).padStart(2, "0")})`;
  };
  async function run(intent: RebookingIntent) {
    if (pending.current || !current() || !actor || !visible || loading || saved.invalid || locked && !saved.intent || !validRebookingIntent(intent, institute) || intent.type === "cancel" && intent.original.employee_id !== employee) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); reject(false);
    let posting = false, returned = false;
    try {
      sessionStorage.setItem(storageKey, JSON.stringify({ employee_id: employee, intent })); save({ intent, employee });
      if (intent.type === "create") {
        const path = `${base(institute)}/rebookings/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<Rebooking | null>(path); if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<Rebooking>(`${base(institute)}/rebookings`, intent.terms); returned = true; }
        if (!current()) return;
        if (!validRebooking(original, institute, employee) || !matchesRebooking(original, intent.terms, actor)) throw new Error("Rebookings originales à vérifier.");
        const verified = await apiGet<Rebooking | null>(path); if (!current()) return;
        if (!validRebooking(verified, institute, employee) || !sameRebookingOriginal(original, verified)) throw new Error("Lecture originale des rebookings à vérifier.");
      } else {
        const path = `${base(institute)}/rebooking-cancellations/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<RebookingCancellation | null>(path); if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<RebookingCancellation>(`${base(institute)}/rebookings/${encodeURIComponent(intent.original.id)}/cancel`, intent.terms); returned = true; }
        if (!current()) return;
        const matches = (c: RebookingCancellation) => c.rebooking_id === intent.original.id && c.actor_id === actor && c.reason === intent.terms.reason && c.idempotency_key === intent.terms.idempotency_key;
        if (!validRebookingCancellation(original, institute, intent.original.id) || !matches(original)) throw new Error("Annulation originale des rebookings à vérifier.");
        const verified = await apiGet<Rebooking>(`${base(institute)}/rebookings/${encodeURIComponent(intent.original.id)}`); if (!current()) return;
        if (!validRebooking(verified, institute, employee) || !sameRebookingOriginal(verified, intent.original) || !verified.cancellation
          || verified.cancellation.id !== original.id || certificationInstant(verified.cancellation.created_at) !== certificationInstant(original.created_at) || !matches(verified.cancellation)) throw new Error("Lecture originale de l’annulation à vérifier.");
      }
      const fresh = await apiGet<RebookingPage>(`${base(institute)}/employees/${encodeURIComponent(employee)}/rebookings?limit=20&offset=${offset}`);
      if (!current()) return;
      if (!validRebookingPage(fresh, institute, employee, offset)) throw new Error("Actualisez les rebookings originales avant de poursuivre.");
      setPage(fresh); sessionStorage.removeItem(storageKey); save({}); chooseCancel(undefined); chooseSelection(undefined); setReason(""); setCancelReason("");
      setSuccess(intent.type === "create" ? "Rebooking déclaré." : "Déclaration annulée ; original conservé.");
    } catch (error) { if (current()) { setError(error instanceof Error ? error.message : "Rebookings indisponibles."); reject(posting && !returned && error instanceof ApiError && [400, 422].includes(error.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function submit(event: FormEvent) {
    event.preventDefault(); if (locked || !selection || selection.source.employee_id !== employee || !staff.some(s => s.id === employee)) return;
    const intent: RebookingIntent = { type: "create", terms: { source_kind: selection.source.kind, source_id: selection.source.id,
      target_appointment_id: selection.target.appointment_id, reason: reason.trim(), idempotency_key: crypto.randomUUID() } };
    if (!validRebookingIntent(intent, institute)) { setError("Choisissez les sources et un motif de déclaration."); return; }
    void run(intent);
  }
  const from = instituteBoundary(day, 0, zone), until = instituteBoundary(day, 24, zone);
  return <section className="workforce-panel absence-panel rebooking-panel" aria-label="Gestion du rebooking">
    <h2>Déclarations de rebooking</h2><p>Lien explicite entre une prestation terminée et une réservation du même client. Une réservation ne prouve pas un retour effectué.</p>
    <button disabled={!visible || loading} onClick={() => declaration.current?.scrollIntoView({ block: "start", behavior: "smooth" })}>Déclarer un rebooking</button>
    <label>Collaboratrice du rebooking<select disabled={frozen} value={employee} onChange={e => { select(e.target.value); paginate(0); chooseCancel(undefined); chooseSelection(undefined); setPage(undefined); setError(undefined); setSuccess(undefined); }}>
      <option value="">Choisir une collaboratrice</option>{staff.map(s => <option key={s.id} value={s.id}>{s.first_name}</option>)}</select></label>
    {employee && <><button disabled={loading || busy} onClick={() => { setError(undefined); refresh(v => v+1); }}>Actualiser les déclarations de rebooking</button>
      {loading && <p role="status">Lecture des déclarations…</p>}
      {visible && <><p>Lecture au {display(visible.generated_at)}</p><ul className="absence-list">{visible.rows.map(r => <li key={r.id}>
        <strong>{r.source_kind === "session" ? "Prestation walk-in" : "Rendez-vous"} terminé le {display(r.source_capture.actual_end)}</strong>
        <p>Réservation créée le {display(r.booking_capture.created_at)} · {r.reason}</p>
        {r.cancellation ? <p>Déclaration annulée, original conservé · {r.cancellation.reason}</p> : <button disabled={frozen} onClick={() => { chooseCancel(r); setCancelReason(""); }}>Annuler cette déclaration</button>}
        <details><summary>Provenance de la déclaration</summary><p>Original {r.id} · acteur {r.actor_id} · enregistrement {r.created_at}</p>
          <p>Prestation {r.source_id} · {r.source_capture.actual_start} – {r.source_capture.actual_end}</p>
          <p>Réservation {r.target_appointment_id} · événement {r.booking_capture.creation_event_id} · {r.booking_capture.created_at}</p>
          <p>Créneau original : {r.booking_capture.original_start} – {r.booking_capture.original_end}</p>
          <p>Créneau lors de la déclaration : {r.booking_capture.current_start} – {r.booking_capture.current_end}</p>
          {r.cancellation && <p>Annulation {r.cancellation.id} · acteur {r.cancellation.actor_id} · {r.cancellation.created_at}</p>}</details></li>)}</ul>
        {!visible.rows.length && <p>Aucune déclaration sur cette page.</p>}
        <div className="workforce-pages"><span>Déclarations : {visible.rows.length ? offset+1 : 0}–{offset+visible.rows.length} / {visible.page.total}</span>
          <button disabled={frozen || loading || !offset} onClick={() => paginate(offset-20)}>Déclarations précédentes</button>
          <button disabled={frozen || loading || offset+20 >= visible.page.total} onClick={() => paginate(offset+20)}>Déclarations suivantes</button></div></>}</>}
    <form ref={declaration} aria-label="Déclarer un rebooking" onSubmit={submit}><h3>Nouvelle déclaration</h3><fieldset disabled={locked}>
      <label>Jour de fin de prestation<input type="date" required value={day} onChange={e => { chooseDay(e.target.value); chooseSelection(undefined); }} /></label>
      {employee && from !== undefined && until !== undefined ? <RebookingChoices institute={institute} employee={employee} day={day}
        start={new Date(from).toISOString()} end={new Date(until).toISOString()} timezone={zone} disabled={locked} onSelection={chooseSelection} />
        : employee && <p>Choisissez un jour civil disponible dans ce fuseau.</p>}
      <label>Motif de déclaration<input required maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button type="submit" disabled={!selection}>Enregistrer le rebooking</button></fieldset></form>
    {cancelling && <form aria-label="Annuler la déclaration sélectionnée" onSubmit={e => { e.preventDefault(); if (!locked) void run({ type: "cancel", original: cancelling, terms: { reason: cancelReason.trim(), idempotency_key: crypto.randomUUID() } }); }}>
      <h3>Annuler la déclaration</h3><p>La prestation et la réservation restent intactes.</p><fieldset disabled={locked}>
        <label>Motif d’annulation du rebooking<input required maxLength={240} value={cancelReason} onChange={e => setCancelReason(e.target.value)} /></label>
        <button type="submit">Confirmer l’annulation de la déclaration</button><button type="button" onClick={() => chooseCancel(undefined)}>Fermer l’annulation</button></fieldset></form>}
    {saved.intent && <><p>Demande de rebooking conservée pour {staff.find(s => s.id === employee)?.first_name || employee}.</p>
      <p>{saved.intent.type === "create" ? `Prestation ${saved.intent.terms.source_id} · réservation ${saved.intent.terms.target_appointment_id}` : `Annulation : ${saved.intent.original.id}`} · {saved.intent.terms.reason}</p>
      <button disabled={busy || loading || !visible} onClick={() => void run(saved.intent!)}>Reprendre la demande de rebooking conservée</button></>}
    {rejected && saved.intent && <button disabled={busy} onClick={() => { try { sessionStorage.removeItem(storageKey); save({}); reject(false); setError(undefined); } catch (e) { setError(String(e)); } }}>Corriger la demande de rebooking refusée</button>}
    {saved.invalid && <p role="alert">La demande conservée ne peut pas être lue. Vérifiez son original avant une nouvelle opération.</p>}
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
  </section>;
}
