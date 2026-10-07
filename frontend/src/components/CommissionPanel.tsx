import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { instituteBoundary, instituteSlot } from "../institute-calendar";
import { instituteTimeZone } from "../institute-time";
import { certificationInstant as instant } from "../certification-utils";
import { validCommission, validCommissionCancellation, validCommissionIntent, validCommissionPage, validCommissionRulePage,
  matchesCommission, sameCommissionOriginal, validCommissionRule, type CommissionRule, type Commission, type CommissionCancellation, type CommissionIntent,
  type CommissionCalculation, type CommissionPage, type CommissionRulePage } from "../commission-utils";
import { CommissionChoices } from "./CommissionChoices";
import { commissionAmount } from "./EmployeeCommissionPanel";
import type { Employee, Service } from "../types";
type Props = { institute: string; timezone?: string; employees: Employee[]; services: Service[] };
const base = (institute: string) => `/workforce/institutes/${encodeURIComponent(institute)}`;
export function CommissionPanel(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Ledger key={JSON.stringify([props.institute, instituteTimeZone(props.timezone), getAccessToken()])} {...props} />;
}
function Ledger({ institute, timezone, employees, services }: Props) {
  const token = getAccessToken(), actor = getOperatorSubject(), zone = instituteTimeZone(timezone), storage = `flowpilot.commission-request:${JSON.stringify([institute, actor])}`;
  const [saved, save] = useState<{ intent?: CommissionIntent; employee?: string; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const value = JSON.parse(raw);
      return typeof value.employee_id === "string" && !!value.employee_id && value.employee_id.trim() === value.employee_id && value.employee_id.length <= 80
        && validCommissionIntent(value.intent, institute) && (value.intent.type === "create" || value.intent.original.employee_id === value.employee_id)
        ? { intent: value.intent, employee: value.employee_id } : { invalid: true };
    } catch { return { invalid: true }; }
  });
  const [employee, select] = useState(saved.employee || ""), [offset, paginate] = useState(0), [ruleOffset, rulePaginate] = useState(0), [revision, refresh] = useState(0);
  const [history, setPage] = useState<CommissionPage>(), [policies, setRules] = useState<CommissionRulePage>(), [ruleId, chooseRule] = useState("");
  const [day, chooseDay] = useState(instituteSlot(new Date(), zone)?.date || ""), [selection, chooseSelection] = useState<CommissionCalculation>();
  const [loading, setLoading] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [success, setSuccess] = useState<string>();
  const [reason, setReason] = useState(""), [cancelling, chooseCancel] = useState<Commission>(), [cancelReason, setCancelReason] = useState(""), [rejected, reject] = useState(false);
  const mounted = useRef(false), pending = useRef(false), scope = useRef(employee), sequence = useRef(0); scope.current = employee;
  const current = () => mounted.current && token === getAccessToken() && scope.current === employee;
  const page = history?.employee_id === employee && history.page.offset === offset ? history : undefined;
  const rules = policies?.employee_id === employee && policies.page.offset === ruleOffset ? policies : undefined;
  const staff = employees.filter(e => e.institute_id === institute), frozen = busy || !!saved.intent || !!saved.invalid, ready = !!page && !!rules && !loading;
  const locked = frozen || !ready || !actor || !staff.some(e => e.id === employee), rule = rules?.rows.find(r => r.id === ruleId);
  const nextDay = /^\d{4}-\d{2}-\d{2}$/.test(day) && Number.isFinite(Date.parse(`${day}T12:00:00Z`)) ? new Date(Date.parse(`${day}T12:00:00Z`)+86400000).toISOString().slice(0, 10) : "";
  const from = instituteBoundary(day, 0, zone) ?? instituteBoundary(nextDay, 0, zone), until = instituteBoundary(nextDay, 0, zone);
  const start = from === undefined ? "" : new Date(from).toISOString(), end = until === undefined ? "" : new Date(until).toISOString();
  async function read() {
    const request = ++sequence.current; setLoading(true); setPage(undefined); setRules(undefined); chooseRule(""); chooseSelection(undefined);
    try {
      const [history, policies] = await Promise.all([
        apiGet<CommissionPage>(`${base(institute)}/employees/${encodeURIComponent(employee)}/commissions?limit=20&offset=${offset}`),
        apiGet<CommissionRulePage>(`${base(institute)}/employees/${encodeURIComponent(employee)}/commission-rules?limit=20&offset=${ruleOffset}`)]);
      if (!current() || request !== sequence.current) return false;
      if (!validCommissionPage(history, institute, employee, offset) || !validCommissionRulePage(policies, institute, employee, ruleOffset)) throw new Error("Lecture des commissions et règles à vérifier.");
      setPage(history); setRules(policies); return true;
    } catch (error) { if (current() && request === sequence.current) setError(error instanceof Error ? error.message : "Commissions indisponibles."); return false; }
    finally { if (current() && request === sequence.current) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; setError(undefined); setPage(undefined); setRules(undefined); if (employee) void read();
    return () => { mounted.current = false; sequence.current++; }; }, [employee, offset, ruleOffset, revision]);
  async function run(intent: CommissionIntent) {
    if (pending.current || !current() || !actor || !ready || saved.invalid || locked && !saved.intent
      || intent.type === "cancel" && intent.original.employee_id !== employee) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); reject(false);
    let posting = false, returned = false;
    try {
      sessionStorage.setItem(storage, JSON.stringify({ employee_id: employee, intent })); save({ intent, employee });
      if (intent.type === "create") {
        const path = `${base(institute)}/commissions/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<Commission | null>(path);
        if (!current()) return;
        if (original === null) {
          const policy = await apiGet<CommissionRule>(`${base(institute)}/commission-rules/${encodeURIComponent(intent.terms.rule_id)}`);
          if (!current()) return;
          if (!validCommissionRule(policy, institute, employee)) throw new Error("Périmètre original de la règle à vérifier.");
          posting = true; original = await apiPost<Commission>(`${base(institute)}/commissions`, intent.terms); returned = true;
        }
        if (!current()) return;
        if (!validCommission(original, institute, employee) || !matchesCommission(original, intent.terms, actor)) throw new Error("Commission originale à vérifier.");
        const verified = await apiGet<Commission | null>(path);
        if (!current()) return;
        if (!validCommission(verified, institute, employee) || !sameCommissionOriginal(original, verified)) throw new Error("Lecture originale de la commission à vérifier.");
      } else {
        const path = `${base(institute)}/commission-cancellations/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<CommissionCancellation | null>(path);
        if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<CommissionCancellation>(`${base(institute)}/commissions/${encodeURIComponent(intent.original.id)}/cancel`, intent.terms); returned = true; }
        if (!current()) return;
        const matches = (c: CommissionCancellation) => c.actor_id === actor && c.commission_id === intent.original.id && c.reason === intent.terms.reason && c.idempotency_key === intent.terms.idempotency_key;
        if (!validCommissionCancellation(original, institute, intent.original.id) || !matches(original)) throw new Error("Annulation originale à vérifier.");
        const verified = await apiGet<Commission>(`${base(institute)}/commissions/${encodeURIComponent(intent.original.id)}`);
        if (!current()) return;
        if (!validCommission(verified, institute, employee) || !sameCommissionOriginal(verified, intent.original) || !verified.cancellation
          || verified.cancellation.id !== original.id || instant(verified.cancellation.created_at) !== instant(original.created_at) || !matches(verified.cancellation)) throw new Error("Lecture originale de l’annulation à vérifier.");
      }
      if (!await read() || !current()) throw new Error("Relisez les commissions avant de poursuivre.");
      sessionStorage.removeItem(storage); save({}); chooseCancel(undefined); setReason(""); setCancelReason("");
      setSuccess(intent.type === "create" ? "Commission enregistrée." : "Commission annulée ; original conservé.");
    } catch (error) { if (current()) { setError(error instanceof Error ? error.message : "Commissions indisponibles."); reject(posting && !returned && error instanceof ApiError && [400, 422].includes(error.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  return <section className="workforce-panel absence-panel commission-panel" aria-label="Gestion des commissions">
    <h2>Commissions</h2><p>Déclarations explicites sur les lignes clôturées attribuées à la collaboratrice. Les droits complets et le total à payer restent inconnus.</p>
    <label>Collaboratrice des déclarations de commission<select disabled={frozen} value={employee} onChange={event => { select(event.target.value); paginate(0); rulePaginate(0); setPage(undefined); setRules(undefined); chooseSelection(undefined); chooseCancel(undefined); setSuccess(undefined); }}>
      <option value="">Choisir une collaboratrice</option>{staff.map(e => <option key={e.id} value={e.id}>{e.first_name}</option>)}</select></label>
    {employee && <button disabled={busy || loading} onClick={() => refresh(v => v+1)}>Actualiser le journal des commissions</button>}
    {loading && <p role="status">Lecture du journal et des règles…</p>}
    <form aria-label="Déclarer une commission" onSubmit={event => { event.preventDefault(); if (locked || !selection || !rule || selection.terms.employee_id !== employee) return;
      const intent: CommissionIntent = { type: "create", terms: { rule_id: rule.id, line_id: selection.source.line_id, reason: reason.trim(), idempotency_key: crypto.randomUUID() } };
      if (!validCommissionIntent(intent, institute)) { setError("Un motif valide est requis."); return; } void run(intent); }}><h3>Nouvelle commission</h3>
      <fieldset disabled={locked}><label>Règle de la commission<select required value={ruleId} onChange={event => { chooseRule(event.target.value); chooseSelection(undefined); }}>
        <option value="">Choisir une règle</option>{rules?.rows.map(r => <option key={r.id} value={r.id} disabled={!!r.cancellation || instant(r.created_at)! > instant(rules.generated_at)!}>{r.title} · {r.rate_basis_points/100} % · {r.currency}{r.cancellation ? " · Annulée" : ""}</option>)}</select></label>
        <label>Jour de clôture des sources<input type="date" required value={day} onChange={event => { chooseDay(event.target.value); chooseSelection(undefined); }} /></label>
        <label>Motif de la commission<input required maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label></fieldset>
      {rules && <div className="workforce-pages"><span>Règles : {rules.rows.length ? ruleOffset+1 : 0}–{ruleOffset+rules.rows.length} / {rules.page.total}</span><button type="button" disabled={frozen || loading || !ruleOffset} onClick={() => rulePaginate(ruleOffset-20)}>Choix de règles précédents</button><button type="button" disabled={frozen || loading || ruleOffset+20 >= rules.page.total} onClick={() => rulePaginate(ruleOffset+20)}>Choix de règles suivants</button></div>}
      {rule && start && end && <CommissionChoices institute={institute} rule={rule} day={day} start={start} end={end} timezone={zone} services={services} disabled={locked} onSelection={chooseSelection} />}
      <button type="submit" disabled={locked || !selection}>Enregistrer la commission</button>
    </form>
    {page && <><h3>Journal des originaux</h3><p>{page.page.total} commissions · lecture : {page.generated_at}</p><ul className="absence-list">{page.rows.map(o => <li key={o.id}><strong>{commissionAmount(o.calculation.amount_minor, o.calculation.source.currency)} · {o.rule_capture.title}</strong><p>{o.cancellation ? `Annulée : ${o.cancellation.reason}` : instant(o.created_at)! > instant(page.generated_at)! ? "Enregistrement daté après la lecture" : "Commission enregistrée"}</p>
      {!o.cancellation && <button disabled={locked} onClick={() => { chooseCancel(o); setCancelReason(""); }}>Annuler cette commission</button>}
      <details><summary>Provenance de la commission</summary><p>Original {o.id} · règle {o.rule_id} · ticket {o.ticket_id} · ligne {o.line_id}</p><p>Enregistré : {o.created_at} · acteur {o.actor_id} · motif : {o.reason}</p><p>Clôture originale : {o.calculation.source.paid_at} · brut : {commissionAmount(o.calculation.source.gross_minor, o.calculation.source.currency)} · quantité déjà incluse : {o.calculation.source.quantity}</p>
        <p>Règle originale : {o.rule_capture.first_day} → {o.rule_capture.last_day} inclus · {o.rule_capture.timezone} · {o.rule_capture.period_start} → {o.rule_capture.period_end}, fin exclue.</p>
        {o.cancellation && <p>Annulation {o.cancellation.id} · {o.cancellation.created_at} · acteur {o.cancellation.actor_id}</p>}</details></li>)}</ul>
      <div className="workforce-pages"><span>Commissions : {page.rows.length ? offset+1 : 0}–{offset+page.rows.length} / {page.page.total}</span><button disabled={frozen || loading || !offset} onClick={() => paginate(offset-20)}>Journal précédent</button><button disabled={frozen || loading || offset+20 >= page.page.total} onClick={() => paginate(offset+20)}>Journal suivant</button></div></>}
    {cancelling && <form aria-label="Annuler la commission sélectionnée" onSubmit={event => { event.preventDefault(); if (locked) return;
      const intent: CommissionIntent = { type: "cancel", original: cancelling, terms: { reason: cancelReason.trim(), idempotency_key: crypto.randomUUID() } };
      if (!validCommissionIntent(intent, institute)) { setError("Un motif d’annulation valide est requis."); return; } void run(intent); }}><h3>Annuler la commission</h3><fieldset disabled={locked}>
      <label>Motif d’annulation de la commission<input required maxLength={240} value={cancelReason} onChange={event => setCancelReason(event.target.value)} /></label><button type="submit">Confirmer l’annulation de la commission</button><button type="button" onClick={() => chooseCancel(undefined)}>Fermer l’annulation</button></fieldset></form>}
    {saved.intent && <><p>Demande de commission conservée pour {staff.find(e => e.id === employee)?.first_name || employee}.</p><p>{saved.intent.type === "create" ? "Déclaration" : "Annulation"} · motif : {saved.intent.terms.reason}</p><button disabled={busy || !ready || !actor} onClick={() => void run(saved.intent!)}>Reprendre la demande de commission conservée</button></>}
    {rejected && saved.intent && <button disabled={busy} onClick={() => { try { sessionStorage.removeItem(storage); save({}); reject(false); setError(undefined); } catch (error) { setError(String(error)); } }}>Corriger la demande de commission refusée</button>}
    {saved.invalid && <p role="alert">La demande conservée ne peut pas être lue. Vérifiez son original avant une nouvelle opération.</p>}
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
  </section>;
}
