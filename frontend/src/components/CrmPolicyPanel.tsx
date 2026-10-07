import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validPolicyTerms, validPolicyOriginal, matchesPolicyReceipt, samePolicyOriginal, type PolicyTerms, type PolicyOriginal } from "../crm-policy-utils";

const durations = ["observation_us", "new_customer_us", "at_risk_us", "dormant_us"] as const;
const names = ["Période observée", "Nouvelle cliente pendant", "À risque après", "Inactive après"];
export function durationMicros(value: string, unit: string): number | undefined {
  const m = /^(\d{1,12})(?:[.,](\d{1,6}))?$/.exec(value.trim());
  const factor = unit === "jours" ? 86400000000n : unit === "heures" ? 3600000000n : unit === "secondes" ? 1000000n : 0n;
  if (!m || !factor) return;
  const amount = BigInt(m[1]+(m[2] || ""))*factor/10n**BigInt((m[2] || "").length);
  if (amount > 0n && amount <= BigInt(Number.MAX_SAFE_INTEGER)) return Number(amount);
}
const integer = (s: string) => /^\d{1,16}$/.test(s) && Number.isSafeInteger(Number(s)) && Number(s) > 0 ? Number(s) : 0;
function pendingTerms(v: unknown, institute: string): v is PolicyTerms {
  return validPolicyTerms(v, institute) && Object.keys(v).length === 4 && Object.keys(v.policy).length === 9;
}
export function CrmPolicyPanel({ institute, onChanged }: { institute: string; onChanged?: () => void }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Editor key={JSON.stringify([institute, getAccessToken()])} institute={institute} onChanged={onChanged} />;
}
function Editor({ institute, onChanged }: { institute: string; onChanged?: () => void }) {
  const token = getAccessToken(), actor = getOperatorSubject(), storage = `flowpilot.crm-policy-request:${JSON.stringify([institute, actor])}`;
  const base = `/crm/institutes/${encodeURIComponent(institute)}/segment-policies`;
  const [saved, save] = useState<{ terms?: PolicyTerms; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const value = JSON.parse(raw);
      return pendingTerms(value, institute) ? { terms: value } : { invalid: true }; } catch { return { invalid: true }; }
  });
  const [original, setOriginal] = useState<PolicyOriginal | null>(), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, setRejected] = useState(false);
  const [unit, setUnit] = useState("jours"), [values, setValues] = useState(["", "", "", ""]);
  const [loyal, setLoyal] = useState(""), [vip, setVip] = useState(""), [currency, setCurrency] = useState("");
  const [gross, setGross] = useState(""), [reason, setReason] = useState(""), [predecessor, setPredecessor] = useState<string | null>();
  const mounted = useRef(false), pending = useRef(false), sequence = useRef(0);
  const current = () => mounted.current && token === getAccessToken();
  const frozen = busy || !!saved.terms || !!saved.invalid;
  async function read() {
    const request = ++sequence.current; setLoading(true); setOriginal(undefined);
    try { const v = await apiGet<unknown>(base+"/current");
      if (!current() || request !== sequence.current) return false;
      if (v !== null && !validPolicyOriginal(v, institute)) throw new Error("Politique courante à vérifier.");
      setOriginal(v); return true;
    } catch (e) { if (current() && request === sequence.current) setError(e instanceof Error ? e.message : "Politique indisponible."); return false; }
    finally { if (current() && request === sequence.current) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void read(); return () => { mounted.current = false; sequence.current++; }; }, []);
  async function run(terms: PolicyTerms) {
    if (!current() || pending.current || !actor || saved.invalid || !pendingTerms(terms, institute)) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); setRejected(false);
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/original/${encodeURIComponent(terms.idempotency_key)}`;
      let receipt = await apiGet<unknown>(path); if (!current()) return;
      if (receipt === null) { posting = true; receipt = await apiPost<unknown>(base, terms); returned = true; }
      if (!current()) return;
      if (!validPolicyOriginal(receipt, institute) || !matchesPolicyReceipt(receipt, terms, actor)) throw new Error("Politique originale à vérifier.");
      const verified = await apiGet<unknown>(path); if (!current()) return;
      if (!validPolicyOriginal(verified, institute) || !samePolicyOriginal(receipt, verified)) throw new Error("Original relu à vérifier.");
      if (!await read() || !current()) throw new Error("Relisez la politique courante avant de clore la demande.");
      if (sessionStorage.getItem(storage) !== raw) throw new Error("Demande conservée à vérifier.");
      sessionStorage.removeItem(storage); save({}); setPredecessor(undefined); setSuccess("Politique originale vérifiée et sélection courante relue.");
      onChanged?.();
    } catch (e) { if (current()) { setError(e instanceof Error ? e.message : "Demande à reprendre.");
      setRejected(posting && !returned && e instanceof ApiError && [400, 422].includes(e.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function prepare() {
    if (original === undefined || frozen) return;
    setPredecessor(original?.id || null); setReason(""); setError(undefined); setSuccess(undefined);
    if (original) {
      setUnit("secondes"); setValues(durations.map(k => { const n = BigInt(original.policy[k]); return `${n/1000000n}.${String(n%1000000n).padStart(6,"0")}`; }));
      setLoyal(String(original.policy.loyal_min_tickets)); setVip(String(original.policy.vip_min_tickets)); setCurrency(original.policy.vip_currency);
      const n = BigInt(original.policy.vip_gross_minor); setGross(`${n/100n}.${String(n%100n).padStart(2,"0")}`);
    }
  }
  function submit(e: FormEvent) {
    e.preventDefault(); if (frozen || loading || original === undefined || predecessor === undefined || predecessor !== (original?.id || null) || !actor) return;
    const parsed = values.map(v => durationMicros(v, unit)), m = /^(\d{1,28})(?:[.,](\d{1,2}))?$/.exec(gross.trim());
    const terms = { policy: { institute_id: institute, observation_us: parsed[0], new_customer_us: parsed[1], at_risk_us: parsed[2], dormant_us: parsed[3],
      loyal_min_tickets: integer(loyal), vip_min_tickets: integer(vip), vip_currency: currency,
      vip_gross_minor: m ? String(BigInt(m[1])*100n+BigInt((m[2] || "").padEnd(2,"0"))) : "" },
      previous_policy_id: predecessor, reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!pendingTerms(terms, institute)) { setError("Vérifiez les durées, les seuils ordonnés, la devise et le motif."); return; }
    void run(terms);
  }
  return <section aria-label="Politique CRM" className="customer-crm"><h3>Politique CRM</h3>
    <button disabled={busy || loading} onClick={() => { setError(undefined); void read(); }}>Actualiser la politique</button>
    {loading && <p role="status">Lecture de la politique…</p>}{error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    {original === null && <p>Aucune politique configurée. Aucun seuil commercial n’est appliqué par défaut.</p>}
    {original && <p>Politique enregistrée par {original.actor_id} · motif : {original.reason}</p>}
    {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
    {saved.terms && <><p>Demande conservée · motif : {saved.terms.reason}</p><button disabled={busy} onClick={() => void run(saved.terms!)}>Reprendre la demande CRM conservée</button></>}
    {rejected && <button onClick={() => { sessionStorage.removeItem(storage); save({}); setRejected(false); setPredecessor(undefined); }}>Corriger la demande refusée</button>}
    <button disabled={frozen || loading || original === undefined} onClick={prepare}>{original ? "Préparer une correction" : "Préparer la configuration"}</button>
    {predecessor !== undefined && <form onSubmit={submit}><fieldset disabled={frozen || loading}><legend>Conditions explicites</legend>
      <label>Unité des durées<select value={unit} onChange={e => { setUnit(e.target.value); setValues(["","","",""]); }}><option>jours</option><option>heures</option><option>secondes</option></select></label>
      {names.map((name, i) => <label key={name}>{name}<input required inputMode="decimal" value={values[i]} onChange={e => setValues(old => old.map((v,j) => j === i ? e.target.value : v))} /></label>)}
      <label>Tickets minimum — Fidèle<input required inputMode="numeric" value={loyal} onChange={e => setLoyal(e.target.value)} /></label>
      <label>Tickets minimum — VIP<input required inputMode="numeric" value={vip} onChange={e => setVip(e.target.value)} /></label>
      <label>Devise VIP<select required value={currency} onChange={e => setCurrency(e.target.value)}><option value="">Choisir</option><option>CHF</option><option>EUR</option></select></label>
      <label>Montant connu minimum — VIP<input required inputMode="decimal" value={gross} onChange={e => setGross(e.target.value)} /></label>
      <label>Motif<input required minLength={3} maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <p>À risque doit précéder Inactive, dans la période observée. VIP exige plus de tickets que Fidèle et le montant connu dans la devise choisie.</p>
      <button disabled={!actor || original === undefined || predecessor !== (original?.id || null)}>Enregistrer la politique explicite</button>
    </fieldset></form>}
  </section>;
}
