import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validLifetimeTerms, validLifetimeOriginal, matchesLifetimeReceipt, sameLifetimeOriginal, type LifetimeTerms, type LifetimeOriginal } from "../crm-lifetime-utils";

function pendingTerms(v: unknown, institute: string, customer: string): v is LifetimeTerms {
  return validLifetimeTerms(v,institute,customer) && Object.keys(v).length === 4 && Object.keys(v.assumptions).length === 8
    && Object.keys(v.assumptions.activity_fraction).length === 2 && Object.keys(v.assumptions.gross_contribution_margin).length === 2;
}
export function lifetimeDuration(value: string, unit: string): string | undefined {
  const m = /^(\d{1,24})(?:[.,](\d{1,6}))?$/.exec(value.trim());
  const factor = unit === "jours" ? 86400000000n : unit === "heures" ? 3600000000n : unit === "secondes" ? 1000000n : 0n;
  if (!m || !factor) return;
  const result = BigInt(m[1]+(m[2] || ""))*factor/10n**BigInt((m[2] || "").length);
  if (result > 0n && String(result).length <= 30) return String(result);
}
export function CrmLifetimeEditor(props: { institute: string; customer: string; onChanged?: () => void }) {
  if (!props.institute || !props.customer || getOperatorRole() !== "responsable_institut") return null;
  return <Editor key={JSON.stringify([props.institute,props.customer,getAccessToken()])} {...props} />;
}
function Editor({ institute, customer, onChanged }: { institute: string; customer: string; onChanged?: () => void }) {
  const token = getAccessToken(), actor = getOperatorSubject(), storage = `flowpilot.crm-lifetime-request:${JSON.stringify([institute, customer, actor])}`;
  const base = `/crm/institutes/${encodeURIComponent(institute)}/customers/${encodeURIComponent(customer)}/lifetime-assumptions`;
  const [saved, save] = useState<{ terms?: LifetimeTerms; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const value = JSON.parse(raw);
      return pendingTerms(value, institute, customer) ? { terms: value } : { invalid: true }; } catch { return { invalid: true }; }
  });
  const [original, setOriginal] = useState<LifetimeOriginal | null>(), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, setRejected] = useState(false);
  const [unit, setUnit] = useState("jours"), [duration, setDuration] = useState("");
  const [activity, setActivity] = useState(["", ""]), [margin, setMargin] = useState(["", ""]);
  const [currency, setCurrency] = useState(""), [cost, setCost] = useState(""), [reason, setReason] = useState("");
  const [predecessor, setPredecessor] = useState<string | null>();
  const mounted = useRef(false), pending = useRef(false), sequence = useRef(0);
  const current = () => mounted.current && token === getAccessToken();
  const frozen = busy || !!saved.terms || !!saved.invalid;
  async function read() {
    const request = ++sequence.current; setLoading(true); setOriginal(undefined);
    try { const v = await apiGet<unknown>(base+"/current");
      if (!current() || request !== sequence.current) return false;
      if (v !== null && !validLifetimeOriginal(v, institute, customer)) throw new Error("Hypothèses CLV courantes à vérifier.");
      setOriginal(v); return true;
    } catch (e) { if (current() && request === sequence.current) setError(e instanceof Error ? e.message : "Hypotheses CLV indisponible."); return false; }
    finally { if (current() && request === sequence.current) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void read(); return () => { mounted.current = false; sequence.current++; }; }, []);
  async function run(terms: LifetimeTerms) {
    if (!current() || pending.current || !actor || saved.invalid || !pendingTerms(terms, institute, customer)) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); setRejected(false);
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/original/${encodeURIComponent(terms.idempotency_key)}`;
      let receipt = await apiGet<unknown>(path); if (!current()) return;
      if (receipt === null) { posting = true; receipt = await apiPost<unknown>(base, terms); returned = true; }
      if (!current()) return;
      if (!validLifetimeOriginal(receipt, institute, customer) || !matchesLifetimeReceipt(receipt, terms, actor)) throw new Error("Hypothèses CLV originales à vérifier.");
      const verified = await apiGet<unknown>(path); if (!current()) return;
      if (!validLifetimeOriginal(verified, institute, customer) || !sameLifetimeOriginal(receipt, verified)) throw new Error("Original relu à vérifier.");
      if (!await read() || !current()) throw new Error("Relisez les hypothèses CLV courantes avant de clore la demande.");
      if (sessionStorage.getItem(storage) !== raw) throw new Error("Demande conservée à vérifier.");
      sessionStorage.removeItem(storage); save({}); setPredecessor(undefined); setSuccess("Hypothèses CLV originales vérifiées et sélection courante relue.");
      onChanged?.();
    } catch (e) { if (current()) { setError(e instanceof Error ? e.message : "Demande à reprendre.");
      setRejected(posting && !returned && e instanceof ApiError && [400, 422].includes(e.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function prepare() {
    if (original === undefined || frozen) return;
    setPredecessor(original?.id || null); setReason(""); setError(undefined); setSuccess(undefined);
    if (original) {
      const a = original.assumptions, n = BigInt(a.expected_active_us), c = BigInt(a.future_relationship_cost_minor);
      setUnit("secondes"); setDuration(`${n/1000000n}.${String(n%1000000n).padStart(6,"0")}`);
      setActivity([a.activity_fraction.numerator,a.activity_fraction.denominator]);
      setMargin([a.gross_contribution_margin.numerator,a.gross_contribution_margin.denominator]);
      setCurrency(a.currency); setCost(`${c/100n}.${String(c%100n).padStart(2,"0")}`);
    }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    if (frozen || loading || original === undefined || predecessor === undefined || predecessor !== (original?.id || null) || !actor) return;
    const m = /^(\d{1,28})(?:[.,](\d{1,2}))?$/.exec(cost.trim());
    const terms = { assumptions: { institute_id: institute,customer_id: customer,
      model: "constant_observed_rate_finite_remaining_lifetime_undiscounted_v1",currency,expected_active_us: lifetimeDuration(duration,unit),
      activity_fraction: { numerator: activity[0].trim(),denominator: activity[1].trim() },
      gross_contribution_margin: { numerator: margin[0].trim(),denominator: margin[1].trim() },
      future_relationship_cost_minor: m ? String(BigInt(m[1])*100n+BigInt((m[2] || "").padEnd(2,"0"))) : "" },
      previous_id: predecessor,reason: reason.trim(),idempotency_key: crypto.randomUUID() };
    if (!pendingTerms(terms,institute,customer)) { setError("Vérifiez la durée positive, les parts entre zéro et un, la devise, les coûts et le motif."); return; }
    void run(terms);
  }
  return <section aria-label="Hypothèses CLV"><h4>Hypothèses de valeur restante</h4>
    <p>Scénario à rythme observé constant, sans actualisation. Déclarez la durée d’activité attendue, la part d’activité conservée, la marge sur montant brut et les coûts futurs. Ces hypothèses ne sont pas une prédiction validée.</p>
    <button disabled={busy || loading} onClick={() => { setError(undefined); void read(); }}>Actualiser les hypothèses CLV</button>
    {loading && <p role="status">Lecture des hypothèses…</p>}{error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    {original === null && <p>Aucune hypothèse configurée. Aucun montant futur n’est calculé par défaut.</p>}
    {original && <p>Original {original.id} · enregistré par {original.actor_id} · motif : {original.reason}</p>}
    {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
    {saved.terms && <><p>Demande conservée · motif : {saved.terms.reason}</p><button disabled={busy} onClick={() => void run(saved.terms!)}>Reprendre la demande CLV conservée</button></>}
    {rejected && <button onClick={() => { sessionStorage.removeItem(storage); save({}); setRejected(false); setPredecessor(undefined); }}>Corriger la demande CLV refusée</button>}
    <button disabled={frozen || loading || original === undefined} onClick={prepare}>{original ? "Préparer une correction CLV" : "Préparer les hypothèses CLV"}</button>
    {predecessor !== undefined && <form onSubmit={submit}><fieldset disabled={frozen || loading}><legend>Hypothèses explicites</legend>
      <label>Unité de durée CLV<select value={unit} onChange={e => { setUnit(e.target.value); setDuration(""); }}><option>jours</option><option>heures</option><option>secondes</option></select></label>
      <label>Durée d’activité attendue<input required inputMode="decimal" value={duration} onChange={e => setDuration(e.target.value)} /></label>
      {[{ label: "Activité conservée",values: activity,set: setActivity },{ label: "Marge sur montant brut",values: margin,set: setMargin }].map(f => <div key={f.label}>
        <label>{f.label} — parts retenues<input required inputMode="numeric" value={f.values[0]} onChange={e => f.set([e.target.value,f.values[1]])} /></label>
        <label>{f.label} — sur<input required inputMode="numeric" value={f.values[1]} onChange={e => f.set([f.values[0],e.target.value])} /></label></div>)}
      <p>Par exemple, 1 sur 2 représente la moitié. Les parts retenues doivent être comprises entre zéro et le total ; le total doit être positif.</p>
      <label>Devise CLV<select required value={currency} onChange={e => setCurrency(e.target.value)}><option value="">Choisir</option><option>CHF</option><option>EUR</option></select></label>
      <label>Coûts futurs de relation cliente<input required inputMode="decimal" value={cost} onChange={e => setCost(e.target.value)} /></label>
      <label>Motif CLV<input required minLength={3} maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button disabled={!actor || original === undefined || predecessor !== (original?.id || null)}>Enregistrer les hypothèses CLV</button>
    </fieldset></form>}
  </section>;
}
