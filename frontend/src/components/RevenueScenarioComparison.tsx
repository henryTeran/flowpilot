import { useEffect, useRef, useState } from "react";
import { apiPost } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validRevenueScenarioComparison, validRevenueScenarioSelection, type RevenueScenarioComparison as Comparison, type RevenueScenarioEnvelope } from "../revenue-scenario-utils";
type Props = { institute: string; baseline?: RevenueScenarioEnvelope; alternatives: RevenueScenarioEnvelope[]; disabled?: boolean; onRemove: (id: string) => void };
export function RevenueScenarioComparison(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([props.institute, getAccessToken(), props.baseline?.fingerprint, props.alternatives.map(e => e.fingerprint)])} {...props} />;
}
const reasons = { currency_difference: "Devises différentes", model_difference: "Modèles différents", observed_period_difference: "Périodes observées différentes", projected_period_difference: "Périodes projetées différentes", unavailable_projection: "Une projection est indisponible" };
function Reader({ institute, baseline, alternatives, disabled, onRemove }: Props) {
  const token = getAccessToken(), sequence = useRef(0), pending = useRef(false);
  const [report, setReport] = useState<Comparison>(), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  const ref = (e: RevenueScenarioEnvelope) => ({ original_id: e.original.id, fingerprint: e.fingerprint });
  const selection = baseline ? { baseline: ref(baseline), alternatives: alternatives.map(ref) } : undefined;
  async function compare() {
    if (pending.current || disabled || token !== getAccessToken() || getOperatorRole() !== "responsable_institut" || !selection || !validRevenueScenarioSelection(selection)) return;
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    pending.current = true; setReport(undefined); setError(undefined); setBusy(true);
    try {
      const value = await apiPost<Comparison>(`/revenue/institutes/${encodeURIComponent(institute)}/scenarios/comparison`, selection);
      if (!await validRevenueScenarioComparison(value, institute, selection)) throw new Error();
      if (current()) setReport(value);
    } catch { if (current()) setError("Comparaison à vérifier. Relisez les originaux sélectionnés, puis réessayez."); }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  return <div role="region" aria-label="Comparer les scénarios">
    <h3>Comparer les scénarios conservés</h3><p>Choisissez explicitement une référence et de une à dix-neuf variantes dans l’historique, y compris sur plusieurs pages. Cette comparaison relit les originaux sélectionnés ; elle ne recapture pas les ventes et ne déclenche aucune action.</p>
    {!baseline && <p>Aucune référence sélectionnée.</p>}
    {[...(baseline ? [baseline] : []), ...alternatives].map(e => <article key={e.original.id}><p>{e === baseline ? "Référence" : "Variante"} : {e.original.reason}</p><p>{e.original.assumptions.currency} · Fraction déclarée {e.original.assumptions.activity_fraction.numerator} / {e.original.assumptions.activity_fraction.denominator}</p>
      <details><summary aria-label={`Voir l’original sélectionné ${e.original.id}`}>Voir l’original sélectionné</summary><p>Original {e.original.id} · Auteur {e.original.actor_id} · {e.original.created_at}</p>
        <p>Observé : {e.original.assumptions.observed_start} → {e.original.assumptions.observed_end}</p><p>Projeté : {e.original.assumptions.projected_start} → {e.original.assumptions.projected_end}</p><p>Sources capturées le {e.original.evidence.window.captured_at}</p><p>Empreinte : {e.fingerprint}</p></details>
      <div className="revenue-guardian-period"><button aria-label={`Retirer ${e === baseline ? "la référence" : "la variante"} ${e.original.id}`} disabled={busy || disabled} onClick={() => onRemove(e.original.id)}>Retirer {e === baseline ? "la référence" : "la variante"}</button></div></article>)}
    <div className="revenue-guardian-period"><button disabled={busy || disabled || !selection || !validRevenueScenarioSelection(selection)} onClick={() => void compare()}>Comparer la sélection</button></div>
    {busy && <p role="status">Vérification des scénarios sélectionnés…</p>}{error && <p role="alert">{error}</p>}
    {report && <><p>Comparaison vérifiée au {report.captured_at} · {report.selected_count} originaux sélectionnés. Les variantes sont des alternatives : leurs projections ne sont pas additionnées.</p>
      {report.currencies.map(g => <p key={g.currency}>{g.currency} : {g.selected_count} sélectionnés, {g.valued_count} projections chiffrées, {g.unavailable_count} indisponibles.</p>)}
      {report.variants.map(v => <article key={v.original.original.id}><h4>{v.is_baseline ? "Référence" : "Variante"} : {v.original.original.reason}</h4>
        <p>Projection conditionnelle : {v.original.original.projected_gross_minor ? `${v.original.original.projected_gross_minor.numerator} / ${v.original.original.projected_gross_minor.denominator} centimes ${v.original.original.assumptions.currency}` : "indisponible"}.</p>
        <p>Écart à la référence : {v.difference_from_baseline_minor ? `${v.difference_from_baseline_minor.numerator} / ${v.difference_from_baseline_minor.denominator} centimes ${v.original.original.assumptions.currency}` : `indisponible — ${reasons[v.difference_unavailable_reason!]}`}.</p>
        <p>Instant de capture des sources {v.same_source_capture ? "identique" : "différent"} · Agrégats enregistrés {v.same_recorded_billing_aggregates ? "identiques" : "différents"}. Ces constats ne prouvent pas l’identité des sources individuelles.</p></article>)}
      <p>Écarts de scénarios uniquement : aucune prévision validée, aucun effet causal confirmé, aucun total de toutes les ventes.</p></>}
  </div>;
}
