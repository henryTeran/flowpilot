import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";

type Intent = { points: number; reason: string; idempotency_key: string };
type Receipt = Intent & { id: string; refund_intent_id: string; actor_id: string; entry_id: string | null };
type Props = { instituteId: string; ticketId: string; refundId: string; onRefresh: () => Promise<boolean>; onRecorded: () => void };
function valid(row: Intent) {
  return !!row && Number.isSafeInteger(row.points) && row.points <= 0 && row.points >= -1e9 &&
    typeof row.reason === "string" && !!row.reason.trim() && row.reason === row.reason.trim() && row.reason.length <= 240 &&
    typeof row.idempotency_key === "string" && !!row.idempotency_key.trim() && row.idempotency_key === row.idempotency_key.trim() && row.idempotency_key.length <= 120;
}
function recover(key: string): Intent | undefined {
  try { const row = JSON.parse(sessionStorage.getItem(key) || "null"); return valid(row) ? { points: row.points, reason: row.reason, idempotency_key: row.idempotency_key } : undefined; } catch { return; }
}
export function RefundLoyaltyDecision(props: Props) {
  return <DecisionForm key={JSON.stringify([props.instituteId, props.ticketId, props.refundId, getAccessToken()])} {...props} />;
}
function DecisionForm({ instituteId, ticketId, refundId, onRefresh, onRecorded }: Props) {
  const token = getAccessToken(), actor = getOperatorSubject();
  const manager = getOperatorRole() === "responsable_institut" && !!actor && actor === actor.trim() && actor.length <= 160;
  const key = `flowpilot.refund-loyalty:${JSON.stringify([instituteId, ticketId, refundId, actor])}`;
  const path = `/payments/institutes/${encodeURIComponent(instituteId)}/refunds/${encodeURIComponent(refundId)}/loyalty-decision`;
  const [intent, setIntent] = useState<Intent | undefined>(() => manager ? recover(key) : undefined);
  const [points, setPoints] = useState("0"), [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const lifetime = useRef(0), pending = useRef(false);
  const callbacks = useRef({ onRefresh, onRecorded }); callbacks.current = { onRefresh, onRecorded };
  useEffect(() => { lifetime.current++; return () => { lifetime.current++; }; }, []);
  function matches(receipt: Receipt, row: Intent) {
    return !!receipt && typeof receipt.id === "string" && !!receipt.id && receipt.refund_intent_id === refundId &&
      receipt.actor_id === actor && receipt.idempotency_key === row.idempotency_key && receipt.points === row.points && receipt.reason === row.reason &&
      (row.points === 0 ? receipt.entry_id === null : typeof receipt.entry_id === "string" && !!receipt.entry_id);
  }
  async function save() {
    if (!manager || pending.current) return;
    if (!intent && !/^-?\d+$/.test(points)) return;
    const row = intent || { points: Number(points), reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!valid(row)) return;
    const generation = lifetime.current;
    const current = () => generation === lifetime.current && token === getAccessToken();
    pending.current = true; setBusy(true); setError(undefined); setIntent(row);
    try {
      sessionStorage.setItem(key, JSON.stringify(row));
      let receipt = await apiGet<Receipt | null>(path);
      if (!current()) return;
      if (receipt === null) {
        try { await apiPost(path, row); }
        catch (failure) {
          if (current() && failure instanceof ApiError && failure.status >= 400 && failure.status < 500) {
            sessionStorage.removeItem(key); setIntent(undefined); setPoints(String(row.points)); setReason(row.reason);
          }
          throw failure;
        }
        if (!current()) return;
        receipt = await apiGet<Receipt | null>(path);
      }
      if (!current()) return;
      if (!receipt || !matches(receipt, row)) throw new Error("La décision enregistrée ne correspond pas à cette intention. Actualisez les paiements.");
      if (!await callbacks.current.onRefresh()) throw new Error("Actualiser le solde et son historique avant de poursuivre");
      if (!current()) return;
      sessionStorage.removeItem(key); setIntent(undefined); callbacks.current.onRecorded();
    } catch (failure) {
      if (current()) setError(failure instanceof Error ? failure.message : "Décision indisponible");
    } finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  if (!manager) return null;
  return <section aria-label="Décision de fidélité après remboursement">
    <h4>Fidélité après remboursement</h4>
    <p>Indiquez 0 pour conserver les points ou une valeur négative pour en retirer, avec un motif.</p>
    {error && <p role="alert">{error}</p>}
    {intent ? <p>Décision conservée : {intent.points} points · {intent.reason}</p> : <fieldset disabled={busy}>
      <label>Variation de points<input inputMode="numeric" value={points} onChange={event => setPoints(event.target.value)} /></label>
      <label>Motif de la décision<input maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label>
    </fieldset>}
    <button type="button" disabled={busy || (!intent && (!/^-?\d+$/.test(points) || Number(points) > 0 || Number(points) < -1e9 || !reason.trim()))} onClick={() => void save()}>
      {intent ? "Récupérer la décision conservée" : "Enregistrer la décision"}
    </button>
  </section>;
}
