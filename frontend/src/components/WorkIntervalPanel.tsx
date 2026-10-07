import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { instituteInstants, instituteSlot } from "../institute-calendar";
import { instituteTimeZone } from "../institute-time";
import { certificationInstant } from "../certification-utils";
import { validWorkIntent, validWorkInterval, validWorkCancellation, validWorkPage, matchesWork, sameWorkOriginal,
  formatWorkDuration, type WorkIntent, type WorkInterval, type WorkCancellation, type WorkPage } from "../work-hours-utils";
import type { Employee } from "../types";
const base = (institute: string) => `/workforce/institutes/${encodeURIComponent(institute)}`;
export function WorkIntervalPanel(props: { institute: string; timezone?: string; employees: Employee[] }) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Directory key={JSON.stringify([props.institute, instituteTimeZone(props.timezone), getAccessToken()])} {...props} />;
}
function Directory({ institute, timezone, employees }: { institute: string; timezone?: string; employees: Employee[] }) {
  const token = getAccessToken(), actor = getOperatorSubject(), zone = instituteTimeZone(timezone), storageKey = `flowpilot.work-request:${JSON.stringify([institute, actor])}`;
  const [saved, save] = useState<{ intent?: WorkIntent; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storageKey); if (!raw) return {}; const value = JSON.parse(raw);
      return validWorkIntent(value, institute) ? { intent: value } : { invalid: true };
    } catch { return { invalid: true }; }
  });
  const intentEmployee = (i: WorkIntent) => i.type === "create" ? i.terms.employee_id : i.original.employee_id;
  const [employee, select] = useState(saved.intent ? intentEmployee(saved.intent) : ""), [offset, paginate] = useState(0), [revision, refresh] = useState(0);
  const [page, setPage] = useState<WorkPage>(), [loading, setLoading] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, reject] = useState(false);
  const [firstDate, setFirstDate] = useState(""), [firstTime, setFirstTime] = useState(""), [lastDate, setLastDate] = useState(""), [lastTime, setLastTime] = useState("");
  const [firstChoice, chooseFirst] = useState(""), [lastChoice, chooseLast] = useState(""), [reason, setReason] = useState("");
  const [cancelling, chooseCancel] = useState<WorkInterval>(), [cancelReason, setCancelReason] = useState("");
  const mounted = useRef(false), pending = useRef(false), scope = useRef({ employee, offset }); scope.current = { employee, offset };
  const declaration = useRef<HTMLFormElement>(null), staff = employees.filter(row => row.institute_id === institute);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const current = () => mounted.current && token === getAccessToken() && scope.current.employee === employee;
  useEffect(() => {
    let disposed = false; const valid = () => !disposed && current() && scope.current.offset === offset;
    setPage(undefined); setLoading(!!employee); if (!employee) return;
    void apiGet<WorkPage>(`${base(institute)}/employees/${encodeURIComponent(employee)}/work-intervals?limit=20&offset=${offset}`)
      .then(value => { if (!valid()) return; if (!validWorkPage(value, institute, employee, offset)) throw new Error("Lecture des heures originales à vérifier."); setPage(value); })
      .catch(error => { if (valid()) setError(error instanceof Error ? error.message : "Heures indisponibles."); })
      .finally(() => { if (valid()) setLoading(false); });
    return () => { disposed = true; };
  }, [employee, offset, revision]);
  const visible = page?.employee_id === employee && page.page.offset === offset ? page : undefined;
  const frozen = busy || !!saved.intent || !!saved.invalid, locked = frozen || !visible || loading || !actor;
  const display = (instant: string) => {
    const slot = instituteSlot(instant, zone)!, minutes = Math.abs(slot.offset)/60000;
    return `${new Date(instant).toLocaleString("fr-CH", { timeZone: zone })} (UTC${slot.offset < 0 ? "−" : "+"}${String(Math.floor(minutes/60)).padStart(2, "0")}:${String(minutes%60).padStart(2, "0")})`;
  };
  async function run(intent: WorkIntent) {
    if (pending.current || !current() || !actor || !visible || loading || saved.invalid || locked && !saved.intent || intentEmployee(intent) !== employee) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); reject(false);
    let posting = false, returned = false;
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(intent)); save({ intent });
      if (intent.type === "create") {
        const path = `${base(institute)}/work-intervals/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<WorkInterval | null>(path); if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<WorkInterval>(`${base(institute)}/work-intervals`, intent.terms); returned = true; }
        if (!current()) return;
        if (!validWorkInterval(original, institute, employee) || !matchesWork(original, intent.terms, actor)) throw new Error("Heures originales à vérifier.");
        const verified = await apiGet<WorkInterval | null>(path); if (!current()) return;
        if (!validWorkInterval(verified, institute, employee) || !sameWorkOriginal(original, verified)) throw new Error("Lecture originale des heures à vérifier.");
      } else {
        const path = `${base(institute)}/work-interval-cancellations/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<WorkCancellation | null>(path); if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<WorkCancellation>(`${base(institute)}/work-intervals/${encodeURIComponent(intent.original.id)}/cancel`, intent.terms); returned = true; }
        if (!current()) return;
        const matches = (c: WorkCancellation) => c.work_interval_id === intent.original.id && c.actor_id === actor && c.reason === intent.terms.reason && c.idempotency_key === intent.terms.idempotency_key;
        if (!validWorkCancellation(original, institute, intent.original.id) || !matches(original)) throw new Error("Annulation originale des heures à vérifier.");
        const verified = await apiGet<WorkInterval>(`${base(institute)}/work-intervals/${encodeURIComponent(intent.original.id)}`); if (!current()) return;
        if (!validWorkInterval(verified, institute, employee) || !sameWorkOriginal(verified, intent.original) || !verified.cancellation
          || verified.cancellation.id !== original.id || verified.cancellation.created_at !== original.created_at || !matches(verified.cancellation)) throw new Error("Lecture originale de l’annulation à vérifier.");
      }
      const fresh = await apiGet<WorkPage>(`${base(institute)}/employees/${encodeURIComponent(employee)}/work-intervals?limit=20&offset=${offset}`);
      if (!current()) return;
      if (!validWorkPage(fresh, institute, employee, offset)) throw new Error("Actualisez les heures originales avant de poursuivre.");
      setPage(fresh); sessionStorage.removeItem(storageKey); save({}); chooseCancel(undefined); setReason(""); setCancelReason("");
      setSuccess(intent.type === "create" ? "Heures effectives enregistrées." : "Heures annulées ; original conservé.");
    } catch (error) { if (current()) { setError(error instanceof Error ? error.message : "Heures indisponibles."); reject(posting && !returned && error instanceof ApiError && [400, 422].includes(error.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function submit(event: FormEvent) {
    event.preventDefault(); if (locked || !staff.some(row => row.id === employee)) return;
    const first = instituteInstants(firstDate, firstTime, zone), last = instituteInstants(lastDate, lastTime, zone);
    const start = first.length === 1 ? first[0] : first.includes(firstChoice) ? firstChoice : undefined;
    const end = last.length === 1 ? last[0] : last.includes(lastChoice) ? lastChoice : undefined;
    if (!start || !end) { setError("Choisissez les instants et les occurrences effectives requises."); return; }
    const intent: WorkIntent = { type: "create", terms: { employee_id: employee, start_time: start, end_time: end, reason: reason.trim(), idempotency_key: crypto.randomUUID() } };
    if (!validWorkIntent(intent, institute) || certificationInstant(end)! > BigInt(Date.now())*1000n) { setError("Une période effective positive, déjà terminée, et un motif sont requis."); return; } void run(intent);
  }
  function clock(label: string, date: string, time: string, choice: string, setDate: (s: string) => void, setTime: (s: string) => void, choose: (s: string) => void) {
    const values = instituteInstants(date, time, zone);
    return <div className="absence-clock"><label>Date de {label}<input type="date" required value={date} onChange={e => { setDate(e.target.value); choose(""); }} /></label>
      <label>Heure de {label}<input type="time" required value={time} onChange={e => { setTime(e.target.value); choose(""); }} /></label>
      {date && time && !values.length && <p>Cette heure n’existe pas à la date choisie.</p>}
      {values.length > 1 && <label>Occurrence de {label}<select required value={choice} onChange={e => choose(e.target.value)}><option value="">Choisir une occurrence</option>{values.map(v => <option key={v} value={v}>{display(v)}</option>)}</select></label>}</div>;
  }
  return <section className="workforce-panel absence-panel work-interval-panel" aria-label="Gestion des heures effectives">
    <h2>Heures effectives</h2><p>Intervalles de travail déclarés, hors pauses · {zone}. Le planning ne fournit pas les heures effectives.</p>
    <button disabled={!visible || loading} onClick={() => declaration.current?.scrollIntoView({ block: "start", behavior: "smooth" })}>Déclarer des heures</button>
    <label>Collaboratrice des heures<select disabled={frozen} value={employee} onChange={e => { select(e.target.value); paginate(0); chooseCancel(undefined); setPage(undefined); setError(undefined); setSuccess(undefined); }}><option value="">Choisir une collaboratrice</option>{staff.map(r => <option key={r.id} value={r.id}>{r.first_name}</option>)}</select></label>
    {employee && <><button disabled={loading || busy} onClick={() => { setError(undefined); refresh(v => v+1); }}>Actualiser les heures originales</button>
      {loading && <p role="status">Lecture des heures originales…</p>}
      {visible && <><p>Lecture au {display(visible.generated_at)}</p><ul className="absence-list">{visible.rows.map(r => <li key={r.id}>
        <strong>{formatWorkDuration(String(certificationInstant(r.end_time)!-certificationInstant(r.start_time)!))}</strong><p>{display(r.start_time)} → {display(r.end_time)}</p><p>{r.reason}</p>
        {r.cancellation ? <p>Annulé, original conservé · {r.cancellation.reason}</p> : <button disabled={frozen} onClick={() => { chooseCancel(r); setCancelReason(""); }}>Annuler ces heures</button>}
        <details><summary>Provenance des heures originales</summary><p>Original {r.id} · {r.actor_id} · {r.created_at}</p><p>{r.start_time} → {r.end_time}</p>{r.cancellation && <p>Annulation {r.cancellation.id} · {r.cancellation.actor_id} · {r.cancellation.created_at}</p>}</details></li>)}</ul>
        {!visible.rows.length && <p>Aucune déclaration sur cette page.</p>}<div className="workforce-pages"><span>Déclarations : {visible.rows.length ? offset+1 : 0}–{offset+visible.rows.length} / {visible.page.total}</span>
          <button disabled={frozen || loading || !offset} onClick={() => paginate(offset-20)}>Déclarations précédentes</button><button disabled={frozen || loading || offset+20 >= visible.page.total} onClick={() => paginate(offset+20)}>Déclarations suivantes</button></div></>}</>}
    <form ref={declaration} aria-label="Enregistrer des heures effectives" onSubmit={submit}><h3>Enregistrer des heures effectives</h3><fieldset disabled={locked}>
      {clock("début effectif", firstDate, firstTime, firstChoice, setFirstDate, setFirstTime, chooseFirst)}
      {clock("fin effective", lastDate, lastTime, lastChoice, setLastDate, setLastTime, chooseLast)}
      <label>Motif des heures<input required maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label><button type="submit">Enregistrer les heures</button></fieldset></form>
    {cancelling && <form aria-label="Annuler les heures sélectionnées" onSubmit={e => { e.preventDefault(); if (locked) return;
      const intent: WorkIntent = { type: "cancel", original: cancelling, terms: { reason: cancelReason.trim(), idempotency_key: crypto.randomUUID() } };
      if (!validWorkIntent(intent, institute)) { setError("Un motif d’annulation valide est requis."); return; } void run(intent); }}>
      <p>Annuler : {display(cancelling.start_time)} → {display(cancelling.end_time)}</p><fieldset disabled={locked}>
        <label>Motif d’annulation des heures<input required maxLength={240} value={cancelReason} onChange={e => setCancelReason(e.target.value)} /></label>
        <button type="submit">Confirmer l’annulation des heures</button><button type="button" onClick={() => chooseCancel(undefined)}>Fermer l’annulation</button></fieldset></form>}
    {saved.intent && <><p>Demande d’heures conservée pour {staff.find(r => r.id === employee)?.first_name || employee}.</p>
      <p>{saved.intent.type === "create" ? `${saved.intent.terms.start_time} → ${saved.intent.terms.end_time}` : `Annulation : ${saved.intent.original.id}`} · {saved.intent.terms.reason}</p>
      <button disabled={busy || loading || !visible} onClick={() => void run(saved.intent!)}>Reprendre la demande d’heures conservée</button></>}
    {rejected && saved.intent && <button disabled={busy} onClick={() => { try { sessionStorage.removeItem(storageKey); save({}); reject(false); setError(undefined); } catch (e) { setError(String(e)); } }}>Corriger la demande d’heures refusée</button>}
    {saved.invalid && <p role="alert">La demande d’heures conservée ne peut pas être lue. Vérifiez son original avant une nouvelle opération.</p>}
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
  </section>;
}
