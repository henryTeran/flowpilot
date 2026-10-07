import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validBirthdayPolicyTerms, validBirthdayPolicyOriginal, matchesBirthdayPolicyReceipt, sameBirthdayPolicyOriginal, type BirthdayPolicyTerms, type BirthdayPolicyOriginal } from "../crm-lifecycle-utils";
function pendingTerms(v: unknown,institute: string): v is BirthdayPolicyTerms {
  return validBirthdayPolicyTerms(v,institute) && Object.keys(v).length === 4 && Object.keys(v.policy).length === 3;
}
export function CrmBirthdayPolicyPanel({ institute,onChanged }: { institute: string; onChanged?: () => void }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Editor key={JSON.stringify([institute,getAccessToken()])} institute={institute} onChanged={onChanged} />;
}
function Editor({ institute, onChanged }: { institute: string; onChanged?: () => void }) {
  const token = getAccessToken(), actor = getOperatorSubject(), storage = `flowpilot.crm-birthday-policy-request:${JSON.stringify([institute, actor])}`;
  const base = `/crm/institutes/${encodeURIComponent(institute)}/birthday-calendar-policies`;
  const [saved, save] = useState<{ terms?: BirthdayPolicyTerms; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const value = JSON.parse(raw);
      return pendingTerms(value, institute) ? { terms: value } : { invalid: true }; } catch { return { invalid: true }; }
  });
  const [original, setOriginal] = useState<BirthdayPolicyOriginal | null>(), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, setRejected] = useState(false);
  const [zone, setZone] = useState(""), [leap, setLeap] = useState("");
  const [reason, setReason] = useState(""), [predecessor, setPredecessor] = useState<string | null>();
  const mounted = useRef(false), pending = useRef(false), sequence = useRef(0);
  const current = () => mounted.current && token === getAccessToken();
  const frozen = busy || !!saved.terms || !!saved.invalid;
  async function read() {
    const request = ++sequence.current; setLoading(true); setOriginal(undefined);
    try { const v = await apiGet<unknown>(base+"/current");
      if (!current() || request !== sequence.current) return false;
      if (v !== null && !validBirthdayPolicyOriginal(v, institute)) throw new Error("Politique courante à vérifier.");
      setOriginal(v); return true;
    } catch (e) { if (current() && request === sequence.current) setError(e instanceof Error ? e.message : "Politique indisponible."); return false; }
    finally { if (current() && request === sequence.current) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void read(); return () => { mounted.current = false; sequence.current++; }; }, []);
  async function run(terms: BirthdayPolicyTerms) {
    if (!current() || pending.current || !actor || saved.invalid || !pendingTerms(terms, institute)) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); setRejected(false);
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/original/${encodeURIComponent(terms.idempotency_key)}`;
      let receipt = await apiGet<unknown>(path); if (!current()) return;
      if (receipt === null) { posting = true; receipt = await apiPost<unknown>(base, terms); returned = true; }
      if (!current()) return;
      if (!validBirthdayPolicyOriginal(receipt, institute) || !matchesBirthdayPolicyReceipt(receipt, terms, actor)) throw new Error("Politique originale à vérifier.");
      const verified = await apiGet<unknown>(path); if (!current()) return;
      if (!validBirthdayPolicyOriginal(verified, institute) || !sameBirthdayPolicyOriginal(receipt, verified)) throw new Error("Original relu à vérifier.");
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
    if (original) { setZone(original.policy.timezone); setLeap(original.policy.leap_day); }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    if (frozen || loading || original === undefined || predecessor === undefined || predecessor !== (original?.id || null) || !actor) return;
    const terms = { policy: { institute_id: institute,timezone: zone.trim(),leap_day: leap },
      previous_policy_id: predecessor,reason: reason.trim(),idempotency_key: crypto.randomUUID() };
    if (!pendingTerms(terms,institute)) { setError("Déclarez un fuseau nommé valide, une règle du 29 février et un motif."); return; }
    void run(terms);
  }
  return <section aria-label="Politique anniversaire"><h3>Calendrier anniversaire</h3>
    <p>Le fuseau définit la journée locale. La règle du 29 février est explicite ; aucune règle ni communication n’est appliquée par défaut.</p>
    <button disabled={busy || loading} onClick={() => { setError(undefined); void read(); }}>Actualiser le calendrier anniversaire</button>
    {loading && <p role="status">Lecture du calendrier…</p>}{error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    {original === null && <p>Aucun calendrier anniversaire configuré.</p>}
    {original && <p>Original {original.id} · fuseau {original.policy.timezone} · 29 février : {{ leap_year_only: "années bissextiles uniquement",february_28: "28 février hors année bissextile",march_1: "1er mars hors année bissextile" }[original.policy.leap_day]} · enregistré par {original.actor_id} · motif : {original.reason}</p>}
    {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
    {saved.terms && <><p>Demande conservée · motif : {saved.terms.reason}</p><button disabled={busy} onClick={() => void run(saved.terms!)}>Reprendre le calendrier conservé</button></>}
    {rejected && <button onClick={() => { sessionStorage.removeItem(storage); save({}); setRejected(false); setPredecessor(undefined); }}>Corriger le calendrier refusé</button>}
    <button disabled={frozen || loading || original === undefined} onClick={prepare}>{original ? "Préparer une correction anniversaire" : "Préparer le calendrier anniversaire"}</button>
    {predecessor !== undefined && <form onSubmit={submit}><fieldset disabled={frozen || loading}><legend>Calendrier explicite</legend>
      <label>Fuseau anniversaire<input required maxLength={64} value={zone} placeholder="Europe/Zurich" onChange={e => setZone(e.target.value)} /></label>
      <label>Anniversaire du 29 février<select required value={leap} onChange={e => setLeap(e.target.value)}>
        <option value="">Choisir</option><option value="leap_year_only">Uniquement les années bissextiles</option>
        <option value="february_28">Le 28 février hors année bissextile</option><option value="march_1">Le 1er mars hors année bissextile</option></select></label>
      <label>Motif anniversaire<input required minLength={3} maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button disabled={!actor || original === undefined || predecessor !== (original?.id || null)}>Enregistrer le calendrier anniversaire</button>
    </fieldset></form>}
  </section>;
}
