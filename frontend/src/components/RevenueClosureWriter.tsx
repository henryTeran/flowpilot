import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validClosureDeclaration, validClosureEnvelope, matchesClosureReceipt, compatibleReference, type ClosureEvidence, type PriceReference, type ClosureDeclaration, type ClosureEnvelope } from "../revenue-closure-utils";
import { ClosureReceipt } from "./RevenueClosureHistory";
type Saved = { institute: string; actor: string; appointment: string; terms: ClosureDeclaration };
type Props = { institute: string; closure?: ClosureEvidence; reference?: PriceReference; onRetained?: () => void };
export function RevenueClosureWriter(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut" || !getOperatorSubject()) return null;
  return <Writer key={JSON.stringify([props.institute, getAccessToken()])} {...props} />;
}
function Writer({ institute, closure, reference, onRetained }: Props) {
  const actor = getOperatorSubject()!, token = getAccessToken(), storage = `flowpilot.closure-valuation.v1:${JSON.stringify([institute, actor])}`, base = `/revenue/institutes/${encodeURIComponent(institute)}`;
  function validSaved(v: unknown): v is Saved { const s = v as Saved; return !!s && typeof s === "object" && Object.keys(s).sort().join(" ") === "actor appointment institute terms"
    && s.institute === institute && s.actor === actor && typeof s.appointment === "string" && s.appointment.trim() === s.appointment && !!s.appointment && Array.from(s.appointment).length <= 80 && validClosureDeclaration(s.terms); }
  const [saved, setSaved] = useState<{ value?: Saved; invalid?: boolean }>(() => { try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const s = JSON.parse(raw); return validSaved(s) ? { value: s } : { invalid: true }; } catch { return { invalid: true }; } });
  const [rate, setRate] = useState(""), [reason, setReason] = useState(""), [receipt, setReceipt] = useState<ClosureEnvelope>(), [busy, setBusy] = useState(false), [rejected, setRejected] = useState(false), [error, setError] = useState<string>();
  const mounted = useRef(false), pending = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { if (!saved.value && !receipt) { setRate(""); setReason(""); setError(undefined); } }, [closure?.event_id, reference?.fingerprint, saved.value, receipt]);
  const current = () => mounted.current && token === getAccessToken() && actor === getOperatorSubject() && getOperatorRole() === "responsable_institut";
  const byKey = (terms: ClosureDeclaration) => apiGet<ClosureEnvelope | null>(`${base}/closure-value-original-by-key?${new URLSearchParams({ key: terms.idempotency_key })}`);
  async function accept(e: ClosureEnvelope, intent: Saved) {
    if (!await validClosureEnvelope(e, institute, intent.appointment) || !matchesClosureReceipt(e, intent.appointment, intent.terms, actor)) throw new Error();
    if (!current()) return;
    const keyed = await byKey(intent.terms);
    if (!keyed || !await validClosureEnvelope(keyed, institute, intent.appointment) || !matchesClosureReceipt(keyed, intent.appointment, intent.terms, actor) || keyed.fingerprint !== e.fingerprint || keyed.original.id !== e.original.id) throw new Error();
    if (!current()) return;
    const identified = await apiGet<ClosureEnvelope>(`${base}/closure-value-originals/${encodeURIComponent(e.original.id)}`);
    if (!await validClosureEnvelope(identified, institute, intent.appointment) || !matchesClosureReceipt(identified, intent.appointment, intent.terms, actor) || identified.fingerprint !== e.fingerprint || identified.original.id !== e.original.id) throw new Error();
    if (!current()) return;
    const raw = sessionStorage.getItem(storage);
    if (!raw || !validSaved(JSON.parse(raw)) || JSON.stringify(JSON.parse(raw)) !== JSON.stringify(intent)) throw new Error();
    sessionStorage.removeItem(storage); setSaved({}); setReceipt(identified); onRetained?.();
  }
  async function retain() {
    if (!current() || pending.current || saved.invalid || receipt) return;
    pending.current = true; setBusy(true); setRejected(false); setError(undefined); let frozen = !!saved.value;
    try {
      let intent = saved.value;
      if (!intent) {
        if (!closure || !reference || !compatibleReference(reference, closure)) throw new Error();
        const terms: ClosureDeclaration = { valuation: { reference_event_id: reference.terms.event_id, expected_fingerprint: reference.fingerprint, closure_event_id: closure.event_id, rate: rate as "member" | "passage", reason: reason.trim() }, idempotency_key: crypto.randomUUID() };
        if (!validClosureDeclaration(terms) || !current() || sessionStorage.getItem(storage) !== null) throw new Error();
        intent = { institute, actor, appointment: closure.appointment_id, terms }; sessionStorage.setItem(storage, JSON.stringify(intent)); setSaved({ value: intent }); frozen = true;
      }
      const original = await byKey(intent.terms); if (!current()) return;
      if (original) { await accept(original, intent); return; }
      await accept(await apiPost<ClosureEnvelope>(`${base}/appointments/${encodeURIComponent(intent.appointment)}/closure-value-originals`, intent.terms), intent);
    } catch (e) { if (current()) { if (e instanceof ApiError && [400, 422].includes(e.status)) setRejected(true);
      setError(frozen ? "Conservation à vérifier. Reprenez la demande figée avec la même clé." : "Demande non envoyée. Choisissez une référence compatible, un tarif et un motif d’au moins trois caractères."); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  async function correct() {
    if (!current() || pending.current || !saved.value || !rejected) return;
    pending.current = true; setBusy(true); setError(undefined);
    try {
      const intent = saved.value, original = await byKey(intent.terms); if (!current()) return;
      if (original) { await accept(original, intent); return; }
      const raw = sessionStorage.getItem(storage);
      if (!raw || !validSaved(JSON.parse(raw)) || JSON.stringify(JSON.parse(raw)) !== JSON.stringify(intent)) throw new Error();
      sessionStorage.removeItem(storage); setSaved({}); setRejected(false);
    } catch { if (current()) setError("Clé à vérifier. La demande figée reste conservée."); }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  const locked = busy || !!saved.value || !!saved.invalid || !!receipt;
  return <section className="revenue-guardian-panel" aria-label="Conserver une valorisation"><h2>Conserver un scénario de valorisation</h2><p>Choix explicite d’un tarif historique. Aucun prix convenu, paiement, éligibilité membre ou perte causale n’est déduit ; aucun suivi n’est déclenché.</p>
    {!saved.value && !receipt && <p>{closure && reference ? `Réservation ${closure.appointment_id} · Référence ${reference.terms.event_id} du ${reference.terms.occurred_at}` : "Lisez un événement terminal, puis choisissez une référence tarifaire compatible."}</p>}
    {!receipt && <><div className="revenue-guardian-period"><label>Tarif déclaré <select disabled={locked} value={rate} onChange={e => setRate(e.target.value)}><option value="">Choisir</option><option value="member">Membre</option><option value="passage">Passage</option></select></label></div>
      <label>Motif de la valorisation <textarea disabled={locked} value={reason} onChange={e => setReason(e.target.value)} /></label></>}
    {saved.value && <article><h3>Demande figée à reprendre</h3><p>Réservation {saved.value.appointment} · Événement terminal {saved.value.terms.valuation.closure_event_id}</p><p>Référence {saved.value.terms.valuation.reference_event_id} · Empreinte {saved.value.terms.valuation.expected_fingerprint}</p><p>Tarif {saved.value.terms.valuation.rate === "member" ? "membre" : "passage"} · {saved.value.terms.valuation.reason}</p><p>Clé : {saved.value.terms.idempotency_key}</p></article>}
    {saved.invalid && <p role="alert">La demande locale est illisible. Aucune nouvelle conservation n’est autorisée dans ce contexte.</p>}
    {!receipt && <div className="revenue-guardian-period"><button disabled={busy || !!saved.invalid || !saved.value && (!closure || !reference || !compatibleReference(reference, closure))} onClick={() => void retain()}>{saved.value ? "Reprendre la valorisation par clé" : "Conserver ce scénario de valorisation"}</button>{rejected && saved.value && <button disabled={busy} onClick={() => void correct()}>Vérifier la clé avant correction</button>}</div>}
    {busy && <p role="status">Vérification de la conservation…</p>}{error && <p role="alert">{error}</p>}
    {receipt && <><h3>Valorisation conservée et relue</h3><ClosureReceipt value={receipt} /><div className="revenue-guardian-period"><button onClick={() => { setReceipt(undefined); setRate(""); setReason(""); setError(undefined); }}>Déclarer une autre valorisation</button></div></>}
  </section>;
}
