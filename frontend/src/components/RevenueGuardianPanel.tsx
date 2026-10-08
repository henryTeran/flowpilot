import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { certificationInstant } from "../certification-utils";
import { instituteMidnight } from "../outlook-utils";
import { revenueAverage, revenueMoney, validRevenueBilling, type RevenueBilling, type RevenueAmounts } from "../revenue-utils";
import { RevenueCapacityReport } from "./RevenueCapacityReport";
import { RevenueScenarioHistory } from "./RevenueScenarioHistory";
import { RevenueScenarioWriter } from "./RevenueScenarioWriter";
import { RevenueBookingClosures } from "./RevenueBookingClosures";
import { RevenueWalkInCancellations } from "./RevenueWalkInCancellations";
import { RevenueSlotOpportunity } from "./RevenueSlotOpportunity";
import type { Service } from "../types";

export function RevenueGuardianPanel({ institute, timezone, services = [] }: { institute: string; timezone?: string; services?: Service[] }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <><Reader key={JSON.stringify([institute, timezone, getAccessToken()])} institute={institute} timezone={timezone} />
    <RevenueCapacityReport institute={institute} timezone={timezone} /><ScenarioWorkspace institute={institute} timezone={timezone} /><RevenueBookingClosures institute={institute} timezone={timezone} /><RevenueWalkInCancellations institute={institute} timezone={timezone} /><RevenueSlotOpportunity institute={institute} timezone={timezone} services={services} /></>;
}
function ScenarioWorkspace({ institute, timezone }: { institute: string; timezone?: string }) {
  const [revision, setRevision] = useState(0);
  return <><RevenueScenarioWriter institute={institute} timezone={timezone} onRetained={() => setRevision(n => n+1)} />
    <RevenueScenarioHistory key={revision} institute={institute} /></>;
}
function Amounts({ value }: { value: RevenueAmounts }) {
  return <>
    {value.currency ? <p>{value.known_amount_count ? `${revenueMoney(value.known_gross_minor)} ${value.currency}` : "Aucun montant connu"} · {value.complete_gross_minor === null ? "Sous-total connu, incomplet" : "Total enregistré de ce groupe"}</p>
      : <p>Devise inconnue : montant monétaire non affiché.</p>}
    <p>{value.known_amount_count} montants connus · {value.missing_amount_count} manquants · {value.invalid_amount_count} invalides.</p>
  </>;
}
function Reader({ institute, timezone }: { institute: string; timezone?: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [start, setStart] = useState(""), [end, setEnd] = useState("");
  const [report, setReport] = useState<RevenueBilling>(), [loading, setLoading] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  function change(field: "start" | "end", value: string) {
    sequence.current++; setReport(undefined); setError(undefined); setLoading(false);
    if (field === "start") setStart(value); else setEnd(value);
  }
  async function load() {
    const request = ++sequence.current, current = () => sequence.current === request && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    setReport(undefined); setError(undefined);
    const from = timezone && instituteMidnight(start, timezone), until = timezone && instituteMidnight(end, timezone);
    const first = certificationInstant(from), last = certificationInstant(until);
    if (!from || !until || first === undefined || last === undefined || first >= last) { setError("Choisissez une période terminée et vérifiez le fuseau de l’institut."); return; }
    setLoading(true);
    try {
      const period = { start: from, end: until };
      const result = await apiGet<unknown>(`/revenue/institutes/${encodeURIComponent(institute)}/billing?${new URLSearchParams(period)}`);
      if (!validRevenueBilling(result, institute, period)) throw new Error("Invalid billing report");
      if (current()) setReport(result);
    } catch { if (current()) setError("Synthèse indisponible. Vérifiez la période et relancez la lecture."); }
    finally { if (current()) setLoading(false); }
  }
  return <section className="revenue-guardian-panel" aria-label="Revenue Guardian" style={{ overflowWrap: "anywhere" }}>
    <h2>Revenue Guardian · Facturation enregistrée</h2>
    <p>Tickets marqués payés et lignes de facture actives. Cette lecture ne confirme pas les encaissements bancaires ni toutes les ventes et ne prédit pas les recettes.</p>
    <p>Journées de l’institut · {timezone || "Fuseau indisponible"}. Début inclus, fin exclue.</p>
    <div className="revenue-guardian-period"><label>Date de début <input type="date" value={start} onChange={e => change("start", e.target.value)} /></label>
    <label>Date de fin exclue <input type="date" value={end} onChange={e => change("end", e.target.value)} /></label>
    <button disabled={loading} onClick={() => void load()}>Lire la facturation enregistrée</button></div>
    {loading && <p role="status">Lecture de la facturation…</p>}{error && <p role="alert">{error}</p>}
    {report && <>
      <p>Lecture du {report.window.captured_at} · {report.ticket_count} tickets payés dans la période.</p>
      {report.ticket_amounts.map(g => <article key={g.currency || "unknown"}><h3>{g.currency || "Devise inconnue"} · {g.source_count} tickets</h3><Amounts value={g} />
        <p>Panier moyen : {g.average_minor ? `${revenueAverage(g.average_minor)} ${g.currency}` : "indisponible"}.</p></article>)}
      <h3>Couverture des catégories</h3>
      <p>{report.care_tickets} tickets avec soin · {report.care_and_retail_tickets} avec soin et produit.</p>
      <p>Association soin / produit : {report.recorded_retail_attach_ratio ? `${report.care_and_retail_tickets} / ${report.care_tickets} tickets avec soin` : "indisponible"}.</p>
      <p>{report.tickets_without_active_lines} tickets sans ligne active · {report.tickets_with_unknown_category} avec catégorie inconnue.</p>
      <h3>Répartition des lignes actives · {report.active_line_count}</h3>
      {report.service_mix.map(g => <article key={JSON.stringify([g.service_id, g.category, g.currency])}>
        <h4>Prestation {g.service_id} · {g.category === "care" ? "Soin" : g.category === "retail" ? "Produit" : "Catégorie inconnue"}</h4>
        <p>{g.line_count} lignes · {g.units} unités · {g.currency || "Devise inconnue"}</p><Amounts value={g.amounts} />
      </article>)}
      <p>Dans tout l’institut, hors décompte de cette période : {report.institute_undated_paid_tickets} tickets payés sans date de paiement exploitable.</p>
    </>}
  </section>;
}
