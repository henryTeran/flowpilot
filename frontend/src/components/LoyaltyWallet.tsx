import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import type { QueueTicket } from "../types";

type Reward = { id: string; name: string; service_id: string; currency: string; points_cost: number; minimum_points: number; discount_amount: string };
type Fact = { id: string; ticket_line_id: string; reversed_at: string | null };
type View = { balance: { customer_id: string; points: number }; redemptions: Fact[] };
type Intent = { kind: "apply" | "reverse"; id: string; line: string; key: string };
type Props = { ticket: QueueTicket; blocked: boolean; excludedLines: string[]; beginMutation: () => (() => void) | null;
  onRefresh: () => Promise<boolean>; onBusy: (busy: boolean) => void; onCoverage: (active: string[], historical: string[]) => void };
export function LoyaltyWallet(props: Props) {
  return <Wallet key={JSON.stringify([props.ticket.institute_id, props.ticket.id, props.ticket.customer_id, getAccessToken()])} {...props} />;
}
function Wallet({ ticket, blocked, excludedLines, beginMutation, onRefresh, onBusy, onCoverage }: Props) {
  const token = getAccessToken(), subject = getOperatorSubject();
  const manager = getOperatorRole() === "responsable_institut";
  const prefix = `/loyalty/institutes/${encodeURIComponent(ticket.institute_id)}`;
  const storageKey = `flowpilot.loyalty-checkout:${encodeURIComponent(ticket.institute_id)}:${encodeURIComponent(ticket.id)}:${encodeURIComponent(ticket.customer_id || "")}:${encodeURIComponent(subject || "")}`;
  const [view, setView] = useState<View>(), [rewards, setRewards] = useState<Reward[]>([]), [intent, setIntent] = useState<Intent>();
  const [loaded, setLoaded] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const ticketRef = useRef(ticket); ticketRef.current = ticket;
  const catalogRef = useRef<Reward[]>([]);
  const factsRef = useRef<View | undefined>(undefined);
  const epoch = useRef(0), reads = useRef(0), pending = useRef(false);
  const callbacks = useRef({ onRefresh, onBusy, onCoverage }); callbacks.current = { onRefresh, onBusy, onCoverage };
  function capture() { const generation = epoch.current; return () => generation === epoch.current && token === getAccessToken(); }
  async function reload() {
    const current = capture(), request = ++reads.current;
    const snapshot = await apiGet<View>(`${prefix}/customers/${encodeURIComponent(ticket.customer_id || "")}/snapshot`).catch(reason => {
      if (reason instanceof ApiError && reason.status === 404) return undefined;
      throw reason;
    });
    if (!current() || request !== reads.current) return false;
    if (snapshot && (snapshot.balance?.customer_id !== ticket.customer_id || !Number.isSafeInteger(snapshot.balance.points) || snapshot.balance.points < 0 || snapshot.balance.points > 1e12 || !Array.isArray(snapshot.redemptions) || snapshot.redemptions.some(row => !row || typeof row.id !== "string" || !row.id || typeof row.ticket_line_id !== "string" || !row.ticket_line_id || !(row.reversed_at === null || (typeof row.reversed_at === "string" && row.reversed_at.length > 0))))) throw new Error("Lecture de fidelite incomplete");
    const catalog = snapshot ? await apiGet<Reward[]>(`${prefix}/rewards`) : [];
    if (!current() || request !== reads.current) return false;
    if (!Array.isArray(catalog) || catalog.some(row => !row || typeof row.id !== "string" || !row.id || typeof row.name !== "string" || !row.name ||
        typeof row.service_id !== "string" || !row.service_id || !["CHF", "EUR"].includes(row.currency) ||
        !Number.isSafeInteger(row.points_cost) || row.points_cost <= 0 || row.points_cost > 1e9 ||
        !Number.isSafeInteger(row.minimum_points) || row.minimum_points < 0 || row.minimum_points > 1e9 ||
        typeof row.discount_amount !== "string" || !/^\d{1,8}(\.\d{1,2})?$/.test(row.discount_amount) || Number(row.discount_amount) <= 0)) throw new Error("Recompenses indisponibles");
    catalogRef.current = catalog; factsRef.current = snapshot; setView(snapshot); setRewards(catalog); setLoaded(true);
    const facts = snapshot?.redemptions.filter(row => ticketRef.current.lines?.some(line => line.id === row.ticket_line_id)) || [];
    callbacks.current.onCoverage(facts.filter(row => !row.reversed_at).map(row => row.ticket_line_id), facts.map(row => row.ticket_line_id));
    return true;
  }
  useEffect(() => {
    epoch.current++; const current = capture(); callbacks.current.onBusy(true);
    let saved: Intent | undefined;
    try {
      const row = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      if (row && ["apply", "reverse"].includes(row.kind) && typeof row.id === "string" && row.id.length <= 80 && row.id &&
          typeof row.key === "string" && row.key.length <= 120 && row.key && ticket.lines?.some(line => line.id === row.line)) {
        saved = { kind: row.kind, id: row.id, line: row.line, key: row.key }; setIntent(saved);
      }
    } catch { setError("Recuperation de fidelite indisponible"); }
    void reload().then(ok => {
      if (!current() || !ok) return;
      if ((saved?.kind === "reverse" && !factsRef.current?.redemptions.some(row => row.id === saved?.id && row.ticket_line_id === saved?.line)) ||
          (saved?.kind === "apply" && !catalogRef.current.some(row => row.id === saved?.id))) {
        sessionStorage.removeItem(storageKey); setIntent(undefined); saved = undefined;
      }
      if (!saved) callbacks.current.onBusy(false);
    })
      .catch(reason => { if (current()) setError(String(reason)); });
    return () => { epoch.current++; };
  }, []);
  useEffect(() => {
    if (!loaded || pending.current || intent) return;
    const current = capture();
    setLoaded(false); setView(undefined); setRewards([]); callbacks.current.onBusy(true);
    void reload().then(ok => { if (current() && ok) callbacks.current.onBusy(false); })
      .catch(reason => { if (current()) { setError(String(reason)); callbacks.current.onBusy(true); } });
  }, [ticket]);
  async function act(operation?: Intent) {
    if (pending.current || (operation && blocked && operation !== intent)) return;
    const release = beginMutation(); if (!release) return;
    const current = capture(); pending.current = true; reads.current++; setBusy(true); callbacks.current.onBusy(true); setError(undefined);
    let reconciled = false, known = !operation;
    try {
      if (operation) {
        if (operation.kind === "apply" && !catalogRef.current.some(row => row.id === operation.id)) throw new Error("Recompense hors catalogue de cet institut");
        if (operation.kind === "reverse" && (!manager || !view?.redemptions.some(row => row.id === operation.id && row.ticket_line_id === operation.line))) throw new Error("Annulation hors historique du ticket");
        setIntent(operation); sessionStorage.setItem(storageKey, JSON.stringify(operation));
        await apiPost(operation.kind === "apply" ? `${prefix}/rewards/${encodeURIComponent(operation.id)}/apply` : `${prefix}/redemptions/${encodeURIComponent(operation.id)}/reverse`, operation.kind === "apply" ? { ticket_line_id: operation.line, idempotency_key: operation.key } : { reason: "Correction de recompense en caisse" });
        known = true;
      }
      if (!current()) return;
      if (!await callbacks.current.onRefresh() || !current()) throw new Error("Actualiser les montants avant de payer");
      reconciled = await reload();
      if (!reconciled) throw new Error("Actualiser la fidelite avant de payer");
      if (known && current()) { sessionStorage.removeItem(storageKey); setIntent(undefined); }
    } catch (reason) {
      if (current()) {
        if (reason instanceof ApiError && reason.status >= 400 && reason.status < 500) { sessionStorage.removeItem(storageKey); setIntent(undefined); }
        setError(String(reason));
      }
    } finally {
      release(); if (current()) { pending.current = false; setBusy(false); callbacks.current.onBusy(!reconciled); }
    }
  }
  const active = view?.redemptions.filter(row => !row.reversed_at && ticket.lines?.some(line => line.id === row.ticket_line_id)) || [];
  const editable = ["ready_for_checkout", "in_checkout"].includes(ticket.status);
  return <section aria-label="Fidelite en caisse"><h3>Fidelite en caisse</h3>
    {view && <p>{view.balance.points} points disponibles</p>}{error && <p role="alert">{error}</p>}
    {intent ? <button type="button" disabled={busy || !loaded} onClick={() => void act(intent)}>Reessayer la recompense conservee</button> : <>
      {editable && rewards.flatMap(reward => ticket.lines?.filter(line => line.service_id === reward.service_id && line.performed_by_employee_id &&
        ticket.currency === reward.currency && !excludedLines.includes(line.id) && !active.some(row => row.ticket_line_id === line.id) &&
        view && view.balance.points >= Math.max(reward.minimum_points, reward.points_cost * line.quantity) && Number(line.total) > 0)
        .map(line => <button key={`${reward.id}:${line.id}`} type="button" disabled={busy || blocked || !loaded} onClick={() => void act({ kind: "apply", id: reward.id, line: line.id, key: crypto.randomUUID() })}>Utiliser {reward.name} : {reward.points_cost * line.quantity} points</button>) || [])}
      {manager && editable && active.map(row => <button key={row.id} type="button" disabled={busy || blocked} onClick={() => void act({ kind: "reverse", id: row.id, line: row.ticket_line_id, key: crypto.randomUUID() })}>Annuler la recompense</button>)}
    </>}
    <button type="button" disabled={busy} onClick={() => void act(intent)}>Actualiser la fidelite en caisse</button>
  </section>;
}
