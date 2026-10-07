import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { instituteSlot } from "../institute-calendar";
import { instituteTimeZone } from "../institute-time";
import { certificationInstant as instant } from "../certification-utils";
import { validCommissionRule, validCommissionRuleIntent, validCommissionRulePage, validRuleCancellation,
  matchesCommissionRule, sameCommissionRuleOriginal, type CommissionRule, type CommissionRulePage, type RuleIntent, type RuleCancellation } from "../commission-utils";
import type { Employee, Service } from "../types";
type Props = { institute: string; timezone?: string; employees: Employee[]; services: Service[] };
const base = (institute: string) => `/workforce/institutes/${encodeURIComponent(institute)}`;
const categoryNames: Record<string, string> = { care: "Soins", product: "Produits", contract: "Contrats", tip: "Pourboires" };
const categoryName = (category: string) => Object.prototype.hasOwnProperty.call(categoryNames, category) ? categoryNames[category] : category;
export function CommissionRulePanel(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Rules key={JSON.stringify([props.institute, instituteTimeZone(props.timezone), getAccessToken()])} {...props} />;
}
function Rules({ institute, timezone, employees, services }: Props) {
  const token = getAccessToken(), actor = getOperatorSubject(), zone = instituteTimeZone(timezone);
  const storage = `flowpilot.commission-rule-request:${JSON.stringify([institute, actor])}`;
  const [saved, save] = useState<{ intent?: RuleIntent; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const value = JSON.parse(raw);
      return validCommissionRuleIntent(value, institute) ? { intent: value } : { invalid: true };
    } catch { return { invalid: true }; }
  });
  const intentEmployee = (intent: RuleIntent) => intent.type === "create" ? intent.terms.employee_id : intent.original.employee_id;
  const [employee, select] = useState(saved.intent ? intentEmployee(saved.intent) : ""), [offset, paginate] = useState(0), [revision, refresh] = useState(0);
  const [page, setPage] = useState<CommissionRulePage>(), [loading, setLoading] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, reject] = useState(false);
  const [title, setTitle] = useState(""), [currency, setCurrency] = useState(""), [category, setCategory] = useState("");
  const [service, setService] = useState(""), [coverage, setCoverage] = useState(""), [rate, setRate] = useState(""), [rounding, setRounding] = useState("");
  const day = instituteSlot(new Date(), zone)?.date || "";
  const [firstDay, setFirstDay] = useState(day), [lastDay, setLastDay] = useState(day), [reason, setReason] = useState("");
  const [cancelling, chooseCancel] = useState<CommissionRule>(), [cancelReason, setCancelReason] = useState("");
  const mounted = useRef(false), pending = useRef(false), scope = useRef(employee), sequence = useRef(0); scope.current = employee;
  const current = () => mounted.current && token === getAccessToken() && scope.current === employee;
  const staff = employees.filter(row => row.institute_id === institute);
  const frozen = busy || !!saved.intent || !!saved.invalid, ready = !!page && page.employee_id === employee && !loading;
  const locked = frozen || !ready || !actor || !staff.some(row => row.id === employee);
  async function read(at = offset) {
    const request = ++sequence.current; setLoading(true); setPage(undefined);
    try {
      const result = await apiGet<CommissionRulePage>(`${base(institute)}/employees/${encodeURIComponent(employee)}/commission-rules?limit=20&offset=${at}`);
      if (!current() || request !== sequence.current) return false;
      if (!validCommissionRulePage(result, institute, employee, at)) throw new Error("Lecture des règles de commission à vérifier.");
      setPage(result); return true;
    } catch (error) { if (current() && request === sequence.current) setError(error instanceof Error ? error.message : "Règles indisponibles."); return false; }
    finally { if (current() && request === sequence.current) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; setPage(undefined); setError(undefined); if (employee) void read();
    return () => { mounted.current = false; sequence.current++; }; }, [employee, offset, revision]);
  async function run(intent: RuleIntent) {
    if (pending.current || !current() || !actor || !ready || saved.invalid || intentEmployee(intent) !== employee || locked && !saved.intent) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); reject(false);
    let posting = false, returned = false;
    try {
      sessionStorage.setItem(storage, JSON.stringify(intent)); save({ intent });
      if (intent.type === "create") {
        const path = `${base(institute)}/commission-rules/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<CommissionRule | null>(path);
        if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<CommissionRule>(`${base(institute)}/commission-rules`, intent.terms); returned = true; }
        if (!current()) return;
        if (!validCommissionRule(original, institute, employee) || !matchesCommissionRule(original, intent.terms, actor)) throw new Error("Règle originale à vérifier.");
        const verified = await apiGet<CommissionRule | null>(path);
        if (!current()) return;
        if (!validCommissionRule(verified, institute, employee) || !sameCommissionRuleOriginal(original, verified)) throw new Error("Lecture originale de la règle à vérifier.");
      } else {
        const path = `${base(institute)}/commission-rule-cancellations/original/${encodeURIComponent(intent.terms.idempotency_key)}`;
        let original = await apiGet<RuleCancellation | null>(path);
        if (!current()) return;
        if (original === null) { posting = true; original = await apiPost<RuleCancellation>(`${base(institute)}/commission-rules/${encodeURIComponent(intent.original.id)}/cancel`, intent.terms); returned = true; }
        if (!current()) return;
        const matches = (c: RuleCancellation) => c.actor_id === actor && c.rule_id === intent.original.id && c.reason === intent.terms.reason && c.idempotency_key === intent.terms.idempotency_key;
        if (!validRuleCancellation(original, institute, intent.original.id) || !matches(original)) throw new Error("Annulation originale à vérifier.");
        const verified = await apiGet<CommissionRule>(`${base(institute)}/commission-rules/${encodeURIComponent(intent.original.id)}`);
        if (!current()) return;
        if (!validCommissionRule(verified, institute, employee) || !sameCommissionRuleOriginal(intent.original, verified) || !verified.cancellation
          || verified.cancellation.id !== original.id || instant(verified.cancellation.created_at) !== instant(original.created_at) || !matches(verified.cancellation)) throw new Error("Lecture originale de l’annulation à vérifier.");
      }
      if (!await read() || !current()) throw new Error("Relisez les règles avant de poursuivre.");
      sessionStorage.removeItem(storage); save({}); chooseCancel(undefined); setReason(""); setCancelReason("");
      if (intent.type === "create") { setTitle(""); setRate(""); }
      setSuccess(intent.type === "create" ? "Règle de commission enregistrée." : "Règle annulée ; commissions déjà enregistrées conservées.");
    } catch (error) { if (current()) { setError(error instanceof Error ? error.message : "Règles indisponibles."); reject(posting && !returned && error instanceof ApiError && [400, 422].includes(error.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function submit(event: FormEvent) {
    event.preventDefault(); if (locked) return;
    const match = /^(\d{1,3})(?:[.,](\d{1,2}))?$/.exec(rate.trim());
    const points = match ? Number(match[1])*100+Number((match[2] || "").padEnd(2, "0")) : -1;
    const intent = { type: "create", terms: { employee_id: employee, title: title.trim(), basis: "closed_attributed_line_gross", currency,
      category, service_id: coverage === "all" ? null : service, rate_basis_points: points, rounding, first_day: firstDay, last_day: lastDay,
      reason: reason.trim(), idempotency_key: crypto.randomUUID() } };
    if (!["all", "named"].includes(coverage) || coverage === "named" && !services.some(s => s.id === service) || !validCommissionRuleIntent(intent, institute)) {
      setError("Choisissez la devise, la catégorie, les prestations et l’arrondi ; indiquez un taux de 0 à 100 % et la période incluse."); return;
    } void run(intent);
  }
  return <section className="workforce-panel absence-panel commission-rule-panel" aria-label="Gestion des règles de commission">
    <h2>Règles de commission</h2><p>Calcul sur le montant brut complet de chaque ligne clôturée attribuée à la collaboratrice. Les règles peuvent se chevaucher ; une ligne ne peut recevoir qu’une commission non annulée.</p>
    <label>Collaboratrice des commissions<select disabled={frozen} value={employee} onChange={event => { select(event.target.value); paginate(0); setPage(undefined); chooseCancel(undefined); setSuccess(undefined); }}>
      <option value="">Choisir une collaboratrice</option>{staff.map(row => <option key={row.id} value={row.id}>{row.first_name}</option>)}</select></label>
    {employee && <section aria-label="Historique des règles de commission"><header><h3>Règles enregistrées</h3><button disabled={busy || loading} onClick={() => refresh(v => v+1)}>Actualiser les règles</button></header>
      {loading && <p role="status">Lecture des règles…</p>}{page && <><p>{page.page.total} règles enregistrées · lecture : {page.generated_at}</p>
        {!page.page.total && <p>Aucune règle enregistrée pour cette collaboratrice.</p>}
        <ul className="absence-list">{page.rows.map(r => <li key={r.id}><strong>{r.title}</strong><p>{r.rate_basis_points/100} % · {r.currency} · catégorie : {categoryName(r.category)} · {r.service_id === null ? "Toutes les prestations de la catégorie" : services.find(s => s.id === r.service_id)?.name || "Prestation conservée dans l’original"}</p>
          <p>Du {r.first_day} au {r.last_day} inclus · {r.timezone} · arrondi : {r.rounding === "half_up" ? "Demi-cent vers le haut" : r.rounding === "half_even" ? "Demi-cent vers le cent pair" : "Cent inférieur"}</p>
          <p>{r.cancellation ? `Annulée : ${r.cancellation.reason}` : instant(r.created_at)! > instant(page.generated_at)! ? "Enregistrement daté après la lecture" : "Règle conservée"}</p>
          {!r.cancellation && <button disabled={locked} onClick={() => { chooseCancel(r); setCancelReason(""); }}>Annuler cette règle</button>}
          <details><summary>Provenance de la règle</summary><p>Original {r.id} · acteur {r.actor_id} · motif : {r.reason}</p><p>Enregistré : {r.created_at} · période UTC : {r.period_start} → {r.period_end}, fin exclue.</p>
            {r.cancellation && <p>Annulation {r.cancellation.id} · acteur {r.cancellation.actor_id} · enregistrée : {r.cancellation.created_at}</p>}</details></li>)}</ul>
        <div className="workforce-pages"><span>Règles : {page.rows.length ? offset+1 : 0}–{offset+page.rows.length} / {page.page.total}</span>
          <button disabled={frozen || loading || !offset} onClick={() => paginate(offset-20)}>Règles précédentes</button><button disabled={frozen || loading || offset+20 >= page.page.total} onClick={() => paginate(offset+20)}>Règles suivantes</button></div></>}
    </section>}
    <form aria-label="Enregistrer une règle de commission" onSubmit={submit}><h3>Nouvelle règle</h3><p>Les nouveaux jours sont interprétés dans le fuseau {zone}. Les commissions enregistrées ne constituent pas un total à payer.</p><fieldset disabled={locked}>
      <label>Intitulé de la règle<input required maxLength={120} value={title} onChange={event => setTitle(event.target.value)} /></label>
      <label>Devise de la règle<select required value={currency} onChange={event => setCurrency(event.target.value)}><option value="">Choisir une devise</option><option>CHF</option><option>EUR</option></select></label>
      <label>Catégorie de la règle<select required value={category} onChange={event => setCategory(event.target.value)}><option value="">Choisir une catégorie</option><option value="care">Soins</option><option value="product">Produits</option><option value="contract">Contrats</option><option value="tip">Pourboires</option></select></label>
      <label>Prestations couvertes<select required value={coverage} onChange={event => setCoverage(event.target.value)}><option value="">Choisir le périmètre</option><option value="all">Toutes les prestations de la catégorie</option><option value="named">Une prestation du catalogue</option></select></label>
      {coverage === "named" && <label>Prestation de la règle<select required value={service} onChange={event => setService(event.target.value)}><option value="">Choisir une prestation</option>{services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>}
      <label>Taux de commission (%)<input required inputMode="decimal" maxLength={6} value={rate} onChange={event => setRate(event.target.value)} /></label>
      <label>Arrondi au cent<select required value={rounding} onChange={event => setRounding(event.target.value)}><option value="">Choisir un arrondi</option><option value="half_up">Demi-cent vers le haut</option><option value="half_even">Demi-cent vers le cent pair</option><option value="down">Cent inférieur</option></select></label>
      <label>Premier jour inclus<input type="date" required value={firstDay} onChange={event => setFirstDay(event.target.value)} /></label><label>Dernier jour inclus<input type="date" required value={lastDay} onChange={event => setLastDay(event.target.value)} /></label>
      <label>Motif de la règle<input required maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label><button type="submit">Enregistrer la règle</button>
    </fieldset></form>
    {cancelling && <form aria-label="Annuler la règle sélectionnée" onSubmit={event => { event.preventDefault(); if (locked) return;
      const intent: RuleIntent = { type: "cancel", original: cancelling, terms: { reason: cancelReason.trim(), idempotency_key: crypto.randomUUID() } };
      if (!validCommissionRuleIntent(intent, institute)) { setError("Un motif d’annulation valide est requis."); return; } void run(intent); }}>
      <h3>Annuler : {cancelling.title}</h3><p>L’annulation empêche de nouvelles commissions avec cette règle. Elle conserve les commissions déjà enregistrées.</p><fieldset disabled={locked}>
        <label>Motif d’annulation de la règle<input required maxLength={240} value={cancelReason} onChange={event => setCancelReason(event.target.value)} /></label>
        <button type="submit">Confirmer l’annulation de la règle</button><button type="button" onClick={() => chooseCancel(undefined)}>Fermer l’annulation</button></fieldset></form>}
    {saved.intent && <><p>Demande de règle conservée pour {staff.find(row => row.id === employee)?.first_name || employee}.</p><p>{saved.intent.type === "create" ? `${saved.intent.terms.title} · ${saved.intent.terms.rate_basis_points/100} % · ${saved.intent.terms.currency} · ${saved.intent.terms.first_day} → ${saved.intent.terms.last_day}` : `Annulation : ${saved.intent.original.title} · ${saved.intent.terms.reason}`}</p>
      <button disabled={busy || !ready || !actor} onClick={() => void run(saved.intent!)}>Reprendre la demande de règle conservée</button></>}
    {rejected && saved.intent && <button disabled={busy} onClick={() => { try { sessionStorage.removeItem(storage); save({}); reject(false); setError(undefined); } catch (error) { setError(String(error)); } }}>Corriger la demande de règle refusée</button>}
    {saved.invalid && <p role="alert">La demande de règle conservée ne peut pas être lue. Vérifiez son original avant une nouvelle opération.</p>}
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
  </section>;
}
