import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validObjectivePage, type ObjectivePage, type Objective } from "../objective-utils";
type Props = { institute: string; employee: string; blocked?: boolean; onCancel?: (row: Objective) => void; onRead?: (ready: boolean) => void };
export function EmployeeObjectivesPanel(props: Props) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <Objectives key={JSON.stringify([props.institute, props.employee, getAccessToken()])} {...props} />;
}
function Objectives({ institute, employee, blocked, onCancel, onRead }: Props) {
  const token = getAccessToken(), [offset, page] = useState(0), [revision, refresh] = useState(0);
  const [result, setResult] = useState<ObjectivePage>(), [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(true);
    onRead?.(false);
    void apiGet<ObjectivePage>(`/workforce/institutes/${encodeURIComponent(institute)}/employees/${encodeURIComponent(employee)}/objectives?limit=20&offset=${offset}`)
      .then(value => { if (!current()) return; if (!validObjectivePage(value, institute, employee, offset)) throw new Error("Lecture des objectifs à vérifier."); setResult(value); onRead?.(true); })
      .catch(error => { if (current()) setError(error instanceof Error ? error.message : "Objectifs indisponibles."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [offset, revision]);
  const visible = result?.page.offset === offset ? result : undefined;
  const states = { upcoming: "À venir", active: "Période en cours", ended: "Période terminée", cancelled: "Annulé, original conservé" };
  return <section aria-label="Objectifs individuels" className="employee-objectives">
    <header><h3>Objectifs individuels</h3><button disabled={loading} onClick={() => refresh(v => v+1)}>Actualiser les objectifs</button></header>
    <p>Le progrès porte sur chaque période déclarée, indépendamment du jour du calendrier individuel.</p>
    {loading && <p role="status">Lecture des objectifs…</p>}{error && <p role="alert">{error}</p>}
    {visible && <><p>Lecture au {new Date(visible.generated_at).toLocaleString("fr-CH", { timeZone: "UTC" })} UTC</p>
      {!visible.page.total && <p>Aucun objectif enregistré pour cette collaboratrice.</p>}
      <ul className="absence-list">{visible.rows.map(p => { const o = p.objective, unit = o.currency || "prestations terminées";
        const amount = (value: string) => `${value.replace(".", ",")} ${unit}`;
        return <li key={o.id}><strong>{o.title}</strong><p>{states[p.period_state]} · cible : {amount(o.target)}</p>
          <p>Du {o.first_day} au {o.last_day} inclus · fuseau déclaré : {o.timezone}</p>
          <p>{o.metric === "closed_attributed_gross" ? "CA brut attribué clôturé en interne" : "Prestations avec fin effective enregistrée"}</p>
          {onCancel && !o.cancellation && <button disabled={blocked || loading} onClick={() => onCancel(o)}>Annuler cet objectif</button>}
          {o.cancellation ? <p>Annulation : {o.cancellation.reason} · aucun progrès recalculé.</p> : <>
            <p>{p.value === null ? "Progrès non déterminable" : `Progrès enregistré : ${amount(p.value)}`} · {p.achieved === null ? "Atteinte indéterminée" : p.achieved ? "Cible atteinte à la lecture" : "Cible non atteinte à la lecture"}</p>
            {p.value === null && <p>Sous-total connu : {amount(p.known_value!)}</p>}
            <p>{p.source_count} sources · {p.missing_amount_sources} montants manquants · {p.unknown_currency_sources} devises inconnues · {p.other_currency_sources} sources dans une autre devise, sans conversion.</p></>}
          <details><summary>Provenance de l’objectif</summary><p>Original {o.id} · acteur {o.actor_id} · motif : {o.reason}</p>
            <p>Période UTC : {o.period_start} → {o.period_end}, borne finale exclue.</p><p>Enregistré : {o.created_at}</p>
            {o.cancellation && <p>Annulation {o.cancellation.id} · acteur {o.cancellation.actor_id} · enregistrée : {o.cancellation.created_at}</p>}</details></li>;
      })}</ul>
      <div className="workforce-pages"><span>Objectifs : {visible.rows.length ? offset+1 : 0}–{offset+visible.rows.length} / {visible.page.total}</span>
        <button disabled={blocked || loading || !offset} onClick={() => page(offset-20)}>Objectifs précédents</button>
        <button disabled={blocked || loading || offset+20 >= visible.page.total} onClick={() => page(offset+20)}>Objectifs suivants</button></div></>}
  </section>;
}
