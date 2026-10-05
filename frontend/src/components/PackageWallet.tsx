import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getAccessToken } from "../api/session";
import type { Customer, QueueTicket } from "../types";

type Package = { id: string; name: string; service_id: string; remaining: number; usable_sessions: number; status: string; expires_at: string };
type Redemption = { id: string; ticket_line_id: string; reversed_at: string | null };

export function PackageWallet({ ticket, onRefresh, onBusy, onCustomer, onCoverage }: {
  ticket: QueueTicket; onRefresh: () => Promise<boolean>; onBusy: (busy: boolean) => void;
  onCustomer: (customer: Customer) => void;
  onCoverage: (active: string[], historical: string[]) => void;
}) {
  const [packages, setPackages] = useState<Package[]>([]);
  const [history, setHistory] = useState<Redemption[]>([]);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  const mutating = useRef(false);
  const readSequence = useRef(0);
  const keys = useRef(new Map<string, string>());
  const callbacks = useRef({ onRefresh, onBusy, onCustomer, onCoverage });
  callbacks.current = { onRefresh, onBusy, onCustomer, onCoverage };
  const prefix = `/commerce/institutes/${encodeURIComponent(ticket.institute_id)}`;
  const token = getAccessToken();
  const current = () => alive.current && token === getAccessToken();
  let manager = false;
  try { manager = JSON.parse(atob((token || "").split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))).role === "responsable_institut"; } catch {}
  async function reload() {
    const request = ++readSequence.current;
    try {
    const list = await apiGet<Package[]>(`${prefix}/packages?customer_id=${encodeURIComponent(ticket.customer_id || "")}`);
    const rows = await Promise.all(list.map(item => apiGet<Redemption[]>(`${prefix}/packages/${item.id}/history`)));
    if (!current() || request !== readSequence.current) return;
    setPackages(list); setHistory(rows.flat());
    const relevant = rows.flat().filter(row => ticket.lines?.some(line => line.id === row.ticket_line_id));
    callbacks.current.onCoverage(relevant.filter(row => !row.reversed_at).map(row => row.ticket_line_id),
      relevant.map(row => row.ticket_line_id));
    } catch (reason) { if (current() && request === readSequence.current) throw reason; }
  }
  useEffect(() => {
    alive.current = true;
    if (!ticket.customer_id) return;
    apiGet<Customer>(`/customers/institutes/${encodeURIComponent(ticket.institute_id)}/${encodeURIComponent(ticket.customer_id)}`)
      .then(customer => { if (current()) callbacks.current.onCustomer(customer); }).catch(() => {});
    return () => { alive.current = false; };
  }, []);
  useEffect(() => {
    if (ticket.customer_id) void reload().catch(reason => { if (current()) setError(reason instanceof Error ? reason.message : "Forfaits indisponibles"); });
  }, [ticket]);
  async function act(path: string, payload: object) {
    if (mutating.current) return;
    mutating.current = true;
    setBusy(true); callbacks.current.onBusy(true); setError(undefined);
    let reconciled = false;
    try {
      await apiPost(path, payload);
      if (!current()) return;
      await reload(); if (!current()) return;
      reconciled = await callbacks.current.onRefresh();
      if (!reconciled) throw new Error("Actualiser les montants avant de payer.");
    } catch (reason) {
      if (current()) setError(reason instanceof Error ? reason.message : "Action impossible");
      // Recover committed writes after a lost response before displaying prices.
      if (current()) { try { await reload(); reconciled = await callbacks.current.onRefresh(); } catch {} }
    } finally { mutating.current = false; if (current()) { setBusy(false); callbacks.current.onBusy(!reconciled); } }
  }
  async function refresh() {
    if (mutating.current) return;
    mutating.current = true; callbacks.current.onBusy(true);
    setBusy(true);
    try {
      await reload();
      if (!current()) return;
      const reconciled = await callbacks.current.onRefresh();
      if (current()) {
        if (reconciled) { setError(undefined); callbacks.current.onBusy(false); }
        else setError("Actualiser les montants avant de payer.");
      }
    } catch (reason) { if (current()) setError(reason instanceof Error ? reason.message : "Actualisation impossible"); }
    finally { mutating.current = false; if (current()) setBusy(false); }
  }
  const active = history.filter(row => !row.reversed_at && ticket.lines?.some(line => line.id === row.ticket_line_id));
  return <section className="package-wallet" aria-label="Forfaits de la cliente">
    <h3>Forfaits de la cliente</h3>
    {packages.map(item => {
      const line = ticket.lines?.find(line => line.service_id === item.service_id && line.performed_by_employee_id
        && line.quantity <= item.usable_sessions && !active.some(row => row.ticket_line_id === line.id));
      return <div key={item.id}><strong>{item.name}</strong><span> {item.remaining} séance(s) · {item.status === "expired" ? "Expiré" : new Date(item.expires_at).toLocaleDateString("fr")}</span>
        {line && ["ready_for_checkout", "in_checkout"].includes(ticket.status) && <button type="button" disabled={busy} onClick={() => {
          const intent = `${item.id}:${line.id}`;
          if (!keys.current.has(intent)) keys.current.set(intent, crypto.randomUUID());
          void act(`${prefix}/packages/${item.id}/consume`, { ticket_line_id: line.id, idempotency_key: keys.current.get(intent) });
        }}>Utiliser {line.quantity} séance(s)</button>}</div>;
    })}
    {manager && ["ready_for_checkout", "in_checkout"].includes(ticket.status) && active.map(row => <button key={row.id} type="button" disabled={busy} onClick={() => {
      void act(`${prefix}/package-redemptions/${row.id}/reverse`, { reason: "Correction du forfait en caisse" });
      keys.current.clear();
    }}>Annuler la consommation</button>)}
    {!packages.length && !error && <p>Aucun forfait enregistré.</p>}
    {error && <p role="alert">{error}</p>}
    <button type="button" disabled={busy} onClick={() => void refresh()}>Actualiser les forfaits</button>
  </section>;
}
