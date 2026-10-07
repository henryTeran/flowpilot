import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { certificationInstant } from "../certification-utils";
import { validSegmentProfile, type SegmentProfile } from "../crm-segment-utils";
import type { Customer } from "../types";

const labels: Record<string, string> = { NEW: "Nouvelle cliente", ACTIVE: "Active", LOYAL: "Fidèle", VIP: "VIP",
  AT_RISK: "À risque", DORMANT: "Inactive", policy_absent: "Politique CRM non configurée", future_policy: "Date de politique à vérifier",
  future_registration: "Date d’inscription à vérifier", future_closings: "Dates de paiement à vérifier",
  unrepresentable_horizon: "Période de politique à vérifier", undated_closings: "Dates de clôture manquantes",
  no_observed_closing: "Aucun paiement observé sur cette période", uncertain_vip_gross: "Montants insuffisants pour déterminer le statut" };
const text = (v: unknown, max: number): v is string => typeof v === "string" && !!v.trim() && v.length <= max;
function validCustomers(v: unknown, institute: string): v is Customer[] {
  return Array.isArray(v) && v.length <= 20 && new Set(v.map(r => r?.id)).size === v.length
    && v.every(r => r && text(r.id, 80) && r.institute_id === institute && text(r.display_name, 160)
      && (r.phone === null || typeof r.phone === "string" && r.phone.length <= 40) && certificationInstant(r.created_at) !== undefined);
}
export function crmMoney(minor: string, currency: string) {
  const value = BigInt(minor); return `${value/100n},${String(value%100n).padStart(2, "0")} ${currency}`;
}
export function CustomerCrmPanel({ institute }: { institute: string }) {
  if (getOperatorRole() !== "responsable_institut" || !institute) return null;
  return <Directory key={JSON.stringify([institute, getAccessToken()])} institute={institute} />;
}
function Directory({ institute }: { institute: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [query, setQuery] = useState(""), [rows, setRows] = useState<Customer[]>([]), [selected, select] = useState<Customer>();
  const [loading, setLoading] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  async function search() {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken();
    setRows([]); select(undefined); setError(undefined); setLoading(true);
    try {
      const v = await apiGet<unknown>(`/customers/institutes/${encodeURIComponent(institute)}?q=${encodeURIComponent(query)}&limit=20`);
      if (!current()) return;
      if (!validCustomers(v, institute)) throw new Error("Recherche cliente à vérifier.");
      setRows(v);
    } catch (e) { if (current()) setError(e instanceof Error ? e.message : "Recherche indisponible."); }
    finally { if (current()) setLoading(false); }
  }
  return <section className="customer-crm" aria-label="Clientes et CRM"><h2>Clientes</h2>
    <form onSubmit={e => { e.preventDefault(); if (query.trim().length >= 2 && !loading) void search(); }}>
      <label>Nom ou téléphone<input value={query} maxLength={160} onChange={e => { sequence.current++; setQuery(e.target.value); setRows([]); select(undefined); setError(undefined); setLoading(false); }} /></label>
      <button disabled={loading || query.trim().length < 2}>Rechercher</button>
    </form><p>Choisissez une cliente enregistrée. Jusqu’à 20 résultats ; affinez la recherche si nécessaire.</p>
    {loading && <p role="status">Recherche…</p>}{error && <p role="alert">{error}</p>}
    <ul>{rows.map(c => <li key={c.id}><button onClick={() => select(c)} aria-pressed={selected?.id === c.id}>{c.display_name}{c.phone ? ` · ${c.phone}` : ""}</button></li>)}</ul>
    {selected && <CustomerCrmProfile institute={institute} customer={selected} />}
  </section>;
}
export function CustomerCrmProfile(props: { institute: string; customer: Customer }) {
  if (getOperatorRole() !== "responsable_institut" || props.customer.institute_id !== props.institute) return null;
  return <Profile key={JSON.stringify([props.institute, props.customer.id, getAccessToken()])} {...props} />;
}
function Profile({ institute, customer }: { institute: string; customer: Customer }) {
  const token = getAccessToken(), [revision, refresh] = useState(0), [result, setResult] = useState<SegmentProfile>();
  const [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(true);
    void apiGet<unknown>(`/crm/institutes/${encodeURIComponent(institute)}/customers/${encodeURIComponent(customer.id)}/segment`)
      .then(v => { if (!current()) return; if (!validSegmentProfile(v, institute, customer.id)) throw new Error("Profil CRM à vérifier."); setResult(v); })
      .catch(e => { if (current()) setError(e instanceof Error ? e.message : "Profil indisponible."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [revision]);
  const s = result?.segment;
  return <section aria-label="Profil CRM"><header><h3>{customer.display_name}</h3><button disabled={loading} onClick={() => refresh(v => v+1)}>Actualiser le profil</button></header>
    {loading && <p role="status">Lecture du profil…</p>}{error && <p role="alert">{error}</p>}
    {result && <><p>Statut : {labels[s?.state || result.unavailable_reason || s?.reason || ""] || "Indéterminé"}</p>
      <p>L’état porte sur les tickets payés observés. L’historique complet et la valeur future restent inconnus.</p>
      {s && <><p>Tickets payés sur la période : {s.billing.closed_tickets}</p>
        <p>Dernier paiement : {s.billing.last_recorded_closed_at || "Non connu"}</p>
        {s.billing.currencies.map(g => <div key={g.currency}><p>Montant connu : {crmMoney(g.known_gross_minor, g.currency)}</p>
          <p>Panier moyen : {g.recorded_average_basket_minor ? `${crmMoney(String((BigInt(g.recorded_average_basket_minor.numerator)*2n+BigInt(g.recorded_average_basket_minor.denominator))/(BigInt(g.recorded_average_basket_minor.denominator)*2n)), g.currency)} (arrondi au centime)` : "Non déterminé"}</p>
          {(g.missing_amount_tickets+g.invalid_amount_tickets > 0) && <p>Montants à vérifier : {g.missing_amount_tickets+g.invalid_amount_tickets}</p>}</div>)}
        {s.billing.unknown_currency_tickets > 0 && <p>Devise inconnue : {s.billing.unknown_currency_tickets} tickets</p>}</>}
      {(result.undated_paid_tickets+result.future_paid_tickets > 0) && <p>Dates à vérifier : {result.undated_paid_tickets+result.future_paid_tickets} tickets</p>}
      <details><summary>Période et règle appliquée</summary><p>Lecture : {result.captured_at}</p>{s && <p>Période : {s.billing.window.start} — {s.billing.window.end}</p>}
        {result.policy_original && <p>Règle enregistrée par {result.policy_original.actor_id} · motif : {result.policy_original.reason}</p>}</details></>}
  </section>;
}
