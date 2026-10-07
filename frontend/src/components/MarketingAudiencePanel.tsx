import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { marketingSegments, validAudienceRequest, validAudienceOriginal, matchesAudienceReceipt, sameAudienceOriginal,
  type MarketingSegment, type AudienceRequest, type AudienceOriginal } from "../marketing-audience-utils";
const labels: Record<MarketingSegment, string> = { NEW: "Nouvelles", ACTIVE: "Actives", LOYAL: "Fidèles", VIP: "VIP", AT_RISK: "À risque", DORMANT: "Inactives" };
export function MarketingAudiencePanel({ institute }: { institute: string }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Capture key={JSON.stringify([institute, getAccessToken()])} institute={institute} />;
}
function Capture({ institute }: { institute: string }) {
  const actor = getOperatorSubject(), token = getAccessToken(), mounted = useRef(false), pending = useRef(false);
  const storage = `flowpilot.marketing-audience-request:${JSON.stringify([institute, actor])}`;
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/audience-captures`;
  const [saved, save] = useState<{ terms?: AudienceRequest; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {};
      const value = JSON.parse(raw); return validAudienceRequest(value) ? { terms: value } : { invalid: true };
    } catch { return { invalid: true }; }
  });
  const [segments, setSegments] = useState<MarketingSegment[]>([]), [channel, setChannel] = useState("");
  const [reason, setReason] = useState(""), [busy, setBusy] = useState(false), [rejected, setRejected] = useState(false);
  const [error, setError] = useState<string>(), [original, setOriginal] = useState<AudienceOriginal>();
  const current = () => mounted.current && token === getAccessToken();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function run(terms: AudienceRequest) {
    if (!current() || pending.current || !actor || saved.invalid || !validAudienceRequest(terms)) return;
    pending.current = true; setBusy(true); setError(undefined); setOriginal(undefined); setRejected(false);
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/original/${encodeURIComponent(terms.idempotency_key)}`;
      let receipt = await apiGet<unknown>(path); if (!current()) return;
      if (receipt === null) { posting = true; receipt = await apiPost<unknown>(base, terms); returned = true; }
      if (!current()) return;
      if (!validAudienceOriginal(receipt, institute) || !matchesAudienceReceipt(receipt, terms, actor)) throw new Error("Capture originale à vérifier.");
      const [byKey, byId] = await Promise.all([apiGet<unknown>(path), apiGet<unknown>(`${base}/${encodeURIComponent(receipt.id)}`)]);
      if (!current()) return;
      if (!validAudienceOriginal(byKey, institute) || !validAudienceOriginal(byId, institute)
        || !sameAudienceOriginal(receipt, byKey) || !sameAudienceOriginal(receipt, byId)) throw new Error("Original relu à vérifier.");
      if (sessionStorage.getItem(storage) !== raw) throw new Error("Demande conservée à vérifier.");
      sessionStorage.removeItem(storage); save({}); setOriginal(receipt); setReason("");
    } catch (e) { if (current()) { setError(e instanceof Error ? e.message : "Capture à reprendre.");
      setRejected(posting && !returned && e instanceof ApiError && [400, 422].includes(e.status)); }
    } finally { pending.current = false; if (current()) setBusy(false); }
  }
  const frozen = busy || !!saved.terms || !!saved.invalid;
  function submit(event: FormEvent) {
    event.preventDefault(); if (frozen || !actor) return;
    const terms = { segments, channel, reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validAudienceRequest(terms)) { setError("Choisissez au moins un segment, un canal et un motif explicite."); return; }
    void run(terms);
  }
  return <section aria-label="Capturer une audience"><h3>Capturer une audience</h3>
    <p>La capture retient les clientes enregistrées, leur segment observé et leur permission marketing déclarée. Les permissions inconnues restent exclues.</p>
    {busy && <p role="status">Vérification de la capture…</p>}{error && <p role="alert">{error}</p>}
    {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
    {saved.terms && <><p>Capture conservée : {saved.terms.channel} · {saved.terms.reason}</p>
      <button disabled={busy} onClick={() => void run(saved.terms!)}>Reprendre la capture conservée</button></>}
    {rejected && <button onClick={() => {
      if (!saved.terms || sessionStorage.getItem(storage) !== JSON.stringify(saved.terms)) return;
      sessionStorage.removeItem(storage); save({}); setRejected(false);
    }}>Corriger la capture refusée</button>}
    <form onSubmit={submit}><fieldset className="marketing-audience-fields" disabled={frozen}><legend>Segments et canal</legend>
      {marketingSegments.map(segment => <label className="marketing-segment-option" key={segment}><input type="checkbox" style={{ width: 44 }} checked={segments.includes(segment)}
        onChange={event => setSegments(previous => event.target.checked ? marketingSegments.filter(s => s === segment || previous.includes(s)) : previous.filter(s => s !== segment))} />{labels[segment]}</label>)}
      <label>Canal de l’audience<select required value={channel} onChange={e => setChannel(e.target.value)}><option value="">Choisir</option>
        <option value="email">Email</option><option value="sms">SMS</option><option value="push">Push</option></select></label>
      <label>Motif de capture<input required minLength={3} maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button disabled={!actor}>Conserver l’audience</button>
    </fieldset></form>
    {original && <div role="status"><p>Capture originale vérifiée : {original.id}</p>
      <p>{original.summary.customer_count} clientes observées · {original.summary.selected_count} sélectionnées · {original.summary.eligible_count} éligibles selon la permission retenue.</p>
      <p>{original.summary.page_count} pages conservées · {original.captured_at}</p></div>}
    <p>Cette capture ne réalise aucun envoi. Push ne dispose pas encore d’une déclaration de permission prise en charge.</p>
  </section>;
}
