import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
type Parent = { id: string; amount: string; currency: string };
type Intent = { kind: "authorize" | "capture" | "cancel" | "refund"; amount: string; currency: string; parent_intent_id: string | null; idempotency_key: string };
type Props = { instituteId: string; ticketId: string; parent: Parent; kind: Intent["kind"]; onRefresh: () => Promise<boolean>; onRecorded: () => void };
const labels = { authorize: "Préparer l'autorisation", capture: "Préparer l'encaissement", cancel: "Préparer l'annulation", refund: "Préparer le remboursement" };
function money(value: string) { return /^\d{1,8}\.\d{2}$/.test(value) && Number(value) > 0; }
export function PaymentPreparation(props: Props) {
  return <Preparation key={JSON.stringify([props.instituteId, props.ticketId, props.parent.id, props.kind, getAccessToken()])} {...props} />;
}
function Preparation({ instituteId, ticketId, parent, kind, onRefresh, onRecorded }: Props) {
  const token = getAccessToken(), actor = getOperatorSubject(), role = getOperatorRole();
  const allowed = !!actor && actor === actor.trim() && ["accueil", "responsable_institut"].includes(role || "") && (kind !== "refund" || role === "responsable_institut");
  const key = `flowpilot.payment-preparation:${JSON.stringify([instituteId, ticketId, parent.id, kind, actor])}`;
  const [intent, setIntent] = useState<Intent | undefined>(() => {
    try {
      const row = JSON.parse(sessionStorage.getItem(key) || "null");
      if (allowed && row && row.kind === kind && row.parent_intent_id === (kind === "authorize" ? null : parent.id) && (kind === "authorize" ? ["CHF", "EUR"].includes(row.currency) : row.currency === parent.currency) && money(row.amount) &&
          (kind === "refund" || kind === "authorize" || row.amount === parent.amount) && typeof row.idempotency_key === "string" && !!row.idempotency_key.trim() && row.idempotency_key === row.idempotency_key.trim() && row.idempotency_key.length <= 120)
        return { kind, amount: row.amount, currency: row.currency, parent_intent_id: kind === "authorize" ? null : parent.id, idempotency_key: row.idempotency_key };
    } catch { /* No untrusted recovery request. */ }
  });
  const [amount, setAmount] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const lifetime = useRef(0), pending = useRef(false);
  const callbacks = useRef({ onRefresh, onRecorded }); callbacks.current = { onRefresh, onRecorded };
  useEffect(() => { lifetime.current++; return () => { lifetime.current++; }; }, []);
  async function prepare() {
    if (!allowed || pending.current) return;
    const row = intent || { kind, amount: kind === "refund" ? amount.replace(",", ".") : parent.amount, currency: parent.currency, parent_intent_id: kind === "authorize" ? null : parent.id, idempotency_key: crypto.randomUUID() };
    if (!money(row.amount)) return;
    const generation = lifetime.current, current = () => generation === lifetime.current && token === getAccessToken();
    pending.current = true; setBusy(true); setIntent(row); setError(undefined);
    const base = `/payments/institutes/${encodeURIComponent(instituteId)}`;
    try {
      sessionStorage.setItem(key, JSON.stringify(row));
      let result: { id: string; kind: string; amount: string; currency: string; idempotency_key: string };
      try { result = await apiPost(`${base}/tickets/${encodeURIComponent(ticketId)}/intents`, row); }
      catch (failure) {
        if (current() && failure instanceof ApiError && failure.status >= 400 && failure.status < 500) { sessionStorage.removeItem(key); setIntent(undefined); }
        throw failure;
      }
      if (!current()) return;
      if (!result || typeof result.id !== "string" || !result.id || result.kind !== kind || result.amount !== row.amount || result.currency !== row.currency || result.idempotency_key !== row.idempotency_key) throw new Error("Demande de paiement à vérifier");
      const snapshot = await apiGet<{ ticket_id: string; operations: Array<typeof result & { actor_id: string }> }>(`${base}/tickets/${encodeURIComponent(ticketId)}/snapshot`);
      if (!current()) return;
      const matching = Array.isArray(snapshot?.operations) ? snapshot.operations.filter(value => value.id === result.id) : [];
      const fact = matching[0];
      if (snapshot?.ticket_id !== ticketId || matching.length !== 1 || fact.kind !== kind || fact.amount !== row.amount || fact.currency !== row.currency || fact.actor_id !== actor || fact.idempotency_key !== row.idempotency_key) throw new Error("Demande enregistrée à vérifier");
      if (!await callbacks.current.onRefresh()) throw new Error("Actualiser le ticket avant de poursuivre");
      if (!current()) return;
      sessionStorage.removeItem(key); setIntent(undefined); callbacks.current.onRecorded();
    } catch (failure) { if (current()) setError(`${failure instanceof Error ? failure.message : "Demande indisponible"}. Reprenez la demande conservée.`); }
    finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  if (!allowed) return null;
  return <div>
    {error && <p role="alert">{error}</p>}
    {intent ? <p>Demande conservée : {intent.amount.replace(".", ",")} {intent.currency}</p> : kind === "refund" && <label>Montant à rembourser ({parent.currency})<input inputMode="decimal" value={amount} onChange={event => setAmount(event.target.value)} /></label>}
    <button type="button" disabled={busy || (!intent && kind === "refund" && !money(amount.replace(",", ".")))} onClick={() => void prepare()}>{intent ? "Reprendre la demande conservée" : labels[kind]}</button>
  </div>;
}
