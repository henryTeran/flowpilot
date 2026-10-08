import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { instituteInstants } from "../institute-calendar";
import { createWaitlistIntent } from "../waitlist-intent";
import { validWaitlistRequest, type WaitlistRequest, type WaitlistEnvelope } from "../waitlist-original-utils";
import type { Customer, Employee, Service } from "../types";
import { CustomerPicker } from "./CustomerPicker";

type Props = { institute: string; timezone?: string; services: Service[]; employees: Employee[]; onRetained?: () => void };
type Clock = { date: string; time: string; occurrence: string };
type WindowDraft = { start: Clock; end: Clock };
const clock = (): Clock => ({ date: "", time: "", occurrence: "" });
const windowDraft = (): WindowDraft => ({ start: clock(), end: clock() });
const intentStorage = { getItem: (key: string) => sessionStorage.getItem(key),
  setItem: (key: string, value: string) => sessionStorage.setItem(key, value), removeItem: (key: string) => sessionStorage.removeItem(key) };
function validZone(zone?: string) {
  if (!zone) return false;
  try { new Intl.DateTimeFormat("fr-CH", { timeZone: zone }); return true; } catch { return false; }
}
function resolveClock(value: Clock, zone: string) {
  const choices = instituteInstants(value.date, value.time, zone);
  return choices.length === 1 ? choices[0] : choices.includes(value.occurrence) ? value.occurrence : undefined;
}
function CivilClock({ label, value, zone, change }: { label: string; value: Clock; zone?: string; change: (value: Clock) => void }) {
  const choices = validZone(zone) ? instituteInstants(value.date, value.time, zone) : [];
  return <div className="revenue-guardian-period">
    <label>{label} — date<input type="date" value={value.date} onChange={e => change({ ...value, date: e.target.value, occurrence: "" })} /></label>
    <label>{label} — heure<input type="time" value={value.time} onChange={e => change({ ...value, time: e.target.value, occurrence: "" })} /></label>
    {choices.length > 1 && <label>{label} — occurrence<select value={value.occurrence} onChange={e => change({ ...value, occurrence: e.target.value })}>
      <option value="">Choisir l’occurrence</option>{choices.map((instant, index) => <option key={instant} value={instant}>{index+1} · {instant}</option>)}</select></label>}
    {!!value.date && !!value.time && choices.length === 0 && <p role="alert">{label} : heure inexistante ou date invalide dans le fuseau de l’institut.</p>}
  </div>;
}
export function WaitlistDemandWriter(props: Props) {
  if (!props.institute || !getOperatorSubject() || getOperatorRole() !== "responsable_institut") return null;
  return <Writer key={JSON.stringify([props.institute, props.timezone, getAccessToken()])} {...props} />;
}
function Writer({ institute, timezone, services, employees, onRetained }: Props) {
  const actor = getOperatorSubject()!, token = getAccessToken(), mounted = useRef(false), pending = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const current = () => mounted.current && token === getAccessToken() && actor === getOperatorSubject() && getOperatorRole() === "responsable_institut";
  const [driver] = useState(() => createWaitlistIntent({ institute, actor, current,
    storage: intentStorage,
    get: path => apiGet(path), post: (path, terms) => apiPost(path, terms) }));
  const [saved, setSaved] = useState(() => driver.state());
  const [customer, setCustomer] = useState<Customer>(), [serviceId, setServiceId] = useState("");
  const [windows, setWindows] = useState<WindowDraft[]>([windowDraft()]);
  const [restriction, setRestriction] = useState(""), [allowed, setAllowed] = useState<string[]>([]);
  const [constraints, setConstraints] = useState(""), [availabilityEvidence, setAvailabilityEvidence] = useState("");
  const [constraintsEvidence, setConstraintsEvidence] = useState(""), [reason, setReason] = useState("");
  const [receipt, setReceipt] = useState<WaitlistEnvelope>(), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const catalog = services.filter(s => s.status === "active" && Number.isSafeInteger(s.duration_min) && s.duration_min > 0 && s.duration_min <= 1440);
  const owned = employees.filter(e => e.institute_id === institute);
  function declaration(): WaitlistRequest {
    const service = catalog.find(s => s.id === serviceId);
    if (!validZone(timezone) || !customer || customer.institute_id !== institute || !service || !["none", "selected"].includes(restriction)
      || restriction === "selected" && (!allowed.length || allowed.some(id => !owned.some(e => e.id === id)))) throw new Error("Incomplete declaration");
    const availability = windows.map(w => ({ start: resolveClock(w.start, timezone!)!, end: resolveClock(w.end, timezone!)! }));
    const terms: WaitlistRequest = { customer_id: customer.id, service_id: service.id, duration_minutes: service.duration_min, availability,
      allowed_employee_ids: restriction === "selected" ? allowed : [], constraints_review: constraints as "confirmed" | "unknown",
      availability_evidence: availabilityEvidence.trim(), constraints_evidence: constraints === "confirmed" ? constraintsEvidence.trim() : null,
      reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validWaitlistRequest(terms) || availability.some(w => Date.parse(w.end) <= Date.now())) throw new Error("Invalid declaration");
    return terms;
  }
  async function act(correct = false) {
    if (!current() || pending.current || receipt) return;
    pending.current = true; setBusy(true); setError(undefined);
    try {
      const state = driver.state();
      const result = correct ? await driver.correct() : await driver.submit(state.status === "empty" ? declaration() : undefined);
      if (!current()) return;
      if (result.status === "confirmed") { setReceipt(result.receipt); onRetained?.(); }
      else if (result.status === "busy") setError("Une vérification est déjà en cours. Reprenez ensuite avec la même clé.");
    } catch {
      if (current()) setError(driver.state().status === "empty"
        ? "Demande non envoyée. Sélectionnez la cliente, la prestation, les restrictions et les contraintes. Vérifiez les fenêtres futures, ordonnées, sans chevauchement, les heures répétées et les preuves d’au moins trois caractères."
        : "Conservation à vérifier. La demande figée reste conservée : reprenez avec la même clé.");
    } finally { pending.current = false; if (current()) { setSaved(driver.state()); setBusy(false); } }
  }
  function reset() { setReceipt(undefined); setCustomer(undefined); setServiceId(""); setWindows([windowDraft()]); setRestriction(""); setAllowed([]);
    setConstraints(""); setAvailabilityEvidence(""); setConstraintsEvidence(""); setReason(""); setError(undefined); }
  function date(value: string) {
    try { return new Intl.DateTimeFormat("fr-CH", { timeZone: timezone || "UTC", dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); } catch { return value; }
  }
  function proof(terms: WaitlistRequest) {
    return <><p>Cliente {terms.customer_id} · prestation {terms.service_id} · durée {terms.duration_minutes} min.</p>
      <ul>{terms.availability.map((w, i) => <li key={i}>Du {date(w.start)} au {date(w.end)}.</li>)}</ul>
      <p>Collaboratrices : {terms.allowed_employee_ids.length ? terms.allowed_employee_ids.join(", ") : "aucune restriction déclarée"}.</p>
      <p>Disponibilité : {terms.availability_evidence}</p><p>Contraintes : {terms.constraints_review === "unknown" ? "inconnues : matching à vérifier" : terms.constraints_evidence}.</p><p>Motif : {terms.reason}</p></>;
  }
  const locked = busy || saved.status !== "empty" || !!receipt;
  return <section className="revenue-guardian-panel waitlist-demand-writer" aria-label="Déclarer une demande de liste d’attente">
    <h2>Déclarer une demande de liste d’attente</h2><p>Conserver les souhaits déclarés de la cliente. L’activation sera une étape explicite distincte ; aucune réservation ni aucun contact n’est effectué ici.</p>
    <p>Dates et heures de l’institut · {validZone(timezone) ? timezone : "fuseau indisponible : nouvelle demande bloquée"}. Fin exclue.</p>
    <fieldset disabled={locked}><legend>Souhaits déclarés</legend>
      {!locked && <CustomerPicker instituteId={institute} selected={customer} clearLabel="Changer de cliente" onSelect={c => { if (current()) setCustomer(c?.institute_id === institute ? c : undefined); }} />}
      <div className="revenue-guardian-period"><label>Prestation demandée<select value={serviceId} onChange={e => setServiceId(e.target.value)}><option value="">Choisir la prestation</option>
        {catalog.map(s => <option key={s.id} value={s.id}>{s.name} · {s.duration_min} min</option>)}</select></label></div>
      {windows.map((w, i) => <div key={i} className="waitlist-window"><h3>Disponibilité {i+1}</h3>
        {(["start", "end"] as const).map(side => <CivilClock key={side} label={`${side === "start" ? "Début" : "Fin"} disponibilité ${i+1}`} value={w[side]} zone={timezone}
          change={value => setWindows(old => old.map((row, index) => index === i ? { ...row, [side]: value } : row))} />)}
        {windows.length > 1 && <button type="button" onClick={() => setWindows(old => old.filter((_, index) => index !== i))}>Retirer disponibilité {i+1}</button>}
      </div>)}
      <div className="revenue-guardian-period"><button type="button" disabled={locked || windows.length >= 64} onClick={() => setWindows(old => [...old, windowDraft()])}>Ajouter une disponibilité</button></div>
      <label>Preuve des disponibilités<textarea value={availabilityEvidence} onChange={e => setAvailabilityEvidence(e.target.value)} /></label>
      <div className="revenue-guardian-period"><label>Restriction de collaboratrices<select value={restriction} onChange={e => { setRestriction(e.target.value); setAllowed([]); }}>
        <option value="">Choisir la restriction</option><option value="none">Aucune restriction déclarée</option><option value="selected">Collaboratrices sélectionnées uniquement</option></select></label></div>
      {restriction === "selected" && <div className="waitlist-employee-choices">{owned.map(e => <label key={e.id}><input type="checkbox" checked={allowed.includes(e.id)}
        onChange={event => setAllowed(old => event.target.checked ? [...old, e.id] : old.filter(id => id !== e.id))} />{e.first_name}</label>)}</div>}
      <div className="revenue-guardian-period"><label>Relecture des contraintes<select value={constraints} onChange={e => { setConstraints(e.target.value); setConstraintsEvidence(""); }}>
        <option value="">Choisir le statut</option><option value="unknown">Contraintes inconnues</option><option value="confirmed">Contraintes relues avec preuve</option></select></label></div>
      {constraints === "confirmed" && <label>Preuve de relecture des contraintes<textarea value={constraintsEvidence} onChange={e => setConstraintsEvidence(e.target.value)} /></label>}
      <label>Motif de la demande<textarea value={reason} onChange={e => setReason(e.target.value)} /></label>
    </fieldset>
    {saved.status === "frozen" && <article><h3>Demande figée à reprendre</h3>{proof(saved.value.terms)}<details><summary>Voir la clé et les termes figés</summary><p>Clé : {saved.value.terms.idempotency_key}</p><pre>{JSON.stringify(saved.value.terms, null, 2)}</pre></details></article>}
    {saved.status === "invalid" && <p role="alert">La demande locale est illisible. Aucune nouvelle demande ne peut être envoyée dans ce contexte.</p>}
    <div className="revenue-guardian-period"><button disabled={busy || saved.status === "invalid" || !!receipt || saved.status === "empty" && !validZone(timezone)} onClick={() => void act()}>
      {saved.status === "frozen" ? "Reprendre la demande par clé" : "Conserver la demande et capturer les sources"}</button>
      {driver.canCorrect() && saved.status === "frozen" && <button disabled={busy} onClick={() => void act(true)}>Vérifier la clé avant correction</button>}</div>
    {busy && <p role="status">Vérification de la conservation…</p>}{error && <p role="alert">{error}</p>}
    {receipt && <article><h3>Demande conservée et relue</h3>{proof({ ...receipt.original.demand, reason: receipt.original.reason, idempotency_key: receipt.original.idempotency_key })}
      <p>Conservée le {date(receipt.original.created_at)} · auteur {receipt.original.actor_id}. Déclaration seule, activation à effectuer.</p>
      <details><summary>Voir l’original et les sources conservées</summary><p>Original {receipt.original.id} · clé {receipt.original.idempotency_key} · empreinte {receipt.fingerprint}.</p><pre>{JSON.stringify(receipt.original, null, 2)}</pre></details></article>}
    {receipt && <div className="revenue-guardian-period"><button onClick={reset}>Déclarer une autre demande</button></div>}
  </section>;
}
