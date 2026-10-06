import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";

type Operation = { id: string; kind: string; amount: string; currency: string; actor_id?: string; status: string };
type Props = { instituteId: string; ticketId: string; operation: Operation; onRefresh: () => Promise<boolean>; onRecorded: () => void };
export function PaymentRecovery(props: Props) {
  return <Recovery key={JSON.stringify([props.instituteId, props.ticketId, props.operation.id, getAccessToken()])} {...props} />;
}
function Recovery({ instituteId, ticketId, operation, onRefresh, onRecorded }: Props) {
  const token = getAccessToken(), actor = getOperatorSubject(), role = getOperatorRole();
  const allowed = !!actor && actor === operation.actor_id && ["accueil", "responsable_institut"].includes(role || "") &&
    (operation.kind !== "refund" || role === "responsable_institut") && ["prepared", "unknown", "pending"].includes(operation.status);
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const generation = useRef(0), pending = useRef(false);
  const callbacks = useRef({ onRefresh, onRecorded }); callbacks.current = { onRefresh, onRecorded };
  useEffect(() => { generation.current++; return () => { generation.current++; }; }, []);
  async function recover() {
    if (!allowed || pending.current) return;
    const lifetime = generation.current;
    const current = () => lifetime === generation.current && token === getAccessToken();
    pending.current = true; setBusy(true); setError(undefined);
    const base = `/payments/institutes/${encodeURIComponent(instituteId)}`;
    try {
      // The durable original ID is the recovery handle; never create another intent.
      const result = await apiPost<Operation>(`${base}/intents/${encodeURIComponent(operation.id)}/dispatch`);
      if (!current()) return;
      const terminal = ({ authorize: "authorized", capture: "captured", cancel: "cancelled", refund: "refunded" } as Record<string, string>)[operation.kind];
      if (!result || result.id !== operation.id || result.kind !== operation.kind || result.amount !== operation.amount || result.currency !== operation.currency ||
          ![terminal, "pending", "failed"].includes(result.status)) throw new Error("Réponse de paiement incohérente. Conservez l'opération d'origine.");
      const snapshot = await apiGet<{ ticket_id: string; operations: Operation[] }>(`${base}/tickets/${encodeURIComponent(ticketId)}/snapshot`);
      if (!current()) return;
      const matching = Array.isArray(snapshot?.operations) ? snapshot.operations.filter(row => row.id === operation.id) : [];
      const fact = matching[0];
      if (snapshot?.ticket_id !== ticketId || matching.length !== 1 || fact.kind !== operation.kind || fact.actor_id !== actor || fact.amount !== operation.amount ||
          fact.currency !== operation.currency || ![terminal, "pending", "failed"].includes(fact.status) ||
          (result.status !== "pending" && fact.status !== result.status)) throw new Error("Actualisez les paiements pour vérifier le résultat enregistré.");
      if (!await callbacks.current.onRefresh()) throw new Error("Actualiser le ticket et ses soldes avant de poursuivre");
      if (current()) callbacks.current.onRecorded();
    } catch (failure) {
      if (current()) setError(`${failure instanceof Error ? failure.message : "Paiement indisponible"} Reprenez cette même opération.`);
    } finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  if (!allowed) return null;
  return <div>
    {error && <p role="alert">{error}</p>}
    <button type="button" disabled={busy} onClick={() => void recover()}>{busy ? "Récupération du résultat…" : "Reprendre cette opération"}</button>
  </div>;
}
