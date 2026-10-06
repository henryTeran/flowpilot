import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { AuthorizationPreparation } from "./AuthorizationPreparation";
import { PaymentPreparation } from "./PaymentPreparation";
import { CapturedCheckout } from "./CapturedCheckout";
import { PaymentRecovery } from "./PaymentRecovery";
import { RefundLoyaltyDecision } from "./RefundLoyaltyDecision";
import { getAccessToken } from "../api/session";

type Decision = { id: string; refund_intent_id: string; points: number; reason: string; actor_id: string; entry_id: string | null };
type Operation = { actor_id?: string; id: string; kind: string; amount: string; currency: string; status: string; applied: boolean; active_protection: boolean; loyalty_decision: Decision | null };
type Snapshot = { ticket_id: string; protected: boolean; operations: Operation[] };
const kinds: Record<string, string> = { authorize: "Autorisation", capture: "Encaissement", cancel: "Annulation", refund: "Remboursement" };
const statuses: Record<string, string> = { prepared: "Préparé", unknown: "Résultat à récupérer", pending: "En attente", authorized: "Autorisé", captured: "Encaissé", cancelled: "Annulé", refunded: "Remboursé", failed: "Échec confirmé" };
function valid(value: Snapshot, ticketId: string) {
  if (!value || value.ticket_id !== ticketId || typeof value.protected !== "boolean" || !Array.isArray(value.operations)) return false;
  const ids = new Set<string>();
  for (const row of value.operations) {
    if (!row || typeof row.id !== "string" || !row.id || ids.has(row.id) || !Object.prototype.hasOwnProperty.call(kinds, row.kind) || !Object.prototype.hasOwnProperty.call(statuses, row.status) ||
        typeof row.amount !== "string" || !/^\d{1,8}\.\d{2}$/.test(row.amount) || Number(row.amount) <= 0 ||
        !["CHF", "EUR"].includes(row.currency) || typeof row.applied !== "boolean" || typeof row.active_protection !== "boolean") return false;
    ids.add(row.id);
    const terminal = ({ authorize: "authorized", capture: "captured", cancel: "cancelled", refund: "refunded" } as Record<string, string>)[row.kind];
    if (!["prepared", "unknown", "pending", "failed", terminal].includes(row.status) ||
        (row.applied && (row.kind !== "capture" || row.status !== "captured")) ||
        (row.active_protection && (row.kind !== "authorize" || !["unknown", "pending", "authorized"].includes(row.status)))) return false;
    const decision = row.loyalty_decision;
    if (decision !== null && (!decision || row.kind !== "refund" || row.status !== "refunded" || decision.refund_intent_id !== row.id ||
        typeof decision.id !== "string" || !decision.id || !Number.isSafeInteger(decision.points) || decision.points > 0 || decision.points < -1_000_000_000 ||
        typeof decision.reason !== "string" || !decision.reason.trim() || decision.reason.length > 240 ||
        typeof decision.actor_id !== "string" || !decision.actor_id.trim() ||
        (decision.points === 0 ? decision.entry_id !== null : typeof decision.entry_id !== "string" || !decision.entry_id))) return false;
  }
  return value.protected === value.operations.some(row => row.active_protection);
}

type Props = { instituteId: string; ticketId: string; employeeId?: string; method?: string; authorizationEligible?: boolean; onRefresh?: () => Promise<boolean> };
export function PaymentHistory({ instituteId, ticketId, employeeId, method, authorizationEligible, onRefresh }: Props) {
  const token = getAccessToken();
  return <ScopedPaymentHistory key={JSON.stringify([instituteId, ticketId, token])} instituteId={instituteId} ticketId={ticketId} token={token} employeeId={employeeId} method={method} authorizationEligible={authorizationEligible} onRefresh={onRefresh} />;
}
function ScopedPaymentHistory({ instituteId, ticketId, token, employeeId, method, authorizationEligible, onRefresh }: Props & { token: string | null }) {
  const [snapshot, setSnapshot] = useState<Snapshot>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(true);
  const mounted = useRef(false), sequence = useRef(0);
  async function load() {
    const request = ++sequence.current;
    const current = () => mounted.current && request === sequence.current && token === getAccessToken();
    setLoading(true); setSnapshot(undefined); setError(undefined);
    try {
      const value = await apiGet<Snapshot>(`/payments/institutes/${encodeURIComponent(instituteId)}/tickets/${encodeURIComponent(ticketId)}/snapshot`);
      if (!valid(value, ticketId)) throw new Error("Lecture des paiements incomplète");
      if (current()) setSnapshot(value);
    } catch (reason) {
      if (current()) setError(reason instanceof Error ? reason.message : "Paiements indisponibles");
    } finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, []);
  return <section className="bm-payment-history" aria-label="Historique des paiements">
    <h3>Paiements du ticket</h3>
    <button type="button" disabled={loading} onClick={() => void load()}>Actualiser les paiements</button>
    {loading && <p>Lecture des paiements…</p>}
    {error && <p role="alert">{error}</p>}
    {snapshot?.protected && <p>Paiement en cours ou résultat à récupérer. Le ticket reste protégé.</p>}
    {snapshot && !snapshot.operations.length && <p>Aucune opération prestataire enregistrée.</p>}
    {snapshot && onRefresh && authorizationEligible && !snapshot.protected && !snapshot.operations.some(row => ["prepared", "unknown", "pending"].includes(row.status)) && <AuthorizationPreparation instituteId={instituteId} ticketId={ticketId} onRefresh={onRefresh} onRecorded={() => void load()} />}
    {snapshot?.operations.map(row => <div key={row.id}>
      <p>{kinds[row.kind]} · {row.amount.replace(".", ",")} {row.currency} · {statuses[row.status]}{row.applied ? " · Appliqué en caisse" : ""}</p>
      {row.loyalty_decision && <p>Fidélité : {row.loyalty_decision.points === 0 ? "points conservés" : `${row.loyalty_decision.points} points`} · {row.loyalty_decision.reason}</p>}
      {onRefresh && row.kind === "authorize" && row.status === "authorized" && row.active_protection && (["capture", "cancel"] as const).map(kind => <PaymentPreparation key={kind} instituteId={instituteId} ticketId={ticketId} parent={row} kind={kind} onRefresh={onRefresh} onRecorded={() => void load()} />)}
      {onRefresh && row.kind === "capture" && row.status === "captured" && row.applied && <PaymentPreparation instituteId={instituteId} ticketId={ticketId} parent={row} kind="refund" onRefresh={onRefresh} onRecorded={() => void load()} />}
      {onRefresh && <CapturedCheckout instituteId={instituteId} ticketId={ticketId} operation={row} employeeId={employeeId} method={method} onRefresh={onRefresh} onRecorded={() => void load()} />}
      {onRefresh && <PaymentRecovery instituteId={instituteId} ticketId={ticketId} operation={row} onRefresh={onRefresh} onRecorded={() => void load()} />}
      {onRefresh && row.kind === "refund" && row.status === "refunded" && !row.loyalty_decision && <RefundLoyaltyDecision instituteId={instituteId} ticketId={ticketId} refundId={row.id} onRefresh={onRefresh} onRecorded={() => void load()} />}
    </div>)}
  </section>;
}
