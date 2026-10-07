import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validWorkHours, formatWorkDuration, type WorkHours } from "../work-hours-utils";
import { instituteSlot } from "../institute-calendar";
type Props = { institute: string; employee: string; day: string; start: string; end: string; timezone: string };
export function EmployeeWorkHoursPanel(props: Props) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <Hours key={JSON.stringify([props.institute, props.employee, props.day, props.start, props.end, props.timezone, getAccessToken()])} {...props} />;
}
function Hours({ institute, employee, day, start, end, timezone }: Props) {
  const token = getAccessToken(), [offset, page] = useState(0), [revision, refresh] = useState(0);
  const [result, setResult] = useState<WorkHours>(), [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(true);
    void apiGet<WorkHours>(`/workforce/institutes/${encodeURIComponent(institute)}/employees/${encodeURIComponent(employee)}/work-hours?day=${day}&limit=20&offset=${offset}`)
      .then(value => { if (!current()) return; if (!validWorkHours(value, institute, employee, day, start, end, timezone, offset)) throw new Error("Lecture des heures à vérifier."); setResult(value); })
      .catch(error => { if (current()) setError(error instanceof Error ? error.message : "Heures indisponibles."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [offset, revision]);
  const visible = result?.page.offset === offset ? result : undefined;
  const display = (instant: string) => {
    const slot = instituteSlot(instant, timezone)!, minutes = Math.abs(slot.offset)/60000;
    return `${new Date(instant).toLocaleString("fr-CH", { timeZone: timezone })} (UTC${slot.offset < 0 ? "−" : "+"}${String(Math.floor(minutes/60)).padStart(2, "0")}:${String(minutes%60).padStart(2, "0")})`;
  };
  return <section aria-label="Heures effectives déclarées" className="employee-work-hours">
    <header><h3>Heures effectives déclarées</h3><button disabled={loading} onClick={() => refresh(v => v+1)}>Actualiser les heures</button></header>
    <p>Jour : {day} · {timezone}. Déclarations de la responsable, hors pauses ; elles ne prouvent pas une présence complète.</p>
    {loading && <p role="status">Lecture des heures…</p>}{error && <p role="alert">{error}</p>}
    {visible && <><p>Lecture au {new Date(visible.generated_at).toLocaleString("fr-CH", { timeZone: "UTC" })} UTC</p>
      <p>{visible.recorded_duration_us === null ? "Total enregistré non déterminable" : `Durée enregistrée sans double comptage : ${formatWorkDuration(visible.recorded_duration_us)}`}</p>
      <p>Sous-total connu : {formatWorkDuration(visible.known_union_duration_us)} · {visible.active_sources} déclarations non annulées.</p>
      {visible.future_end_sources > 0 && <p>{visible.future_end_sources} fins futures à la lecture, exclues du sous-total.</p>}
      {visible.overlap_sources > 0 && <p>{visible.overlap_sources} chevauchements fusionnés · somme déclarée : {formatWorkDuration(visible.known_declared_duration_us)}.</p>}
      {!visible.page.total && <p>Aucune déclaration enregistrée sur ce jour. Les heures travaillées restent inconnues.</p>}
      <ul className="absence-list">{visible.rows.map(s => <li key={s.interval.id}><strong>{formatWorkDuration(s.duration_us)} sur le jour sélectionné</strong>
        <p>{display(s.clipped_start)} → {display(s.clipped_end)}</p>
        <p>{s.exclusion === "cancelled" ? "Annulé, original conservé, durée exclue" : s.exclusion === "future_end" ? "Fin future à la lecture, durée exclue" : "Déclaration retenue"}</p>
        <p>{s.interval.reason}</p><details><summary>Provenance des heures</summary><p>Original {s.interval.id} · acteur {s.interval.actor_id}</p>
          <p>Intervalle original : {s.interval.start_time} → {s.interval.end_time}</p><p>Intervalle retenu sur le jour : {s.clipped_start} → {s.clipped_end}</p>
          <p>Enregistré : {s.interval.created_at}</p>{s.interval.cancellation && <p>Annulation {s.interval.cancellation.id} · {s.interval.cancellation.reason} · acteur {s.interval.cancellation.actor_id} · {s.interval.cancellation.created_at}</p>}</details></li>)}</ul>
      <div className="workforce-pages"><span>Déclarations : {visible.rows.length ? offset+1 : 0}–{offset+visible.rows.length} / {visible.page.total}</span>
        <button disabled={loading || !offset} onClick={() => page(offset-20)}>Heures précédentes</button>
        <button disabled={loading || offset+20 >= visible.page.total} onClick={() => page(offset+20)}>Heures suivantes</button></div></>}
  </section>;
}
