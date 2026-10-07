import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { automationTriggers, type AutomationTrigger, validAutomationTerms, validAutomationOriginal, matchesAutomationReceipt, sameAutomationOriginal, type AutomationTerms, type AutomationOriginal } from "../crm-automation-utils";
const labels: Record<AutomationTrigger,string> = { birthday:"Anniversaire",post_service:"Suivi de soin",rebooking:"Rebooking",inactivity:"Inactivité",package_expiry:"Expiration package",subscription_renewal:"Renouvellement abonnement" };
export function automationSeconds(us: string) {
  const n=BigInt(us),fraction=String(n%1000000n).padStart(6,"0").replace(/0+$/,"");
  return `${n/1000000n}${fraction ? "."+fraction : ""}`;
}
export function automationMicroseconds(seconds: string): string | undefined {
  if (seconds.length>19 || seconds.trim()!==seconds || !/^(0|[1-9][0-9]*)(?:\.[0-9]{1,6})?$/.test(seconds)) return;
  const [whole,fraction=""]=seconds.split(".");const n=BigInt(whole)*1000000n+BigInt(fraction.padEnd(6,"0"));
  return n<=253402300799999999n ? String(n) : undefined;
}
type Draft = { trigger: AutomationTrigger; enabled: string; seconds: string };
function pendingTerms(v: unknown,institute: string): v is AutomationTerms {
  return validAutomationTerms(v,institute) && Object.keys(v).length === 4 && Object.keys(v.policy).length === 2 && v.policy.rules.every(r => Object.keys(r).length === 3);
}
export function CrmAutomationPolicyPanel({ institute,onChanged }: { institute: string; onChanged?: () => void }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Editor key={JSON.stringify([institute,getAccessToken()])} institute={institute} onChanged={onChanged} />;
}
function Editor({ institute, onChanged }: { institute: string; onChanged?: () => void }) {
  const token = getAccessToken(), actor = getOperatorSubject(), storage = `flowpilot.crm-automation-policy-request:${JSON.stringify([institute, actor])}`;
  const base = `/crm/institutes/${encodeURIComponent(institute)}/automation-policies`;
  const [saved, save] = useState<{ terms?: AutomationTerms; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const value = JSON.parse(raw);
      return pendingTerms(value, institute) ? { terms: value } : { invalid: true }; } catch { return { invalid: true }; }
  });
  const [original, setOriginal] = useState<AutomationOriginal | null>(), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, setRejected] = useState(false);
  const [draft,setDraft] = useState<Draft[]>([]);
  const [reason, setReason] = useState(""), [predecessor, setPredecessor] = useState<string | null>();
  const mounted = useRef(false), pending = useRef(false), sequence = useRef(0);
  const current = () => mounted.current && token === getAccessToken();
  const frozen = busy || !!saved.terms || !!saved.invalid;
  async function read() {
    const request = ++sequence.current; setLoading(true); setOriginal(undefined);
    try { const v = await apiGet<unknown>(base+"/current");
      if (!current() || request !== sequence.current) return false;
      if (v !== null && !validAutomationOriginal(v, institute)) throw new Error("Politique courante à vérifier.");
      setOriginal(v); return true;
    } catch (e) { if (current() && request === sequence.current) setError(e instanceof Error ? e.message : "Politique indisponible."); return false; }
    finally { if (current() && request === sequence.current) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void read(); return () => { mounted.current = false; sequence.current++; }; }, []);
  async function run(terms: AutomationTerms) {
    if (!current() || pending.current || !actor || saved.invalid || !pendingTerms(terms, institute)) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); setRejected(false);
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/original/${encodeURIComponent(terms.idempotency_key)}`;
      let receipt = await apiGet<unknown>(path); if (!current()) return;
      if (receipt === null) { posting = true; receipt = await apiPost<unknown>(base, terms); returned = true; }
      if (!current()) return;
      if (!validAutomationOriginal(receipt, institute) || !matchesAutomationReceipt(receipt, terms, actor)) throw new Error("Politique originale à vérifier.");
      const verified = await apiGet<unknown>(path); if (!current()) return;
      if (!validAutomationOriginal(verified, institute) || !sameAutomationOriginal(receipt, verified)) throw new Error("Original relu à vérifier.");
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
    setDraft(original ? original.policy.rules.map(r => ({trigger:r.trigger,enabled:String(r.enabled),seconds:automationSeconds(r.offset_us)}))
      : automationTriggers.map(trigger => ({trigger,enabled:"",seconds:trigger==="birthday" ? "0" : ""})));
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    if (frozen || loading || original === undefined || predecessor === undefined || predecessor !== (original?.id || null) || !actor) return;
    if (draft.length!==6 || draft.some(r => !["true","false"].includes(r.enabled) || automationMicroseconds(r.seconds)===undefined)) {
      setError("Déclarez activation et durée explicites pour chaque règle."); return;
    }
    const terms = { policy:{institute_id:institute,rules:draft.map(r => ({trigger:r.trigger,enabled:r.enabled==="true",offset_us:automationMicroseconds(r.seconds)!}))},
      previous_policy_id:predecessor,reason:reason.trim(),idempotency_key:crypto.randomUUID() };
    if (!pendingTerms(terms,institute)) { setError("Vérifiez les six règles, les intervalles et le motif."); return; }
    void run(terms);
  }
  return <section aria-label="Règles automatisation"><h3>Règles du cycle de vie</h3>
    <p>Ces règles créent des événements internes. Aucun message n'est envoyé. Le worker récurrent doit être activé séparément.</p>
    <p>Anniversaire : journée locale du calendrier déclaré. Autres durées : secondes écoulées, jusqu'à six décimales, sans arrondi.</p>
    <button disabled={busy || loading} onClick={() => {setError(undefined);void read();}}>Actualiser les règles</button>
    {loading && <p role="status">Lecture des règles...</p>}{error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    {original === null && <p>Aucune règle configurée.</p>}
    {original && <><p>Original {original.id} | acteur {original.actor_id} | motif : {original.reason}</p>
      <ul>{original.policy.rules.map(r => <li key={r.trigger}>{labels[r.trigger]} : {r.enabled ? "active" : "désactivée"} | {r.trigger==="birthday" ? "journée locale" : `${automationSeconds(r.offset_us)} secondes`}</li>)}</ul></>}
    {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
    {saved.terms && <><p>Demande conservée : {saved.terms.reason}</p><button disabled={busy} onClick={() => void run(saved.terms!)}>Reprendre les règles conservées</button></>}
    {rejected && <button onClick={() => {sessionStorage.removeItem(storage);save({});setRejected(false);setPredecessor(undefined);}}>Corriger les règles refusées</button>}
    <button disabled={frozen || loading || original===undefined} onClick={prepare}>{original ? "Préparer une correction des règles" : "Préparer les règles"}</button>
    {predecessor!==undefined && <form onSubmit={submit}><fieldset disabled={frozen || loading}><legend>Six règles explicites</legend>
      {draft.map((r,i) => <fieldset key={r.trigger}><legend>{labels[r.trigger]}</legend>
        <label>Activation {labels[r.trigger]}<select required value={r.enabled} onChange={e => setDraft(v => v.map((p,j) => j===i ? {...p,enabled:e.target.value} : p))}>
          <option value="">Choisir</option><option value="true">Activer</option><option value="false">Désactiver</option></select></label>
        {r.trigger!=="birthday" && <label>{["package_expiry","subscription_renewal"].includes(r.trigger) ? "Anticipation" : "Délai"} {labels[r.trigger]} (secondes)
          <input required inputMode="decimal" maxLength={19} value={r.seconds} onChange={e => setDraft(v => v.map((p,j) => j===i ? {...p,seconds:e.target.value} : p))} /></label>}
        {r.trigger==="birthday" && <p>Selon le fuseau et la règle du 29 février du calendrier anniversaire.</p>}
      </fieldset>)}
      <label>Motif des règles<input required minLength={3} maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button disabled={!actor || original===undefined || predecessor!==(original?.id || null)}>Enregistrer les règles</button>
    </fieldset></form>}
  </section>;
}
