import { useEffect, useRef, useState } from "react";
import { apiPost } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validWaitlistLifecycleState } from "../waitlist-lifecycle-utils";
import { validOptimizerPolicyEnvelope, type OptimizerPolicyEnvelope } from "../optimizer-policy-utils";
import { validOptimizerReview, type OptimizerReview, type OptimizerReviewSelection } from "../optimizer-review-utils";
import { validWaitlistPolicy, type WaitlistMatchingSelection } from "../waitlist-matching-utils";
import { certificationInstant as instant } from "../certification-utils";
import type { Employee } from "../types";
import { optimizerLabels } from "./OptimizerPolicyPanel";
type Props = { institute: string; timezone?: string; matching?: WaitlistMatchingSelection; policy?: OptimizerPolicyEnvelope; employees?: Employee[] };
const constraints = ["Contraintes clientes relues", "Durée de prestation inchangée", "Disponibilités déclarées de la cliente",
  "Fenêtre libre et restriction de collaboratrice", "Qualifications requises", "Ressources distinctes compatibles", "Absence d’occupation cliente en conflit", "Projection de file connue"];
const unknownReasons: Record<string, string> = { revenue_score: "Devise du catalogue non enregistrée.", continuity_score: "Pas d’indicateur de continuité liée à une collaboratrice.",
  client_preference_score: "Les restrictions déclarées sont des contraintes, sans préférence graduée.", employee_preference_score: "Pas de préférence explicite enregistrée pour la collaboratrice.",
  overtime_penalty: "Horaires de travail déclarés indisponibles." };
const refusals: Record<string, string> = { cancelled: "Liste annulée", registration_unavailable: "Inscription cliente indisponible", active_service_unavailable: "Prestation active indisponible",
  history_requirement_unmet: "Historique insuffisant pour la règle choisie", permission_requirement_unmet: "Accord de suivi insuffisant pour la règle choisie",
  constraints_unknown: "Contraintes clientes inconnues", duration_changed: "Durée actuelle modifiée", resource_configuration_unknown: "Ressources à vérifier",
  customer_capacity_unknown: "Occupation cliente à vérifier", queue_projection_unknown: "Projection de file à vérifier", no_matching_recorded_capacity: "Aucune capacité enregistrée correspondante" };
export function OptimizerScoringReview(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut" || !getOperatorSubject()) return null;
  return <Reader key={JSON.stringify([props.institute, props.timezone, getAccessToken(), props.policy?.fingerprint,
    props.matching?.state.events[props.matching.state.events.length-1]?.fingerprint, props.matching?.horizon_end, props.matching?.policy])} {...props} />;
}
function Reader({ institute, timezone, matching, policy, employees = [] }: Props) {
  const token = getAccessToken(), actor = getOperatorSubject(), mounted = useRef(false), sequence = useRef(0), section = useRef<HTMLElement>(null);
  const [selection, setSelection] = useState<OptimizerReviewSelection>(), [report, setReport] = useState<OptimizerReview>(), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const current = (n: number) => mounted.current && n === sequence.current && token === getAccessToken() && actor === getOperatorSubject() && getOperatorRole() === "responsable_institut";
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current++; }; }, []);
  useEffect(() => {
    const n = ++sequence.current; setReport(undefined); setSelection(undefined); setBusy(false); setError(undefined);
    if (!matching || !policy) return;
    void (async () => {
      const value = { ...structuredClone(matching), policyOriginal: structuredClone(policy) };
      if (!await validWaitlistLifecycleState(value.state, institute) || value.state.state !== "active" || !validWaitlistPolicy(value.policy)
        || instant(value.horizon_end) === undefined || !await validOptimizerPolicyEnvelope(value.policyOriginal, institute)) {
        if (current(n)) setError("Sélections à vérifier. Relisez la demande et la politique conservées."); return;
      }
      if (current(n)) { setSelection(value); section.current?.focus(); section.current?.scrollIntoView?.({ block: "start" }); }
    })();
  }, [matching, policy]);
  function date(value: string) { try { return new Intl.DateTimeFormat("fr-CH", { timeZone: timezone || "UTC", dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); } catch { return value; } }
  async function load() {
    if (!selection || busy) return;
    const n = ++sequence.current; setReport(undefined); setError(undefined); if (!current(n)) return; setBusy(true);
    const expected = structuredClone(selection), latest = expected.state.events[expected.state.events.length-1];
    try {
      const value = await apiPost<OptimizerReview>(`/optimizer/institutes/${encodeURIComponent(institute)}/reviews/current`, {
        policy_id: expected.policyOriginal.original.id, policy_fingerprint: expected.policyOriginal.fingerprint,
        root_id: expected.state.root.original.id, expected_event_id: latest.original.id, expected_event_fingerprint: latest.fingerprint,
        horizon_end: expected.horizon_end, matching_policy: expected.policy });
      if (!await validOptimizerReview(value, institute, expected)) throw new Error("Invalid current scoring report");
      if (current(n)) setReport(value);
    } catch { if (current(n)) setError("Scores et preuves à vérifier. Relisez la demande active et la politique si leur version a changé, puis relancez la revue."); }
    finally { if (current(n)) setBusy(false); }
  }
  const reason = report?.source.unavailable_reason || report?.source.review?.unavailable_reason;
  return <section ref={section} tabIndex={-1} className="revenue-guardian-panel" aria-label="Scores des créneaux sous hypothèses"><h2>Scores des créneaux sous hypothèses</h2>
    <p>Les scores comparent des alternatives indépendantes dans la capacité enregistrée. Relisez les preuves et revalidez avant toute réservation ou tout contact.</p>
    <p>Les fenêtres reposent sur les occupations enregistrées ; les horaires d’ouverture ne sont pas vérifiés.</p>
    {selection ? <p>Demande : {selection.state.current_demand.original.reason} · politique : {selection.policyOriginal.original.reason}. Horizon jusqu’au {date(selection.horizon_end)}.</p>
      : <p>Choisissez une politique conservée et examinez une demande active dans la revue de créneaux.</p>}
    <div className="revenue-guardian-period"><button disabled={!selection || busy} onClick={() => void load()}>Relire les sources et calculer les scores</button></div>
    {busy && <p role="status">Relecture des sources et vérification des scores…</p>}{error && <p role="alert">{error}</p>}
    {report && <><p>Capture au {date(report.captured_at)}. Aucun créneau réservé, aucun contact autorisé par cette lecture.</p>
      {reason && <p>{refusals[reason]} : aucune option scorée disponible.</p>}
      {report.review?.ranking === "incomplete_evidence" && <p>Classement indisponible : preuves pondérées manquantes. Aucun meilleur créneau n’est désigné.</p>}
      {report.review?.ranking === "complete" && <p>Classement complet selon la politique explicite, sous réserve de revalidation.</p>}
      {report.review?.ranking === "no_admissible_options" && <p>Aucune option admissible dans cette capture.</p>}
      {report.review?.options.map((r, i) => { const proof = report.proofs.find(p => p.option.employee_id === r.option.employee_id && p.option.start === r.option.start && p.option.end === r.option.end
        && JSON.stringify([...p.option.resource_ids].sort()) === JSON.stringify([...r.option.resource_ids].sort()))!;
        return <article key={i} aria-label={`Option scorée ${i+1}`}><h3>{r.rank === null ? "Option sans classement" : `Rang ${r.rank} sous hypothèses`}</h3>
          <p>Du {date(r.option.start)} au {date(r.option.end)} · collaboratrice {employees.find(e => e.institute_id === institute && e.id === r.option.employee_id)?.first_name || r.option.employee_id}.
            {r.option.resource_ids.length ? ` Ressources : ${r.option.resource_ids.join(", ")}.` : " Aucune ressource requise selon la capture."}</p>
          <p>{r.score ? `Score exact : ${r.score.numerator}/${r.score.denominator}.` : "Score indisponible : une preuve pondérée manque."}</p>
          <h4>Facteurs et raisons</h4><ul>{r.contributions.map((c, j) => <li key={c.factor}><strong>{optimizerLabels[c.factor]}</strong> : {c.state === "disabled_by_policy" ? "désactivé explicitement" : c.state === "unavailable" ? "preuve indisponible" : `contribution ${c.contribution!.numerator}/${c.contribution!.denominator}`}.
            {proof.factors[j].source.quantity === null ? ` Donnée inconnue, sans valeur inventée. ${unknownReasons[c.factor] || ""}`
              : c.factor === "utilization_score" ? ` Durée proposée ${report.source.review!.capture.service.duration_minutes} min ; fenêtre capturée du ${date(proof.containing_employee_window.start)} au ${date(proof.containing_employee_window.end)}.`
              : c.factor === "idle_gap_penalty" ? ` Délai entre la capture au ${date(report.captured_at)} et le début proposé au ${date(r.option.start)}.`
              : " Aucun conflit identifié dans cette capture."}
            {proof.factors[j].saturated === "yes" && " Normalisation plafonnée selon la politique explicite."}</li>)}</ul>
          <h4>Vérifications dans cette capture</h4><ul>{r.constraints.map((c, j) => <li key={c.id}>{constraints[j]} : satisfait selon les sources capturées.</li>)}</ul>
          <details><summary>Voir les raisons exactes et les preuves de cette option</summary><ul>{r.reasons.map((s, j) => <li key={j}>{s}</li>)}</ul><pre>{JSON.stringify({ option: r, proof }, null, 2)}</pre></details>
        </article>;
      })}
      <details><summary>Voir la politique, la version et toutes les sources</summary><p>Politique {report.policy_original.original.id} · empreinte {report.policy_original.fingerprint}.</p>
        <pre>{JSON.stringify(report, null, 2)}</pre></details></>}
  </section>;
}
