import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";

type Intent = { employee_id: string; method: "cb" | "especes" | "cheque" };
type Operation = { id: string; kind: string; status: string; applied: boolean; actor_id?: string; amount: string; currency: string };
type Props = { instituteId: string; ticketId: string; operation: Operation; employeeId?: string; method?: string; onRefresh: () => Promise<boolean>; onRecorded: () => void };
function valid(value: Intent) {
  return !!value && typeof value.employee_id === "string" && !!value.employee_id.trim() && value.employee_id === value.employee_id.trim() && value.employee_id.length <= 80 &&
    ["cb", "especes", "cheque"].includes(value.method);
}
function recover(key: string): Intent | undefined {
  try { const row = JSON.parse(sessionStorage.getItem(key) || "null"); return valid(row) ? { employee_id: row.employee_id, method: row.method } : undefined; } catch { return; }
}
export function CapturedCheckout(props: Props) {
  return <Checkout key={JSON.stringify([props.instituteId, props.ticketId, props.operation.id, getAccessToken()])} {...props} />;
}
function Checkout({ instituteId, ticketId, operation, employeeId, method, onRefresh, onRecorded }: Props) {
  const token = getAccessToken(), actor = getOperatorSubject(), role = getOperatorRole();
  const allowed = !!actor && actor === operation.actor_id && ["accueil", "responsable_institut"].includes(role || "") && operation.kind === "capture" && operation.status === "captured" && !operation.applied;
  const key = `flowpilot.capture-checkout:${JSON.stringify([instituteId, ticketId, operation.id, actor])}`;
  const [intent, setIntent] = useState<Intent | undefined>(() => allowed ? recover(key) : undefined);
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const lifetime = useRef(0), pending = useRef(false);
  const callbacks = useRef({ onRefresh, onRecorded }); callbacks.current = { onRefresh, onRecorded };
  useEffect(() => { lifetime.current++; return () => { lifetime.current++; }; }, []);
  async function apply() {
    if (!allowed || pending.current) return;
    const row = intent || { employee_id: employeeId || "", method: method as Intent["method"] };
    if (!valid(row)) return;
    const generation = lifetime.current;
    const current = () => generation === lifetime.current && token === getAccessToken();
    pending.current = true; setBusy(true); setIntent(row); setError(undefined);
    const base = `/payments/institutes/${encodeURIComponent(instituteId)}`;
    try {
      sessionStorage.setItem(key, JSON.stringify(row));
      const result = await apiPost<{ ticket_id: string; status: string }>(`${base}/intents/${encodeURIComponent(operation.id)}/checkout`, row);
      if (!current()) return;
      if (!result || result.ticket_id !== ticketId || result.status !== "paid") throw new Error("Clôture du ticket à vérifier");
      const snapshot = await apiGet<{ ticket_id: string; operations: Operation[] }>(`${base}/tickets/${encodeURIComponent(ticketId)}/snapshot`);
      if (!current()) return;
      const matching = Array.isArray(snapshot?.operations) ? snapshot.operations.filter(value => value.id === operation.id) : [];
      const fact = matching[0];
      if (snapshot?.ticket_id !== ticketId || matching.length !== 1 || fact.kind !== "capture" || fact.status !== "captured" || fact.applied !== true ||
          fact.actor_id !== actor || fact.amount !== operation.amount || fact.currency !== operation.currency) throw new Error("Application de la capture à vérifier");
      if (!await callbacks.current.onRefresh()) throw new Error("Actualiser le ticket et ses soldes avant de poursuivre");
      if (!current()) return;
      sessionStorage.removeItem(key); setIntent(undefined); callbacks.current.onRecorded();
    } catch (failure) {
      if (current()) setError(`${failure instanceof Error ? failure.message : "Clôture indisponible"}. Reprenez la clôture conservée.`);
    } finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  if (!allowed) return null;
  const ready = !!intent || valid({ employee_id: employeeId || "", method: method as Intent["method"] });
  return <div>
    {error && <p role="alert">{error}</p>}
    {intent ? <p>Clôture conservée avec l'employée d'origine · {({ cb: "CB", especes: "Espèces", cheque: "Chèque" })[intent.method]}</p> : <p>Appliquer cet encaissement avec l'employée de caisse et le mode sélectionnés.</p>}
    <button type="button" disabled={busy || !ready} onClick={() => void apply()}>{intent ? "Reprendre la clôture conservée" : "Appliquer l'encaissement en caisse"}</button>
  </div>;
}
