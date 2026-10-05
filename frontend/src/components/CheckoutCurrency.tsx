import { useEffect, useRef, useState } from "react";
import { apiGet, apiPatch } from "../api/client";
import { getAccessToken } from "../api/session";
import type { QueueTicket } from "../types";

export function CheckoutCurrency({ ticket, blocked, onRefresh, onBusy, beginMutation }: {
  ticket: QueueTicket; blocked: boolean; onRefresh: () => Promise<boolean>;
  onBusy: (value: boolean) => void; beginMutation: () => (() => void) | null;
}) {
  const [currency, setCurrency] = useState<"CHF" | "EUR">();
  const [reason, setReason] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<string>();
  const [pending, setPending] = useState(false);
  const epoch = useRef(0), writing = useRef(false), reads = useRef(0);
  const callbacks = useRef({ onBusy, onRefresh, beginMutation }); callbacks.current = { onBusy, onRefresh, beginMutation };
  const token = getAccessToken();
  const prefix = `/gift-cards/institutes/${encodeURIComponent(ticket.institute_id)}`;
  function capture() { const stamp = epoch.current; return () => stamp === epoch.current && token === getAccessToken(); }
  useEffect(() => {
    epoch.current++; writing.current = false; setPending(false); setUncertain(false); setError(undefined); setCurrency(undefined); setReason("");
    const current = capture(), read = ++reads.current;
    if (!ticket.currency && ticket.status !== "paid") apiGet<{ currency: "CHF" | "EUR" }>(`${prefix}/settings`)
      .then(value => { if (current() && read === reads.current) setCurrency(value.currency); })
      .catch(failure => { if (current() && read === reads.current) setError(`${failure.message || failure}. Configurez ou vérifiez la devise dans Offres.`); });
    return () => { epoch.current++; reads.current++; };
  }, [ticket.id, ticket.institute_id, token]);

  async function confirm(refreshOnly = false) {
    if (writing.current || (!refreshOnly && (blocked || !currency || reason.trim().length < 3))) return;
    const release = callbacks.current.beginMutation();
    if (!release) return;
    const current = capture(); writing.current = true; setPending(true); setUncertain(true); callbacks.current.onBusy(true); setError(undefined);
    try {
      if (!refreshOnly) await apiPatch(`/tickets/${encodeURIComponent(ticket.id)}/currency`, { currency, reason: reason.trim() });
      if (!current()) return;
      if (!await callbacks.current.onRefresh()) throw new Error("Actualiser complètement le ticket avant de payer");
      if (!current()) return;
      setUncertain(false); callbacks.current.onBusy(false);
    } catch (failure) {
      if (current()) setError(`${failure instanceof Error ? failure.message : "Confirmation indisponible"}. Actualisez le ticket pour vérifier la devise enregistrée.`);
    } finally { release(); if (current()) { writing.current = false; setPending(false); } }
  }
  if (ticket.currency && !uncertain) return null;
  if (ticket.status === "paid" && !uncertain) return null;
  return <section aria-label="Devise du ticket">
    <p>La devise de ce ticket historique doit être confirmée avant l’utilisation d’une carte cadeau ou d’un nouveau tarif.</p>
    {error && <p role="alert">{error}</p>}
    {!uncertain && <fieldset disabled={pending || blocked || !currency}>
      <p>{currency ? `Devise configurée : ${currency}` : "Devise non vérifiée"}</p>
      <label>Motif de confirmation de devise<input maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label>
      <button type="button" disabled={reason.trim().length < 3} onClick={() => void confirm()}>Confirmer la devise {currency || ""}</button>
    </fieldset>}
    {uncertain && <button type="button" disabled={pending} onClick={() => void confirm(true)}>Actualiser la devise du ticket</button>}
  </section>;
}
