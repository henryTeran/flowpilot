import { useEffect, useRef, useState } from "react";
import { ApiError, apiGet, apiPost } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import type { QueueTicket } from "../types";

type Money = string | number;
type Allocation = { id: string; card_id: string; amount: Money; currency: string; reversed_at: string | null };
export type GiftTender = { ticket_id: string; currency: "CHF" | "EUR" | null; total: Money; gift_amount: Money;
  remaining_due: Money; remainder_amount: Money; remainder_method: string | null; allocations: Allocation[] };
type Card = { id: string; currency: "CHF" | "EUR"; remaining: Money; usable_amount: Money; status: string };
type Operation = { path: string; payload: object; label: string };

function readRecovery(raw: string, prefix: string, ticketId: string): Operation {
  const saved = JSON.parse(raw);
  if (typeof saved.path !== "string" || !saved.path.startsWith(`${prefix}/`) || !saved.payload) throw new Error("Demande cadeau à vérifier");
  const payload = saved.payload;
  const suffix = saved.path.slice(prefix.length);
  if (/^\/[^/]+\/allocations$/.test(suffix) && payload.ticket_id === ticketId
      && typeof payload.amount === "string" && /^\d{1,8}(\.\d{1,2})?$/.test(payload.amount) && cents(payload.amount) > 0
      && typeof payload.idempotency_key === "string" && payload.idempotency_key.trim().length > 0 && payload.idempotency_key.length <= 120) {
    return { path: saved.path, label: "Réessayer ce débit cadeau", payload: { ticket_id: ticketId, amount: payload.amount, idempotency_key: payload.idempotency_key } };
  }
  if (/^\/allocations\/[^/]+\/reverse$/.test(suffix) && typeof payload.reason === "string"
      && payload.reason.trim().length >= 3 && payload.reason.length <= 240) {
    return { path: saved.path, label: "Réessayer cette annulation cadeau", payload: { reason: payload.reason } };
  }
  throw new Error("Demande cadeau incompatible avec ce ticket");
}

export function cents(value: Money) {
  const match = /^(\d{1,10})(?:\.(\d{1,2}))?$/.exec(String(value));
  if (!match) throw new Error("Montant serveur invalide");
  return Number(match[1]) * 100 + Number((match[2] || "").padEnd(2, "0"));
}
export function giftMoney(value: Money, currency: string | null) {
  return `${(cents(value) / 100).toLocaleString("fr", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${currency ? ` ${currency}` : ""}`;
}

export function GiftCardWallet({ ticket, blocked, onRefresh, onBusy, onTender, beginMutation }: {
  ticket: QueueTicket; blocked: boolean; onRefresh: () => Promise<boolean>; onBusy: (value: boolean) => void;
  onTender: (value: GiftTender) => void; beginMutation: () => (() => void) | null;
}) {
  const [view, setView] = useState<GiftTender>();
  const [card, setCard] = useState<Card>();
  const [code, setCode] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("Correction du paiement cadeau en caisse");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(true);
  const [retry, setRetry] = useState<Operation>();
  const epoch = useRef(0), reads = useRef(0), writing = useRef(false);
  const bearer = useRef("");
  const operation = useRef<Operation | undefined>(undefined);
  const callbacks = useRef({ onRefresh, onBusy, onTender, beginMutation }); callbacks.current = { onRefresh, onBusy, onTender, beginMutation };
  const token = getAccessToken();
  const prefix = `/gift-cards/institutes/${encodeURIComponent(ticket.institute_id)}`;
  const manager = getOperatorRole() === "responsable_institut";
  const subject = getOperatorSubject();
  const recoveryKey = subject ? `flowpilot.gift-tender:${encodeURIComponent(ticket.institute_id)}:${encodeURIComponent(ticket.id)}:${encodeURIComponent(subject)}` : undefined;
  function capture() { const stamp = epoch.current; return () => stamp === epoch.current && token === getAccessToken(); }
  async function reload() {
    const current = capture(), request = ++reads.current;
    const value = await apiGet<GiftTender>(`${prefix}/tickets/${encodeURIComponent(ticket.id)}/tenders`);
    if (!current() || request !== reads.current) return false;
    if (value.ticket_id !== ticket.id || !Array.isArray(value.allocations)
        || cents(value.gift_amount) + cents(value.remainder_amount) + cents(value.remaining_due) !== cents(value.total)) throw new Error("Paiements cadeaux non vérifiés");
    let updated: Card | undefined;
    if (bearer.current) updated = await apiPost<Card>(`${prefix}/lookup`, { code: bearer.current });
    if (!current() || request !== reads.current) return false;
    setView(value); if (updated) setCard(updated); callbacks.current.onTender(value); return true;
  }
  useEffect(() => {
    epoch.current++; reads.current++; writing.current = false; bearer.current = ""; operation.current = undefined;
    setView(undefined); setCard(undefined); setCode(""); setAmount(""); setRetry(undefined); setError(undefined); setBusy(true);
    if (recoveryKey) {
      try {
        const raw = sessionStorage.getItem(recoveryKey);
        if (raw) {
          const saved = readRecovery(raw, prefix, ticket.id);
          operation.current = saved; setRetry(saved);
        }
      } catch (failure) { setError(failure instanceof Error ? failure.message : "Récupération indisponible"); }
    }
    callbacks.current.onBusy(true);
    return () => { epoch.current++; reads.current++; };
  }, [ticket.id, ticket.institute_id, token]);
  useEffect(() => {
    if (writing.current) return;
    const current = capture(); callbacks.current.onBusy(true); setBusy(true);
    void reload().then(loaded => { if (current() && loaded && !writing.current) { callbacks.current.onBusy(!!operation.current); setBusy(false); } })
      .catch(failure => { if (current()) { setBusy(false); setView(undefined); setError(failure instanceof Error ? failure.message : "Paiements non vérifiés"); } });
  }, [ticket.id, ticket.institute_id, token, ticket.total_amount, ticket.currency, ticket.status]);

  async function lookup() {
    if (writing.current || blocked || !code.trim()) return;
    const release = callbacks.current.beginMutation(); if (!release) return;
    const current = capture(); writing.current = true; setBusy(true); callbacks.current.onBusy(true); setError(undefined);
    let reconciled = false;
    try {
      const value = await apiPost<Card>(`${prefix}/lookup`, { code: code.trim() });
      if (!current()) return;
      bearer.current = code.trim(); setCard(value); setCode(""); setAmount("");
      if (!await callbacks.current.onRefresh() || !current()) throw new Error("Actualiser le ticket avant d'utiliser cette carte");
      reconciled = await reload();
    } catch (failure) {
      if (current()) {
        setError(failure instanceof Error ? failure.message : "Carte introuvable");
        try { if (await callbacks.current.onRefresh() && current()) reconciled = await reload(); } catch { /* Explicit refresh remains available. */ }
      }
    }
    finally { release(); if (current()) { writing.current = false; setBusy(false); callbacks.current.onBusy(!reconciled || !!operation.current); } }
  }
  async function mutate(next?: Operation) {
    if (writing.current || blocked) return;
    const selected = next || operation.current;
    if (!selected) return;
    if (selected.path.endsWith("/reverse")) {
      const segments = selected.path.split("/");
      const identifier = segments[segments.length - 2];
      if (!manager || !view?.allocations.some(row => row.id === identifier)) {
        setError("Vérifier ce débit dans l'historique du ticket avec la responsable"); return;
      }
    }
    const release = callbacks.current.beginMutation(); if (!release) return;
    const current = capture(); operation.current = selected; setRetry(selected);
    writing.current = true; reads.current++; setBusy(true); callbacks.current.onBusy(true); setError(undefined);
    let reconciled = false;
    try {
      if (recoveryKey) sessionStorage.setItem(recoveryKey, JSON.stringify(selected));
      await apiPost(selected.path, selected.payload);
      if (!current()) return;
      if (recoveryKey) sessionStorage.removeItem(recoveryKey);
      operation.current = undefined; setRetry(undefined); setAmount("");
      if (!await callbacks.current.onRefresh() || !current()) throw new Error("Actualiser le ticket avant de payer");
      reconciled = await reload();
    } catch (failure) {
      if (!current()) return;
      if (failure instanceof ApiError && failure.status >= 400 && failure.status < 500 && failure.status !== 408) {
        if (recoveryKey) sessionStorage.removeItem(recoveryKey);
        operation.current = undefined; setRetry(undefined);
      }
      setError(`${failure instanceof Error ? failure.message : "Paiement indisponible"}. Vérifiez les paiements enregistrés avant de poursuivre.`);
      try { if (await callbacks.current.onRefresh() && current()) reconciled = await reload(); } catch { /* Explicit recovery stays available. */ }
    } finally { release(); if (current()) { writing.current = false; setBusy(false); callbacks.current.onBusy(!reconciled || !!operation.current); } }
  }
  async function refresh() {
    if (writing.current) return;
    const release = callbacks.current.beginMutation(); if (!release) return;
    const current = capture(); writing.current = true; setBusy(true); callbacks.current.onBusy(true); setError(undefined);
    try {
      if (!await callbacks.current.onRefresh() || !current() || !await reload()) throw new Error("Actualiser complètement les paiements avant de payer");
      if (current()) callbacks.current.onBusy(!!operation.current);
    } catch (failure) { if (current()) setError(failure instanceof Error ? failure.message : "Actualisation indisponible"); }
    finally { release(); if (current()) { writing.current = false; setBusy(false); } }
  }
  const normalized = amount.trim().replace(",", ".");
  const validAmount = /^\d{1,8}(\.\d{1,2})?$/.test(normalized) && cents(normalized) > 0;
  const unpaid = ["ready_for_checkout", "in_checkout"].includes(ticket.status);
  const active = view?.allocations.filter(row => !row.reversed_at) || [];
  return <section className="package-wallet" aria-label="Paiements par carte cadeau">
    <h3>Cartes cadeaux en caisse</h3>
    {view && <p>Crédit utilisé : {giftMoney(view.gift_amount, view.currency)} · Reste à payer : {giftMoney(view.remaining_due, view.currency)}</p>}
    {error && <p role="alert">{error}</p>}
    {unpaid && <><fieldset disabled={busy || blocked || !!retry || !view}>
      <label>Code cadeau<input autoComplete="off" value={code} onChange={event => setCode(event.target.value)} /></label>
      <button type="button" disabled={!code.trim()} onClick={() => void lookup()}>Rechercher la carte cadeau</button>
      {card && <><p>Carte : {giftMoney(card.usable_amount, card.currency)} utilisables · {card.status}</p>
        <label>Montant cadeau à utiliser<input inputMode="decimal" value={amount} onChange={event => setAmount(event.target.value)} /></label>
        <button type="button" disabled={!view || !validAmount || card.currency !== ticket.currency || card.status !== "active"
          || (validAmount && (cents(normalized) > cents(card.usable_amount) || cents(normalized) > cents(view.remaining_due)))} onClick={() => void mutate({
            path: `${prefix}/${encodeURIComponent(card.id)}/allocations`, label: "Réessayer ce débit cadeau",
            payload: { ticket_id: ticket.id, amount: normalized, idempotency_key: crypto.randomUUID() },
          })}>Utiliser ce crédit cadeau</button>
      </>}
    </fieldset>
      {manager && active.length > 0 && <fieldset disabled={busy || blocked || !!retry}>
        <label>Motif d’annulation cadeau<input maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label>
        {active.map(row => <button key={row.id} type="button" disabled={reason.trim().length < 3} onClick={() => void mutate({
          path: `${prefix}/allocations/${encodeURIComponent(row.id)}/reverse`, payload: { reason: reason.trim() }, label: "Réessayer cette annulation cadeau",
        })}>Annuler le débit cadeau {giftMoney(row.amount, row.currency)} · n°{(view?.allocations.findIndex(item => item.id === row.id) ?? 0) + 1}</button>)}
      </fieldset>}
    </>}
    {view?.allocations.filter(row => row.reversed_at).map(row => <p key={row.id}>Débit annulé : {giftMoney(row.amount, row.currency)}</p>)}
    {retry && <button type="button" disabled={busy || blocked} onClick={() => void mutate()}>{retry.label}</button>}
    <button type="button" disabled={busy} onClick={() => void refresh()}>Actualiser les paiements cadeaux</button>
  </section>;
}
