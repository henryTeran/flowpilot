import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validOccupation, type Occupation } from "../occupation-utils";
import { formatOccupationBasisPoints } from "../occupation-math";
import { formatWorkDuration } from "../work-hours-utils";
type Props = { institute: string; employee: string; day: string; start: string; end: string; timezone: string };
export function EmployeeOccupationPanel(props: Props) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <Reading key={JSON.stringify([props, getAccessToken()])} {...props} />;
}
function Reading({ institute, employee, day, start, end, timezone }: Props) {
  const token = getAccessToken(), [offset, page] = useState(0), [revision, refresh] = useState(0);
  const [result, setResult] = useState<Occupation>(), [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(true);
    void apiGet<Occupation>(`/workforce/institutes/${encodeURIComponent(institute)}/employees/${encodeURIComponent(employee)}/occupation?day=${day}&limit=20&offset=${offset}`)
      .then(v => { if (!current()) return; if (!validOccupation(v, institute, employee, day, start, end, timezone, offset)) throw new Error("Lecture de l’occupation à vérifier."); setResult(v); })
      .catch(e => { if (current()) setError(e instanceof Error ? e.message : "Occupation indisponible."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [offset, revision]);
  const visible = result?.page.offset === offset ? result : undefined;
  const labels = { missing_start: "Début effectif inconnu", missing_end: "Fin effective inconnue", invalid_interval: "Intervalle incohérent", future_end: "Fin future", unfinalized: "Exécution non finalisée" };
  return <section aria-label="Occupation enregistrée" className="employee-occupation">
    <header><h3>Occupation enregistrée</h3><button disabled={loading} onClick={() => refresh(v => v+1)}>Actualiser l’occupation</button></header>
    <p>{day} · {timezone}. Mesure sur les heures déclarées ; la présence et l’activité complètes restent inconnues.</p>
    {loading && <p role="status">Lecture de l’occupation…</p>}{error && <p role="alert">{error}</p>}
    {visible && <><p>Lecture au {visible.work_hours.generated_at}</p>
      <p>Heures déclarées à cette lecture : {visible.work_hours.recorded_duration_us === null ? "Inconnues" : formatWorkDuration(visible.work_hours.recorded_duration_us)}.</p>
      <p>{visible.recorded_occupation_basis_points === null ? "Occupation non déterminable" : `Occupation sur le temps déclaré : ${formatOccupationBasisPoints(visible.recorded_occupation_basis_points)} (arrondie vers le bas)`}</p>
      <p>Temps occupé connu : {formatWorkDuration(visible.known_busy_duration_us)} · couvert par les heures déclarées : {formatWorkDuration(visible.covered_busy_duration_us)}.</p>
      <p>Hors heures déclarées : {formatWorkDuration(visible.outside_recorded_work_duration_us)}.</p>
      {Object.entries(labels).map(([key, label]) => visible.diagnostics[key as keyof typeof labels] > 0 && <p key={key}>{label} : {visible.diagnostics[key as keyof typeof labels]} sources exclues.</p>)}
      <ul className="absence-list">{visible.rows.map(s => <li key={`${s.kind}:${s.id}`}><strong>{s.kind === "session" ? "Prestation walk-in" : "Rendez-vous"}</strong>
        <p>{s.exclusion ? labels[s.exclusion] : `Durée retenue : ${formatWorkDuration(s.duration_us!)}`}</p>
        <details><summary>Provenance de l’occupation</summary><p>Original {s.id} · prestation {s.service_id} · état {s.status}</p>
          <p>Début effectif : {s.actual_start || "Inconnu"} · fin effective : {s.actual_end || "Inconnue"}</p></details></li>)}</ul>
      <div className="workforce-pages"><span>Sources : {visible.rows.length ? offset+1 : 0}–{offset+visible.rows.length} / {visible.page.total}</span>
        <button disabled={loading || !offset} onClick={() => page(offset-20)}>Occupation précédente</button><button disabled={loading || offset+20 >= visible.page.total} onClick={() => page(offset+20)}>Occupation suivante</button></div></>}
  </section>;
}
