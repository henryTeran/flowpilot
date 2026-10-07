import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { instituteInstants, instituteSlot, nextInstituteSlot } from "../institute-calendar";
import { instituteTimeZone } from "../institute-time";
import type { Employee } from "../types";
import { validCertificationPage, validCertificationIntent, validCertification, validCertificationRevocation,
  matchesCertification, matchesRevocation, certificationEmployee, type CertificationPage,
  type CertificationIntent, type Certification, type CertificationRevocation, type CertificationState } from "../certification-utils";

const base = (institute: string) => `/workforce/institutes/${encodeURIComponent(institute)}`;
const message = (error: unknown) => error instanceof Error ? error.message : "Certifications indisponibles.";
const labels: Record<CertificationState, string> = { not_yet_valid: "Période déclarée à venir", in_validity_window: "Période déclarée en cours", expired: "Période déclarée terminée", revoked: "Certification révoquée" };
function display(value: string | null, timezone?: string) {
  if (!value) return "Sans date de fin déclarée";
  const zone = instituteTimeZone(timezone), slot = instituteSlot(value, zone)!;
  const minutes = Math.abs(slot.offset)/60000;
  return `${new Date(value).toLocaleString("fr-CH", { timeZone: zone, dateStyle: "short", timeStyle: "short" })} (UTC${slot.offset < 0 ? "−" : "+"}${String(Math.floor(minutes/60)).padStart(2, "0")}:${String(minutes%60).padStart(2, "0")})`;
}
function useRecords(institute: string, employee: string) {
  const token = getAccessToken(), [page, setPage] = useState<CertificationPage>(), [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false), [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0), scope = useRef({ employee, offset }); scope.current = { employee, offset };
  async function load() {
    const request = ++sequence.current;
    const current = () => mounted.current && token === getAccessToken() && request === sequence.current
      && scope.current.employee === employee && scope.current.offset === offset;
    setPage(undefined); setError(undefined); setLoading(!!employee);
    if (!employee) return false;
    try {
      const result = await apiGet<CertificationPage>(`${base(institute)}/employees/${encodeURIComponent(employee)}/certifications?limit=50&offset=${offset}`);
      if (!current()) return false;
      if (!validCertificationPage(result, institute, employee, offset)) throw new Error("Lecture des certifications à vérifier.");
      setPage(result); return true;
    } catch (error) { if (current()) setError(message(error)); return false; }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, [employee, offset]);
  const visible = page?.employee_id === employee && page.page.offset === offset ? page : undefined;
  return { page: visible, loading, error, offset, setOffset, load };
}
function Records({ data, timezone, blocked = false, onRevoke }: { data: ReturnType<typeof useRecords>; timezone?: string;
  blocked?: boolean; onRevoke?: (row: Certification) => void }) {
  return <section aria-label="Certifications enregistrées">
    <header><h3>Certifications enregistrées</h3><button disabled={blocked || data.loading} onClick={() => void data.load()}>Actualiser les certifications</button></header>
    {data.loading && <p role="status">Lecture des certifications…</p>}{data.error && <p role="alert">{data.error}</p>}
    {data.page && <><p>Lecture au {display(data.page.generated_at, timezone)}</p><ul className="absence-list certification-list">{data.page.rows.map(({ certificate: row, state }) => <li key={row.id}>
      <strong>{row.title} · {row.code}</strong><p>Émetteur : {row.issuer} · Référence : {row.reference}</p>
      <p>Date d’émission : {row.issued_on || "Non connue"}</p><p>Validité déclarée : {display(row.valid_from, timezone)} → {display(row.valid_until, timezone)}</p>
      <p>{labels[state]}</p><p>{row.reason} · {row.actor_id}</p>
      {row.revocation && <p>Révocation : {row.revocation.reason} · {row.revocation.actor_id} · {display(row.revocation.created_at, timezone)}</p>}
      {onRevoke && !row.revocation && <button disabled={blocked} onClick={() => onRevoke(row)}>Révoquer cette certification</button>}
    </li>)}</ul>{!data.page.rows.length && <p>Aucune certification sur cette page.</p>}
      <div className="workforce-pages"><span>Certifications : {data.page.rows.length ? data.offset+1 : 0}–{data.offset+data.page.rows.length} / {data.page.page.total}</span>
        <button disabled={blocked || data.loading || !data.offset} onClick={() => data.setOffset(data.offset-50)}>Certifications précédentes</button>
        <button disabled={blocked || data.loading || data.offset+50 >= data.page.page.total} onClick={() => data.setOffset(data.offset+50)}>Certifications suivantes</button></div></>}
  </section>;
}
export function CertificationReadOnly({ institute, employee, timezone }: { institute: string; employee: string; timezone?: string }) {
  if (!institute || !employee || getOperatorRole() !== "responsable_institut") return null;
  return <ReadOnly key={JSON.stringify([institute, employee, getAccessToken()])} institute={institute} employee={employee} timezone={timezone} />;
}
function ReadOnly({ institute, employee, timezone }: { institute: string; employee: string; timezone?: string }) {
  const data = useRecords(institute, employee);
  return <div className="certification-panel"><Records data={data} timezone={timezone} /></div>;
}
export function CertificationPanel(props: { institute: string; timezone?: string; employees: Employee[] }) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Directory key={JSON.stringify([props.institute, instituteTimeZone(props.timezone), getAccessToken()])} {...props} />;
}
function Directory({ institute, timezone, employees }: { institute: string; timezone?: string; employees: Employee[] }) {
  const token = getAccessToken(), actor = getOperatorSubject(), zone = instituteTimeZone(timezone);
  const storageKey = `flowpilot.certification-request:${JSON.stringify([institute, actor])}`;
  const [saved, save] = useState<{ intent?: CertificationIntent; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storageKey); if (!raw) return {};
      const value = JSON.parse(raw); return validCertificationIntent(value) ? { intent: value } : { invalid: true };
    } catch { return { invalid: true }; }
  });
  const [employee, select] = useState(saved.intent ? certificationEmployee(saved.intent) : ""), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, reject] = useState(false);
  const data = useRecords(institute, employee), staff = employees.filter(row => row.institute_id === institute);
  const mounted = useRef(false), pending = useRef(false), employeeScope = useRef(employee); employeeScope.current = employee;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const current = () => mounted.current && token === getAccessToken() && employeeScope.current === employee;
  const [code, setCode] = useState(""), [title, setTitle] = useState(""), [issuer, setIssuer] = useState(""), [reference, setReference] = useState("");
  const [issued, setIssued] = useState(""), [unknownIssued, setUnknownIssued] = useState(false), [reason, setReason] = useState("");
  const initial = useRef(nextInstituteSlot(zone)).current;
  const [startDate, setStartDate] = useState(initial.date), [startTime, setStartTime] = useState(initial.time), [startChoice, chooseStart] = useState("");
  const [endDate, setEndDate] = useState(initial.date), [endTime, setEndTime] = useState(initial.time), [endChoice, chooseEnd] = useState(""), [noEnd, setNoEnd] = useState(false);
  const [revoking, chooseRevocation] = useState<Certification>(), [revokeReason, setRevokeReason] = useState("");
  const frozen = busy || !!saved.intent || !!saved.invalid;
  const locked = frozen || !employee || !data.page || data.loading || !actor;
  useEffect(() => { chooseRevocation(undefined); setCode(""); setTitle(""); setIssuer(""); setReference(""); setReason(""); setIssued(""); }, [employee]);
  async function run(intent: CertificationIntent) {
    if (pending.current || locked && !saved.intent || data.loading || !data.page || !actor || saved.invalid
      || !current() || certificationEmployee(intent) !== employee) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); reject(false);
    let posting = false, postReturned = false;
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(intent)); save({ intent });
      if (intent.type === "create") {
        const originalPath = `${base(institute)}/certifications/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<Certification | null>(originalPath);
        if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<Certification>(`${base(institute)}/certifications`, intent.terms); postReturned = true; }
        if (!current()) return;
        if (!validCertification(original, institute, employee) || !matchesCertification(original, intent.terms, actor)) throw new Error("Certification originale à vérifier.");
        const verified = await apiGet<Certification | null>(originalPath);
        if (!current()) return;
        if (!validCertification(verified, institute, employee) || verified.id !== original.id || verified.created_at !== original.created_at
          || !matchesCertification(verified, intent.terms, actor)) throw new Error("Lecture originale de la certification à vérifier.");
      } else {
        const originalPath = `${base(institute)}/certification-revocations/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<CertificationRevocation | null>(originalPath);
        if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<CertificationRevocation>(`${base(institute)}/certifications/${encodeURIComponent(intent.certification_id)}/revoke`, intent.terms); postReturned = true; }
        if (!current()) return;
        if (!validCertificationRevocation(original, institute, intent.certification_id) || !matchesRevocation(original, intent.certification_id, intent.terms, actor)) throw new Error("Révocation originale à vérifier.");
        const verified = await apiGet<Certification>(`${base(institute)}/certifications/${encodeURIComponent(intent.certification_id)}`);
        if (!current()) return;
        if (!validCertification(verified, institute, employee) || verified.id !== intent.certification_id || !verified.revocation
          || verified.revocation.id !== original.id || verified.revocation.created_at !== original.created_at
          || !matchesRevocation(verified.revocation, intent.certification_id, intent.terms, actor)) throw new Error("Lecture originale de la révocation à vérifier.");
      }
      if (!await data.load() || !current()) throw new Error("Actualisez les certifications avant de poursuivre.");
      sessionStorage.removeItem(storageKey); save({}); chooseRevocation(undefined); setReason(""); setRevokeReason("");
      setSuccess(intent.type === "create" ? "Certification enregistrée." : "Certification révoquée ; original conservé.");
    } catch (error) { if (current()) { setError(message(error)); reject(posting && !postReturned && error instanceof ApiError && [400, 422].includes(error.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function submit(event: FormEvent) {
    event.preventDefault(); if (locked) return;
    const starts = instituteInstants(startDate, startTime, zone), ends = instituteInstants(endDate, endTime, zone);
    const start = starts.length === 1 ? starts[0] : starts.includes(startChoice) ? startChoice : undefined;
    const end = noEnd ? null : ends.length === 1 ? ends[0] : ends.includes(endChoice) ? endChoice : undefined;
    if (!start || end === undefined || !staff.some(row => row.id === employee)) { setError("Choisissez les dates et les occurrences de validité requises."); return; }
    const intent: CertificationIntent = { type: "create", terms: { employee_id: employee, code: code.trim(), title: title.trim(), issuer: issuer.trim(), reference: reference.trim(),
      issued_on: unknownIssued ? null : issued, valid_from: start, valid_until: end, reason: reason.trim(), idempotency_key: crypto.randomUUID() } };
    if (!validCertificationIntent(intent)) { setError("Complétez les informations et une période de validité cohérente."); return; }
    void run(intent);
  }
  function clock(label: string, date: string, time: string, choice: string, setDate: (value: string) => void, setTime: (value: string) => void, choose: (value: string) => void) {
    const candidates = instituteInstants(date, time, zone);
    return <div className="absence-clock"><label>Date de {label}<input type="date" required value={date} onChange={event => { setDate(event.target.value); choose(""); }} /></label>
      <label>Heure de {label}<input type="time" required value={time} onChange={event => { setTime(event.target.value); choose(""); }} /></label>
      {!candidates.length && <p>Cette heure n’existe pas à la date choisie.</p>}
      {candidates.length > 1 && <label>Occurrence de {label}<select required value={choice} onChange={event => choose(event.target.value)}><option value="">Choisir une occurrence</option>{candidates.map(value => <option key={value} value={value}>{display(value, zone)}</option>)}</select></label>}</div>;
  }
  const savedCreate = saved.intent?.type === "create" ? saved.intent.terms : undefined;
  return <section className="workforce-panel absence-panel certification-panel" aria-label="Gestion des certifications">
    <h2>Certifications</h2><p>Documents et périodes de validité déclarés · {zone}</p>
    <label>Collaboratrice des certifications<select disabled={frozen} value={employee} onChange={event => { select(event.target.value); data.setOffset(0); }}><option value="">Choisir une collaboratrice</option>{staff.map(row => <option key={row.id} value={row.id}>{row.first_name}</option>)}</select></label>
    {employee && <Records data={data} timezone={zone} blocked={frozen || data.loading || !data.page} onRevoke={row => { chooseRevocation(row); setRevokeReason(""); }} />}
    <form aria-label="Enregistrer une certification" onSubmit={submit}><h3>Enregistrer une certification</h3><fieldset disabled={locked}>
      <label>Code de certification<input required maxLength={64} value={code} onChange={event => setCode(event.target.value)} /></label>
      <label>Intitulé de certification<input required maxLength={120} value={title} onChange={event => setTitle(event.target.value)} /></label>
      <label>Émetteur du document<input required maxLength={120} value={issuer} onChange={event => setIssuer(event.target.value)} /></label>
      <label>Référence du document<input required maxLength={160} value={reference} onChange={event => setReference(event.target.value)} /></label>
      <div><label className="certification-check"><input type="checkbox" checked={unknownIssued} onChange={event => setUnknownIssued(event.target.checked)} />Date d’émission inconnue</label>
        {!unknownIssued && <label>Date d’émission<input type="date" required value={issued} onChange={event => setIssued(event.target.value)} /></label>}</div>
      {clock("début de validité", startDate, startTime, startChoice, setStartDate, setStartTime, chooseStart)}
      <div><label className="certification-check"><input type="checkbox" checked={noEnd} onChange={event => setNoEnd(event.target.checked)} />Sans date de fin déclarée</label>
        {!noEnd && clock("fin de validité", endDate, endTime, endChoice, setEndDate, setEndTime, chooseEnd)}</div>
      <label>Motif de déclaration<input required maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label><button type="submit">Enregistrer la certification</button>
    </fieldset></form>
    {revoking && <form aria-label="Révoquer la certification sélectionnée" onSubmit={event => { event.preventDefault(); if (locked) return;
      const intent: CertificationIntent = { type: "revoke", employee_id: employee, certification_id: revoking.id, terms: { reason: revokeReason.trim(), idempotency_key: crypto.randomUUID() } };
      if (!validCertificationIntent(intent)) { setError("Un motif de révocation valide est requis."); return; } void run(intent); }}>
      <p>Révoquer : {revoking.title} · {revoking.issuer} · {revoking.reference}</p><fieldset disabled={locked}>
        <label>Motif de révocation<input required maxLength={240} value={revokeReason} onChange={event => setRevokeReason(event.target.value)} /></label>
        <button type="submit">Confirmer la révocation</button><button type="button" onClick={() => chooseRevocation(undefined)}>Fermer la révocation</button></fieldset></form>}
    {saved.intent && <><p>Demande de certification conservée pour {staff.find(row => row.id === employee)?.first_name || employee}.</p>
      {savedCreate && <p>{savedCreate.title} · {savedCreate.issuer} · {savedCreate.reference} · {display(savedCreate.valid_from, zone)} → {display(savedCreate.valid_until, zone)}</p>}
      {saved.intent.type === "revoke" && <p>Révocation : {saved.intent.terms.reason}</p>}
      <button disabled={busy || data.loading || !data.page} onClick={() => void run(saved.intent!)}>Reprendre la demande de certification conservée</button></>}
    {rejected && saved.intent && <button disabled={busy} onClick={() => { try { sessionStorage.removeItem(storageKey); save({}); reject(false); setError(undefined); } catch (error) { setError(message(error)); } }}>Corriger la demande de certification refusée</button>}
    {saved.invalid && <p role="alert">La demande de certification conservée ne peut pas être lue. Vérifiez son original avant une nouvelle opération.</p>}
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
  </section>;
}
