import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { PaymentPreparation } from "./PaymentPreparation";
type Props = { instituteId: string; ticketId: string; onRefresh: () => Promise<boolean>; onRecorded: () => void };
type Quote = { ticket_id: string; amount: string; currency: string };
export function AuthorizationPreparation(props: Props) {
  return <Authorization key={JSON.stringify([props.instituteId, props.ticketId, getAccessToken()])} {...props} />;
}
function Authorization({ instituteId, ticketId, onRefresh, onRecorded }: Props) {
  const token = getAccessToken(), allowed = ["accueil", "responsable_institut"].includes(getOperatorRole() || "");
  const [quote, setQuote] = useState<Quote>(), [error, setError] = useState<string>(), [loading, setLoading] = useState(false);
  const lifetime = useRef(0), sequence = useRef(0);
  async function load() {
    if (!allowed) return;
    const generation = lifetime.current, request = ++sequence.current;
    const current = () => generation === lifetime.current && request === sequence.current && token === getAccessToken();
    setQuote(undefined); setError(undefined); setLoading(true);
    try {
      const value = await apiGet<Quote>(`/payments/institutes/${encodeURIComponent(instituteId)}/tickets/${encodeURIComponent(ticketId)}/authorization-quote`);
      if (!value || value.ticket_id !== ticketId || typeof value.amount !== "string" || !/^\d{1,8}\.\d{2}$/.test(value.amount) || Number(value.amount) <= 0 || !["CHF", "EUR"].includes(value.currency)) throw new Error("Montant à autoriser incohérent");
      if (current()) setQuote(value);
    } catch (failure) { if (current()) setError(failure instanceof Error ? failure.message : "Montant indisponible"); }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { lifetime.current++; void load(); return () => { lifetime.current++; }; }, []);
  if (!allowed) return null;
  return <section aria-label="Autorisation du paiement">
    {error && <p role="alert">{error}</p>}
    <button type="button" disabled={loading} onClick={() => void load()}>Actualiser le montant à autoriser</button>
    {quote && <><p>Reste à autoriser : {quote.amount.replace(".", ",")} {quote.currency}</p><PaymentPreparation instituteId={instituteId} ticketId={ticketId} parent={{ id: ticketId, amount: quote.amount, currency: quote.currency }} kind="authorize" onRefresh={onRefresh} onRecorded={onRecorded} /></>}
  </section>;
}
