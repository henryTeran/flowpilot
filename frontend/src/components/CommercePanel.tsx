import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { readUtcDate } from "../api/dates";
import { getAccessToken, getOperatorRole } from "../api/session";
import type { Customer, Service } from "../types";
import { CustomerPicker } from "./CustomerPicker";
import { MembershipManagement } from "./MembershipManagement";
import { LoyaltyTiers } from "./LoyaltyTiers";
import { LoyaltyOverview } from "./LoyaltyOverview";
import { GiftCardManagement } from "./GiftCardManagement";

type Plan = { id: string; name: string; service_id: string; sessions: number; valid_days: number };
type Balance = { id: string; name: string; remaining: number; usable_sessions: number; expires_at: string };

export function CommercePanel({ instituteId, services }: { instituteId: string; services: Service[] }) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [customer, setCustomer] = useState<Customer>();
  const [balances, setBalances] = useState<Balance[]>([]);
  const [balancesLoaded, setBalancesLoaded] = useState(false);
  const [name, setName] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [sessions, setSessions] = useState("5");
  const [days, setDays] = useState("90");
  const [planId, setPlanId] = useState("");
  const [busy, setBusy] = useState(false);
  const [membershipBusy, setMembershipBusy] = useState(false);
  const membershipPending = useRef(false);
  const [error, setError] = useState<string>();
  const [message, setMessage] = useState<string>();
  const epoch = useRef(0);
  const pending = useRef(false);
  const planSequence = useRef(0);
  const balanceSequence = useRef(0);
  const intents = useRef(new Map<string, { fingerprint: string; key: string }>());
  const token = getAccessToken();
  const prefix = `/commerce/institutes/${encodeURIComponent(instituteId)}`;
  const manager = getOperatorRole() === "responsable_institut";
  useEffect(() => {
    const stamp = ++epoch.current;
    const request = ++planSequence.current;
    apiGet<Plan[]>(`${prefix}/package-plans`).then(value => {
      if (epoch.current === stamp && request === planSequence.current && token === getAccessToken()) setPlans(value);
    }).catch(reason => { if (epoch.current === stamp && request === planSequence.current && token === getAccessToken()) setError(String(reason.message || reason)); });
    return () => { epoch.current++; };
  }, [instituteId, token]);
  useEffect(() => {
    let cancelled = false;
    const request = ++balanceSequence.current;
    setBalances([]); setBalancesLoaded(false);
    if (customer) apiGet<Balance[]>(`${prefix}/packages?customer_id=${encodeURIComponent(customer.id)}`)
      .then(value => { if (!cancelled && request === balanceSequence.current && token === getAccessToken()) { setBalances(value); setBalancesLoaded(true); } })
      .catch(reason => { if (!cancelled && request === balanceSequence.current && token === getAccessToken()) setError(String(reason.message || reason)); });
    return () => { cancelled = true; };
  }, [customer?.id, instituteId, token]);

  async function write(kind: "plan" | "issue") {
    if (pending.current || membershipPending.current || !manager) return;
    const stamp = epoch.current;
    const current = () => stamp === epoch.current && token === getAccessToken();
    const payload = kind === "plan"
      ? { name: name.trim(), service_id: serviceId, sessions: Number(sessions), valid_days: Number(days) }
      : { plan_id: planId, customer_id: customer?.id };
    const fingerprint = JSON.stringify({ instituteId, ...payload });
    let intent = intents.current.get(kind);
    if (!intent || intent.fingerprint !== fingerprint) {
      intent = { fingerprint, key: crypto.randomUUID() }; intents.current.set(kind, intent);
    }
    pending.current = true; setBusy(true); setError(undefined); setMessage(undefined);
    if (kind === "plan") planSequence.current++; else balanceSequence.current++;
    try {
      await apiPost(`${prefix}/${kind === "plan" ? "package-plans" : "packages"}`, { ...payload, idempotency_key: intent.key });
      if (!current()) return;
      if (kind === "plan") {
        const value = await apiGet<Plan[]>(`${prefix}/package-plans`);
        if (!current()) return;
        setPlans(value); setName(""); setMessage("Forfait configuré");
      } else {
        const value = await apiGet<Balance[]>(`${prefix}/packages?customer_id=${encodeURIComponent(customer!.id)}`);
        if (!current()) return;
        setBalances(value); setBalancesLoaded(true); setPlanId(""); setMessage(`Droits attribués à ${customer!.display_name}`);
      }
      intents.current.delete(kind);
    } catch (reason) {
      if (current()) setError(`${reason instanceof Error ? reason.message : "Opération indisponible"}. Réessayez avec les mêmes informations pour récupérer cette opération.`);
    } finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  const validTerms = name.trim().length > 0 && !!serviceId && Number.isInteger(Number(sessions)) && Number(sessions) >= 1
    && Number(sessions) <= 1000 && Number.isInteger(Number(days)) && Number(days) >= 1 && Number(days) <= 3650;
  return <section className="commerce-panel">
    <h2>Forfaits de l’institut</h2>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <div className="commerce-plans">{plans.map(plan => <article key={plan.id}>
      <strong>{plan.name}</strong><p>{services.find(service => service.id === plan.service_id)?.name || "Prestation indisponible"}</p>
      <p>{plan.sessions} séances · validité {plan.valid_days} jours</p>
    </article>)}</div>
    {manager && <form onSubmit={event => { event.preventDefault(); void write("plan"); }}>
      <h3>Configurer un forfait</h3><fieldset disabled={busy || membershipBusy}>
        <label>Nom du forfait<input maxLength={120} value={name} onChange={event => setName(event.target.value)} /></label>
        <label>Prestation<select value={serviceId} onChange={event => setServiceId(event.target.value)}><option value="">Choisir</option>
          {services.filter(service => service.status === "active").map(service => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
        <label>Nombre de séances<input type="number" min="1" max="1000" step="1" value={sessions} onChange={event => setSessions(event.target.value)} /></label>
        <label>Validité en jours<input type="number" min="1" max="3650" step="1" value={days} onChange={event => setDays(event.target.value)} /></label>
        <button type="submit" disabled={!validTerms}>Créer le forfait</button>
      </fieldset>
    </form>}
    <h3>{manager ? "Attribuer des droits" : "Consulter les forfaits d’une cliente"}</h3>
    <fieldset disabled={busy || membershipBusy}><CustomerPicker instituteId={instituteId} selected={customer} onSelect={value => {
      if (!pending.current && !membershipPending.current) { setCustomer(value); setMessage(undefined); }
    }} />
      {manager && <><p>Cette attribution accorde des séances. Elle ne constitue pas une vente encaissée.</p>
        <label>Forfait<select value={planId} onChange={event => setPlanId(event.target.value)}><option value="">Choisir</option>
          {plans.map(plan => <option key={plan.id} value={plan.id}>{plan.name} · {plan.sessions} séances</option>)}</select></label>
        <button type="button" disabled={!customer || !planId} onClick={() => void write("issue")}>Attribuer le forfait</button></>}
    </fieldset>
    {customer && <div><h3>Forfaits de {customer.display_name}</h3>{balancesLoaded && balances.length === 0 && <p>Aucun forfait enregistré</p>}
      {balances.map(balance => <p key={balance.id}>{balance.name} · {balance.usable_sessions} séances utilisables / {balance.remaining} restantes · expiration {readUtcDate(balance.expires_at).toLocaleDateString("fr")}</p>)}</div>}
    <MembershipManagement key={`${instituteId}:${customer?.id || ""}`} instituteId={instituteId} customer={customer} disabled={busy}
      onBusy={value => { membershipPending.current = value; setMembershipBusy(value); }} />
    <LoyaltyTiers key={`tiers:${instituteId}`} instituteId={instituteId} />
    <LoyaltyOverview instituteId={instituteId} customer={customer} />
    <GiftCardManagement key={`gift:${instituteId}`} instituteId={instituteId} />
  </section>;
}
