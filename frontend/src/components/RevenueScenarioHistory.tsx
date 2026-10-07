import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validRevenueScenarioAudit, type RevenueScenarioAudit } from "../revenue-scenario-utils";
import { revenueMoney } from "../revenue-utils";
const unavailable = { unknown_currency: "Une devise enregistrée est inconnue.", undated_paid_tickets: "Des tickets payés de l’institut n’ont pas de date exploitable.",
  no_selected_currency: "Aucun ticket dans la devise sélectionnée.", uncertain_amounts: "Des montants sont manquants ou invalides." };
export function RevenueScenarioHistory({ institute }: { institute: string }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([institute, getAccessToken()])} institute={institute} />;
}
function Reader({ institute }: { institute: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [report, setReport] = useState<RevenueScenarioAudit>(), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  async function load(offset = 0) {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    setReport(undefined); setError(undefined); setBusy(true);
    try {
      const value = await apiGet<RevenueScenarioAudit>(`/revenue/institutes/${encodeURIComponent(institute)}/scenarios/originals?offset=${offset}&limit=20`);
      if (!await validRevenueScenarioAudit(value, institute, offset)) throw new Error("Invalid scenario audit");
      if (current()) setReport(value);
    } catch { if (current()) setError("Historique des scénarios à vérifier. Relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <section className="revenue-guardian-panel" aria-label="Scénarios conservés">
    <h2>Scénarios conservés</h2>
    <p>Estimations conditionnelles fondées sur des hypothèses déclarées et des sources capturées. Leur conservation ne valide pas une prévision et ne déclenche aucune action.</p>
    <div className="revenue-guardian-period"><button disabled={busy} onClick={() => void load()}>Lire l’historique des scénarios</button></div>
    {busy && <p role="status">Lecture des scénarios…</p>}{error && <p role="alert">{error}</p>}
    {report && <>
      <p>Historique vérifié au {report.captured_at} · {report.total} scénarios conservés.</p>
      <p>{report.originals.length ? `${report.offset+1}–${report.offset+report.originals.length}` : "0"} sur {report.total}. Chaque page est une nouvelle lecture.</p>
      {report.originals.map(e => <article key={e.original.id}>
        <h3>{e.original.reason}</h3>
        <p>Original {e.original.id} · Conservé le {e.original.created_at} · Auteur {e.original.actor_id}.</p>
        <p>Projection conditionnelle : {e.original.projected_gross_minor
          ? `${e.original.projected_gross_minor.numerator} / ${e.original.projected_gross_minor.denominator} centimes ${e.original.assumptions.currency}` : "indisponible"}.</p>
        {e.original.unavailable_reason && <p>{unavailable[e.original.unavailable_reason]}</p>}
        <details><summary>Voir les hypothèses et preuves de {e.original.id}</summary>
          <p>Modèle : rythme brut enregistré constant, appliqué à la période projetée avec la fraction d’activité déclarée.</p>
          <p>Devise sélectionnée : {e.original.assumptions.currency}. Début inclus, fin exclue.</p>
          <p>Période observée : {e.original.assumptions.observed_start} → {e.original.assumptions.observed_end}.</p>
          <p>Période projetée : {e.original.assumptions.projected_start} → {e.original.assumptions.projected_end}.</p>
          <p>Fraction d’activité déclarée : {e.original.assumptions.activity_fraction.numerator} / {e.original.assumptions.activity_fraction.denominator}.</p>
          <p>{e.original.evidence.ticket_count} tickets payés enregistrés · Sources capturées le {e.original.evidence.window.captured_at}.</p>
          <p>{e.original.evidence.institute_undated_paid_tickets} tickets payés sans date exploitable dans tout l’institut.</p>
          <p>Ces enregistrements ne prouvent ni toutes les ventes ni les encaissements bancaires.</p>
          {e.original.evidence.ticket_amounts.map(g => <p key={g.currency || "unknown"}>{g.currency || "Devise inconnue"} : {g.known_amount_count} montants connus, {g.missing_amount_count} manquants, {g.invalid_amount_count} invalides.
            {g.currency && g.known_amount_count > 0 ? ` Montants connus : ${revenueMoney(g.known_gross_minor)} ${g.currency}${g.complete_gross_minor === null ? " (incomplet)" : ""}.` : " Montant monétaire indisponible."}</p>)}
          <p>Clé de reprise : {e.original.idempotency_key}</p><p>Empreinte de l’original : {e.fingerprint}</p>
        </details>
      </article>)}
      <div className="revenue-guardian-period"><button disabled={report.offset === 0} onClick={() => void load(Math.max(0, report.offset-20))}>Scénarios précédents</button>
        <button disabled={report.offset+report.originals.length >= report.total} onClick={() => void load(report.offset+20)}>Scénarios suivants</button></div>
    </>}
  </section>;
}
