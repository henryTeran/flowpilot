import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validLifecycleTerms, validLifecycleOriginal, matchesLifecycleReceipt, sameLifecycleOriginal, type LifecycleTerms, type LifecycleOriginal } from "../crm-lifecycle-utils";
function pendingTerms(v: unknown,institute: string,customer: string): v is LifecycleTerms {
  return validLifecycleTerms(v,institute,customer) && Object.keys(v).length === 4 && Object.keys(v.declaration).length === 5;
}
export function CrmLifecycleEditor({ institute,customer,onChanged }: { institute: string; customer: string; onChanged?: () => void }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Editor key={JSON.stringify([institute,customer,getAccessToken()])} institute={institute} customer={customer} onChanged={onChanged} />;
}
function Editor({ institute,customer, onChanged }: { institute: string; customer: string; onChanged?: () => void }) {
  const token = getAccessToken(), actor = getOperatorSubject(), storage = `flowpilot.crm-lifecycle-request:${JSON.stringify([institute,customer, actor])}`;
  const base = `/crm/institutes/${encodeURIComponent(institute)}/customers/${encodeURIComponent(customer)}/lifecycle-declarations`;
  const [saved, save] = useState<{ terms?: LifecycleTerms; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const value = JSON.parse(raw);
      return pendingTerms(value, institute,customer) ? { terms: value } : { invalid: true }; } catch { return { invalid: true }; }
  });
  const [original, setOriginal] = useState<LifecycleOriginal | null>(), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, setRejected] = useState(false);
  const [known,setKnown] = useState(""), [month,setMonth] = useState(""), [day,setDay] = useState(""), [birthEvidence,setBirthEvidence] = useState("");
  const [communications,setCommunications] = useState<LifecycleTerms["declaration"]["communications"]>([]);
  const [reason, setReason] = useState(""), [predecessor, setPredecessor] = useState<string | null>();
  const mounted = useRef(false), pending = useRef(false), sequence = useRef(0);
  const current = () => mounted.current && token === getAccessToken();
  const frozen = busy || !!saved.terms || !!saved.invalid;
  async function read() {
    const request = ++sequence.current; setLoading(true); setOriginal(undefined);
    try { const v = await apiGet<unknown>(base+"/current");
      if (!current() || request !== sequence.current) return false;
      if (v !== null && !validLifecycleOriginal(v, institute,customer)) throw new Error("Déclaration courante à vérifier.");
      setOriginal(v); return true;
    } catch (e) { if (current() && request === sequence.current) setError(e instanceof Error ? e.message : "Déclaration indisponible."); return false; }
    finally { if (current() && request === sequence.current) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void read(); return () => { mounted.current = false; sequence.current++; }; }, []);
  async function run(terms: LifecycleTerms) {
    if (!current() || pending.current || !actor || saved.invalid || !pendingTerms(terms, institute,customer)) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); setRejected(false);
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/original/${encodeURIComponent(terms.idempotency_key)}`;
      let receipt = await apiGet<unknown>(path); if (!current()) return;
      if (receipt === null) { posting = true; receipt = await apiPost<unknown>(base, terms); returned = true; }
      if (!current()) return;
      if (!validLifecycleOriginal(receipt, institute,customer) || !matchesLifecycleReceipt(receipt, terms, actor)) throw new Error("Déclaration originale à vérifier.");
      const verified = await apiGet<unknown>(path); if (!current()) return;
      if (!validLifecycleOriginal(verified, institute,customer) || !sameLifecycleOriginal(receipt, verified)) throw new Error("Original relu à vérifier.");
      if (!await read() || !current()) throw new Error("Relisez la déclaration courante avant de clore la demande.");
      if (sessionStorage.getItem(storage) !== raw) throw new Error("Demande conservée à vérifier.");
      sessionStorage.removeItem(storage); save({}); setPredecessor(undefined); setSuccess("Déclaration originale vérifiée et sélection courante relue.");
      onChanged?.();
    } catch (e) { if (current()) { setError(e instanceof Error ? e.message : "Demande à reprendre.");
      setRejected(posting && !returned && e instanceof ApiError && [400, 422].includes(e.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function prepare() {
    if (original === undefined || frozen) return;
    setPredecessor(original?.id || null); setReason(""); setError(undefined); setSuccess(undefined);
    if (original) { const d = original.declaration; setKnown(d.birthday ? "known" : "unknown"); setMonth(d.birthday ? String(d.birthday.month) : ""); setDay(d.birthday ? String(d.birthday.day) : ""); setBirthEvidence(d.birthday_evidence || ""); setCommunications(d.communications.map(c => ({...c}))); }
    else { setKnown(""); setCommunications((["email","sms"] as const).flatMap(channel => (["service_follow_up","marketing"] as const).map(purpose => ({channel,purpose,permission:"unknown" as const,evidence:null})))); }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    if (frozen || loading || original === undefined || predecessor === undefined || predecessor !== (original?.id || null) || !actor) return;
    if (!["known","unknown"].includes(known)) { setError("Choisissez anniversaire connu ou inconnu."); return; }
    const terms: LifecycleTerms = { declaration: { institute_id: institute,customer_id: customer,
      birthday: known === "known" ? {month:Number(month),day:Number(day)} : null,
      birthday_evidence: known === "known" ? birthEvidence.trim() : null,
      communications: communications.map(c => ({...c,evidence:c.permission === "unknown" ? null : c.evidence?.trim() || null})) },
      previous_id: predecessor,reason:reason.trim(),idempotency_key:crypto.randomUUID() };
    if (!pendingTerms(terms,institute,customer)) { setError("Date, permissions, preuves et motif doivent etre coherents."); return; }
    void run(terms);
  }
  return <section aria-label="Declaration du cycle de vie"><h3>Declaration cliente</h3>
    <p>Aucune permission ne vaut pour un autre canal ou usage. Une permission declaree ne certifie pas une autorisation de livraison.</p>
    <button disabled={busy || loading} onClick={() => { setError(undefined); void read(); }}>Actualiser la declaration</button>
    {loading && <p role="status">Lecture...</p>}{error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    {original === null && <p>Aucune declaration cliente.</p>}
    {original && <p>Original {original.id} | acteur {original.actor_id} | motif : {original.reason}</p>}
    {saved.invalid && <p role="alert">Demande conservee invalide : aucune ecriture possible.</p>}
    {saved.terms && <><p>Demande conservee : {saved.terms.reason}</p><button disabled={busy} onClick={() => void run(saved.terms!)}>Reprendre la declaration conservee</button></>}
    {rejected && <button onClick={() => { sessionStorage.removeItem(storage); save({}); setRejected(false); setPredecessor(undefined); }}>Corriger la declaration refusee</button>}
    <button disabled={frozen || loading || original === undefined} onClick={prepare}>{original ? "Preparer une correction cliente" : "Preparer la declaration cliente"}</button>
    {predecessor !== undefined && <form onSubmit={submit}><fieldset disabled={frozen || loading}><legend>Faits et permissions explicites</legend>
      <label>Anniversaire<select required value={known} onChange={e => setKnown(e.target.value)}><option value="">Choisir</option><option value="unknown">Inconnu</option><option value="known">Connu avec preuve</option></select></label>
      {known === "known" && <><label>Mois<input required type="number" min={1} max={12} step={1} value={month} onChange={e => setMonth(e.target.value)} /></label>
        <label>Jour<input required type="number" min={1} max={31} step={1} value={day} onChange={e => setDay(e.target.value)} /></label>
        <label>Preuve anniversaire<input required minLength={3} maxLength={240} value={birthEvidence} onChange={e => setBirthEvidence(e.target.value)} /></label></>}
      {communications.map((c,i) => { const label = `${c.channel === "email" ? "Email" : "SMS"} ${c.purpose === "marketing" ? "marketing" : "suivi de soin"}`;
        return <fieldset key={`${c.channel}:${c.purpose}`}><legend>{label}</legend><label>Permission {label}<select value={c.permission} onChange={e => setCommunications(v => v.map((p,j) => j === i ? {...p,permission:e.target.value as typeof c.permission,evidence:null} : p))}>
          <option value="unknown">Inconnue</option><option value="granted">Accord declare</option><option value="refused">Refus declare</option></select></label>
          {c.permission !== "unknown" && <label>Preuve {label}<input required minLength={3} maxLength={240} value={c.evidence || ""} onChange={e => setCommunications(v => v.map((p,j) => j === i ? {...p,evidence:e.target.value} : p))} /></label>}</fieldset>;
      })}
      <label>Motif declaration<input required minLength={3} maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button disabled={!actor || original === undefined || predecessor !== (original?.id || null)}>Enregistrer la declaration cliente</button>
    </fieldset></form>}
  </section>;
}
