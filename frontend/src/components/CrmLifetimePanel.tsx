import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validLifetimeRead, type LifetimeRead } from "../crm-lifetime-utils";
import type { BillingRatio } from "../crm-billing-utils";
import { CrmLifetimeEditor } from "./CrmLifetimeEditor";
const reasons: Record<string,string> = { assumptions_absent: "Hypothèses non configurées",future_assumptions: "Date des hypothèses à vérifier",
  future_registration: "Date d’inscription à vérifier",stale_window: "Période ancienne",undated_closings: "Dates de paiement manquantes",
  future_closings: "Dates de paiement futures",unrepresentable_lifetime: "Durée future hors calendrier",
  unknown_currency: "Devise de paiement inconnue",no_observed_currency: "Aucun paiement observé dans la devise choisie",uncertain_amounts: "Montants de paiement à vérifier" };
export function lifetimeMoney(r: BillingRatio,currency: string) {
  const n = BigInt(r.numerator), d = BigInt(r.denominator), abs = n < 0n ? -n : n;
  const cents = (abs*2n+d)/(2n*d);
  return `${n < 0n && cents > 0n ? "−" : ""}${cents/100n},${String(cents%100n).padStart(2,"0")} ${currency}`;
}
export function CrmLifetimePanel(props: { institute: string; customer: string; start?: string }) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <Panel key={JSON.stringify([props.institute,props.customer,getAccessToken()])} {...props} />;
}
function Panel({ institute,customer,start }: { institute: string; customer: string; start?: string }) {
  const [revision,refresh] = useState(0);
  return <><details><summary>Déclarer les hypothèses CLV</summary>
    <CrmLifetimeEditor institute={institute} customer={customer} onChanged={() => refresh(v => v+1)} /></details>
    {start ? <Scenario key={JSON.stringify([start,revision])} institute={institute} customer={customer} start={start} />
      : <p>Scénario CLV indisponible : configurez une période CRM vérifiable.</p>}</>;
}
function Scenario({ institute,customer,start }: { institute: string; customer: string; start: string }) {
  const token = getAccessToken(), [revision,refresh] = useState(0), [result,setResult] = useState<LifetimeRead>();
  const [loading,setLoading] = useState(true), [error,setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(true);
    void apiGet<unknown>(`/crm/institutes/${encodeURIComponent(institute)}/customers/${encodeURIComponent(customer)}/lifetime-scenario?${new URLSearchParams({ start })}`)
      .then(v => { if (!current()) return; if (!validLifetimeRead(v,institute,customer,start)) throw new Error("Scénario CLV à vérifier."); setResult(v); })
      .catch(e => { if (current()) setError(e instanceof Error ? e.message : "Scénario indisponible."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [revision]);
  const s = result?.scenario, a = result?.original?.assumptions, reason = result?.unavailable_reason || s?.unavailable_reason;
  return <section aria-label="Scénario CLV restante"><header><h4>Scénario de valeur restante</h4>
    <button disabled={loading} onClick={() => { setResult(undefined); setLoading(true); refresh(v => v+1); }}>Actualiser le scénario CLV</button></header>
    <p>Projection conditionnelle sur les hypothèses déclarées, à rythme observé constant, sans actualisation. L’historique complet et la valeur future réelle restent inconnus.</p>
    {loading && <p role="status">Lecture du scénario…</p>}{error && <p role="alert">{error}</p>}
    {result && <><p>Période de facturation : {result.window.start} — {result.window.end}</p>
      <p>Lecture du scénario : {result.window.captured_at}. Lecture distincte du profil et des soins.</p>
      {reason && <p>Valeur restante non déterminée : {reasons[reason]}.</p>}
      {s && a && <><p>Tickets payés observés : {s.billing.closed_tickets} · devise du scénario : {a.currency}</p>
        <p>Dates manquantes : {s.undated_paid_tickets} · dates futures : {s.future_paid_tickets}</p>
        {s.remaining_clv_minor && <><p>Montant brut projeté : {lifetimeMoney(s.projected_gross_minor!,a.currency)} (arrondi au centime)</p>
          <p>Contribution projetée : {lifetimeMoney(s.projected_contribution_minor!,a.currency)} (arrondi au centime)</p>
          <p>CLV restante conditionnelle : {lifetimeMoney(s.remaining_clv_minor,a.currency)} (arrondi au centime)</p></>}
        <details><summary>Hypothèses et calcul CLV</summary><p>Durée d’activité supposée : {a.expected_active_us} microsecondes · jusqu’au {s.assumed_active_until || "Non déterminé"}</p>
          <p>Activité conservée : {a.activity_fraction.numerator} sur {a.activity_fraction.denominator} · marge sur brut : {a.gross_contribution_margin.numerator} sur {a.gross_contribution_margin.denominator}</p>
          <p>Coûts futurs déclarés : {lifetimeMoney({ numerator: a.future_relationship_cost_minor,denominator: "1" },a.currency)}</p>
          <p>Brut = montant observé / durée observée × durée supposée × activité conservée. Contribution = brut × marge. Valeur restante = contribution − coûts futurs.</p>
          {s.remaining_clv_minor && <p>Valeur exacte en centimes : {s.remaining_clv_minor.numerator} / {s.remaining_clv_minor.denominator}.</p>}</details></>}
      {result.original && <p>Original {result.original.id} · enregistré par {result.original.actor_id} · motif : {result.original.reason}</p>}</>}
  </section>;
}
