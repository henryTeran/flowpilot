import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { readUtcDate } from "../api/dates";
import { getAccessToken, getOperatorRole } from "../api/session";
import type { Customer } from "../types";

type Plan = { id: string; name: string; valid_days: number };
type Membership = { id: string; name: string; active_from: string; active_until: string; status: string };
type Renewal = { id: string; occurred_at: string; active_until: string };

export function MembershipManagement({ instituteId, customer, disabled, onBusy }: {
  instituteId: string; customer?: Customer; disabled: boolean; onBusy: (value: boolean) => void;
}) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [history, setHistory] = useState<Record<string, Renewal[]>>({});
  const [name, setName] = useState("");
  const [days, setDays] = useState("30");
  const [planId, setPlanId] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();
  const [message, setMessage] = useState<string>();
  const lifetime = useRef(0);
  const reads = useRef(0);
  const pending = useRef(false);
  const intents = useRef(new Map<string, { fingerprint: string; key: string }>());
  const callbacks = useRef({ onBusy }); callbacks.current = { onBusy };
  const token = getAccessToken();
  const manager = getOperatorRole() === "responsable_institut";
  const prefix = `/memberships/institutes/${encodeURIComponent(instituteId)}`;
  function capture() { const epoch = lifetime.current; return () => epoch === lifetime.current && token === getAccessToken(); }
  async function reload() {
    const current = capture();
    const request = ++reads.current;
    const [list, rights] = await Promise.all([
      apiGet<Plan[]>(`${prefix}/plans`), customer ? apiGet<Membership[]>(`${prefix}?customer_id=${encodeURIComponent(customer.id)}`) : Promise.resolve([]),
    ]);
    if (!current() || request !== reads.current) return false;
    const renewals = await Promise.all(rights.map(row => apiGet<Renewal[]>(`${prefix}/${row.id}/history`)));
    if (!current() || request !== reads.current) return false;
    setPlans(list); setMemberships(rights); setHistory(Object.fromEntries(rights.map((row, index) => [row.id, renewals[index]]))); setLoaded(true);
    return true;
  }
  useEffect(() => {
    lifetime.current++;
    const current = capture();
    void reload().catch(reason => { if (current()) setError(reason instanceof Error ? reason.message : "Abonnements indisponibles"); });
    return () => { lifetime.current++; };
  }, []);
  async function write(kind: "plan" | "issue" | "renew", identifier?: string) {
    if (pending.current || disabled || !manager) return;
    const current = capture();
    const payload = kind === "plan" ? { name: name.trim(), valid_days: Number(days) }
      : kind === "issue" ? { plan_id: planId, customer_id: customer?.id } : {};
    const slot = `${kind}:${identifier || ""}`;
    const fingerprint = JSON.stringify({ instituteId, identifier, ...payload });
    let intent = intents.current.get(slot);
    if (!intent || intent.fingerprint !== fingerprint) {
      intent = { fingerprint, key: crypto.randomUUID() }; intents.current.set(slot, intent);
    }
    pending.current = true; reads.current++; setBusy(true); callbacks.current.onBusy(true); setError(undefined); setMessage(undefined);
    try {
      await apiPost(kind === "plan" ? `${prefix}/plans` : kind === "issue" ? prefix : `${prefix}/${identifier}/renew`,
        { ...payload, idempotency_key: intent.key });
      if (!current()) return;
      if (!await reload()) throw new Error("Actualiser les abonnements avant de poursuivre");
      if (!current()) return;
      intents.current.delete(slot);
      if (kind === "plan") setName("");
      if (kind === "issue") setPlanId("");
      setMessage(kind === "plan" ? "Formule configurée" : kind === "issue" ? "Abonnement attribué" : "Abonnement renouvelé");
    } catch (reason) {
      if (current()) setError(`${reason instanceof Error ? reason.message : "Opération indisponible"}. Réessayez la même opération pour la récupérer sans doublon.`);
    } finally { if (current()) { pending.current = false; setBusy(false); callbacks.current.onBusy(false); } }
  }
  const active = memberships.some(row => row.status === "active");
  async function refresh() {
    if (pending.current || disabled) return;
    const current = capture();
    pending.current = true; setBusy(true); callbacks.current.onBusy(true);
    try {
      if (await reload() && current()) setError(undefined);
    } catch (reason) { if (current()) setError(reason instanceof Error ? reason.message : "Actualisation impossible"); }
    finally { if (current()) { pending.current = false; setBusy(false); callbacks.current.onBusy(false); } }
  }
  return <section className="membership-management" aria-label="Gestion des abonnements">
    <h2>Abonnements</h2><p>Les droits donnent accès aux tarifs membres déclarés. Attribution et renouvellement ne constituent pas une vente encaissée.</p>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {manager && <form onSubmit={event => { event.preventDefault(); void write("plan"); }}><fieldset disabled={busy || disabled}>
      <h3>Configurer une formule</h3><label>Nom de la formule<input maxLength={120} value={name} onChange={event => setName(event.target.value)} /></label>
      <label>Validité en jours<input type="number" min="1" max="3650" step="1" value={days} onChange={event => setDays(event.target.value)} /></label>
      <button type="submit" disabled={!name.trim() || !Number.isInteger(Number(days)) || Number(days) < 1 || Number(days) > 3650}>Créer la formule</button>
    </fieldset></form>}
    <div className="commerce-plans">{plans.map(plan => <article key={plan.id}><strong>{plan.name}</strong><p>{plan.valid_days} jours</p></article>)}</div>
    {customer ? <><h3>Abonnements de {customer.display_name}</h3>
      {manager && <fieldset disabled={busy || disabled}><label>Formule<select value={planId} onChange={event => setPlanId(event.target.value)}><option value="">Choisir</option>
        {plans.map(plan => <option key={plan.id} value={plan.id}>{plan.name} · {plan.valid_days} jours</option>)}</select></label>
        <button type="button" disabled={!planId || active} onClick={() => void write("issue")}>Attribuer l’abonnement</button></fieldset>}
      {loaded && !memberships.length && <p>Aucun abonnement enregistré</p>}
      {memberships.map(row => <article key={row.id}><strong>{row.name}</strong><p>{row.status === "active" ? "Actif" : row.status === "scheduled" ? "À venir" : "Expiré"} · validité jusqu’au {readUtcDate(row.active_until).toLocaleString("fr")}</p>
        {manager && <button type="button" disabled={busy || disabled || (active && row.status !== "active")}
          onClick={() => void write("renew", row.id)}>Renouveler {row.name}</button>}
        {!!history[row.id]?.length && <details><summary>Historique des renouvellements</summary>{history[row.id].map(fact => <p key={fact.id}>
          {readUtcDate(fact.occurred_at).toLocaleString("fr")} · nouvelle échéance {readUtcDate(fact.active_until).toLocaleString("fr")}</p>)}</details>}
      </article>)}</> : <p>Sélectionnez une cliente ci-dessus pour consulter ou attribuer un abonnement.</p>}
    <button type="button" disabled={busy || disabled} onClick={() => void refresh()}>Actualiser les abonnements</button>
  </section>;
}
