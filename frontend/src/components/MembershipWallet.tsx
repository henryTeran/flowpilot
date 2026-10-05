import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { readUtcDate } from "../api/dates";
import { getAccessToken, getOperatorRole } from "../api/session";
import type { QueueTicket, Service } from "../types";

type Membership = { id: string; name: string; status: string; active_until: string };
type Benefit = { id: string; ticket_line_id: string; reversed_at: string | null };

export function MembershipWallet({ ticket, services, blocked, excludedLines, beginMutation, onRefresh, onBusy, onCoverage }: {
  ticket: QueueTicket; services: Service[]; blocked: boolean; excludedLines: string[];
  beginMutation: () => (() => void) | null; onRefresh: () => Promise<boolean>;
  onBusy: (value: boolean) => void; onCoverage: (active: string[], historical: string[]) => void;
}) {
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [history, setHistory] = useState<Benefit[]>([]);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();
  const lifetime = useRef(0);
  const sequence = useRef(0);
  const pending = useRef(false);
  const keys = useRef(new Map<string, string>());
  const callbacks = useRef({ onRefresh, onBusy, onCoverage }); callbacks.current = { onRefresh, onBusy, onCoverage };
  const token = getAccessToken();
  const manager = getOperatorRole() === "responsable_institut";
  const prefix = `/memberships/institutes/${encodeURIComponent(ticket.institute_id)}`;
  function capture() { const epoch = lifetime.current; return () => epoch === lifetime.current && token === getAccessToken(); }
  async function reload() {
    const current = capture();
    const request = ++sequence.current;
    const list = await apiGet<Membership[]>(`${prefix}?customer_id=${encodeURIComponent(ticket.customer_id || "")}`);
    if (!current() || request !== sequence.current) return false;
    const rows = (await Promise.all(list.map(row => apiGet<Benefit[]>(`${prefix}/${row.id}/benefits`)))).flat();
    if (!current() || request !== sequence.current) return false;
    setMemberships(list); setHistory(rows); setLoaded(true);
    const relevant = rows.filter(row => ticket.lines?.some(line => line.id === row.ticket_line_id));
    callbacks.current.onCoverage(relevant.filter(row => !row.reversed_at).map(row => row.ticket_line_id), relevant.map(row => row.ticket_line_id));
    return true;
  }
  useEffect(() => { lifetime.current++; return () => { lifetime.current++; }; }, []);
  useEffect(() => {
    const current = capture();
    void reload().catch(reason => { if (current()) setError(reason instanceof Error ? reason.message : "Abonnements indisponibles"); });
  }, [ticket]);
  async function reconcile() {
    const current = capture();
    if (!await reload() || !current()) return false;
    const refreshed = await callbacks.current.onRefresh();
    return current() && refreshed;
  }
  async function act(path?: string, payload?: object) {
    if (pending.current || (path && blocked)) return;
    const release = beginMutation();
    if (!release) return;
    const current = capture();
    pending.current = true; setBusy(true); callbacks.current.onBusy(true); setError(undefined);
    let reconciled = false;
    try {
      if (path) await apiPost(path, payload);
      if (!current()) return;
      reconciled = await reconcile();
      if (!reconciled) throw new Error("Actualiser les montants avant de payer");
    } catch (reason) {
      if (!current()) return;
      setError(reason instanceof Error ? reason.message : "Action indisponible");
      if (path && current()) { try { reconciled = await reconcile(); } catch {} }
    } finally {
      release(); pending.current = false;
      if (current()) { setBusy(false); callbacks.current.onBusy(!reconciled); }
    }
  }
  const active = history.filter(row => !row.reversed_at && ticket.lines?.some(line => line.id === row.ticket_line_id));
  const editable = ["ready_for_checkout", "in_checkout"].includes(ticket.status);
  return <section className="package-wallet" aria-label="Abonnements de la cliente"><h3>Abonnements de la cliente</h3>
    {memberships.map(row => <div key={row.id}><strong>{row.name}</strong><span>{row.status === "active" ? "Actif" : row.status === "scheduled" ? "À venir" : "Expiré"} · {readUtcDate(row.active_until).toLocaleString("fr")}</span>
      {row.status === "active" && editable && ticket.lines?.filter(line => {
        const price = services.find(service => service.id === line.service_id)?.price_member;
        return line.performed_by_employee_id && price != null && Number.isFinite(Number(price)) && Number(price) >= 0
          && Number(price) < Number(line.unit_price) && !excludedLines.includes(line.id) && !active.some(fact => fact.ticket_line_id === line.id);
      }).map(line => <button key={line.id} type="button" disabled={busy || blocked} onClick={() => {
        const intent = `${row.id}:${line.id}`;
        if (!keys.current.has(intent)) keys.current.set(intent, crypto.randomUUID());
        void act(`${prefix}/${row.id}/benefits`, { ticket_line_id: line.id, idempotency_key: keys.current.get(intent) });
      }}>Appliquer le tarif membre · {services.find(service => service.id === line.service_id)?.name}</button>)}
    </div>)}
    {manager && editable && active.map(row => <button type="button" key={row.id} disabled={busy || blocked} onClick={() => {
      keys.current.clear(); void act(`${prefix}/benefits/${row.id}/reverse`, { reason: "Correction du tarif membre en caisse" });
    }}>Annuler le tarif membre</button>)}
    {loaded && !memberships.length && <p>Aucun abonnement enregistré</p>}{error && <p role="alert">{error}</p>}
    <button type="button" disabled={busy} onClick={() => void act()}>Actualiser les abonnements en caisse</button>
  </section>;
}
