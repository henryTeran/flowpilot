import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validConversionReport, type ConversionReport } from "../marketing-conversion-utils";
import { certificationInstant } from "../certification-utils";
import { instituteMidnight } from "../outlook-utils";
import { MarketingCurrentConversions } from "./MarketingCurrentConversions";

function money(minor: string): string {
  const amount = BigInt(minor);
  return `${amount / 100n}.${(amount % 100n).toString().padStart(2, "0")}`;
}
export function MarketingConversionReport({ institute, campaign, timezone }: { institute: string; campaign: string; timezone?: string }) {
  if (!institute || !campaign || getOperatorRole() !== "responsable_institut") return null;
  return <ReportForm key={JSON.stringify([institute, campaign, timezone, getAccessToken()])} institute={institute} campaign={campaign} timezone={timezone} />;
}
function ReportForm({ institute, campaign, timezone }: { institute: string; campaign: string; timezone?: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [start, setStart] = useState(""), [end, setEnd] = useState("");
  const [report, setReport] = useState<ConversionReport>(), [loading, setLoading] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  function change(field: "start" | "end", value: string) {
    sequence.current++; setReport(undefined); setError(undefined); setLoading(false);
    if (field === "start") setStart(value); else setEnd(value);
  }
  async function load() {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken()
      && getOperatorRole() === "responsable_institut";
    setReport(undefined); setError(undefined);
    const from = timezone && instituteMidnight(start, timezone), until = timezone && instituteMidnight(end, timezone);
    const first = certificationInstant(from), last = certificationInstant(until);
    if (!from || !until || first === undefined || last === undefined || first >= last) { setError("Choisissez deux dates dans l’ordre et vérifiez le fuseau de l’institut."); return; }
    const period = { start: from, end: until };
    setLoading(true);
    try {
      const params = new URLSearchParams(period);
      const result = await apiGet<ConversionReport>(`/marketing/institutes/${encodeURIComponent(institute)}/campaigns/${encodeURIComponent(campaign)}/conversions/summary?${params}`);
      if (!validConversionReport(result, institute, campaign, period)) throw new Error("Invalid conversion summary");
      if (current()) setReport(result);
    } catch { if (current()) setError("Synthèse à vérifier. Vérifiez la période et relancez la lecture."); }
    finally { if (current()) setLoading(false); }
  }
  return <section aria-label="Synthèse des conversions" style={{ overflowWrap: "anywhere" }}>
    <h3>Conversions déclarées</h3>
    <p>Choisissez une période de facturation déjà observée. Le début est inclus, la fin exclue.</p>
    <p>Journées de l’institut · {timezone || "Fuseau indisponible"}</p>
    <label>Date de début <input type="date" value={start} onChange={e => change("start", e.target.value)} /></label>
    <label>Date de fin exclue <input type="date" value={end} onChange={e => change("end", e.target.value)} /></label>
    <button disabled={loading} onClick={() => void load()}>Lire la synthèse des conversions</button>
    {loading && <p role="status">Lecture des conversions…</p>}
    {error && <p role="alert">{error}</p>}
    {report && <>
      <p>Lecture du {report.summary.window.captured_at}</p>
      <p>{report.selected_current_links} tickets liés courants : {report.summary.live_linked_tickets} en mode réel et {report.summary.test_linked_tickets} en mode test.</p>
      <p>Montants historiques retenus lors du lien. Une correction du ticket seule ne modifie pas cette attribution.</p>
      {report.summary.currencies.map(c => <article key={`${c.mode}/${c.currency}`}>
        <h4>{c.mode === "live" ? "Mode réel" : "Mode test"} · {c.currency}</h4>
        <p>{money(c.known_gross_minor)} {c.currency} de montants connus pour {c.known_amount_tickets} tickets.</p>
        <p>{c.missing_amount_tickets} montants manquants · {c.invalid_amount_tickets} montants invalides.</p>
      </article>)}
      <p>Devise inconnue : {report.summary.unknown_currency_live_tickets} tickets réels et {report.summary.unknown_currency_test_tickets} tickets de test.</p>
      <p>Cette synthèse couvre les liens déclarés courants de la période. Elle ne prouve pas toutes les ventes, la livraison ou l’effet de la campagne. Taux de conversion et retour publicitaire non calculés.</p>
      <MarketingCurrentConversions institute={institute} campaign={campaign} period={{ start: report.summary.window.start, end: report.summary.window.end }} />
    </>}
  </section>;
}
