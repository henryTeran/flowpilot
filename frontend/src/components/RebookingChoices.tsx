import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validSourceChoices, validTargetChoices, sameExecution, type SourceChoices, type TargetChoices } from "../rebooking-options";
import type { ExecutionCapture, BookingCapture } from "../rebooking-utils";
import { instituteSlot } from "../institute-calendar";
export type RebookingSelection = { source: ExecutionCapture; target: BookingCapture };
type Props = { institute: string; employee: string; day: string; start: string; end: string; timezone: string; disabled?: boolean;
  onSelection: (value: RebookingSelection | undefined) => void };
const sourceLabels = { invalid_execution: "Instants effectifs incohérents ou incomplets", future_end: "Fin future à cette lecture",
  unknown_customer: "Lien client inconnu", already_attributed: "Prestation déjà attribuée" };
export function RebookingChoices(props: Props) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <Choices key={JSON.stringify([props.institute, props.employee, props.day, props.start, props.end, props.timezone, getAccessToken()])} {...props} />;
}
function Choices({ institute, employee, day, start, end, timezone, disabled, onSelection }: Props) {
  const token = getAccessToken(), base = `/workforce/institutes/${encodeURIComponent(institute)}`;
  const [sourceOffset, sourcePage] = useState(0), [targetOffset, targetPage] = useState(0), [revision, refresh] = useState(0);
  const [sources, setSources] = useState<SourceChoices>(), [targets, setTargets] = useState<TargetChoices>();
  const [sourceRevision, setSourceRevision] = useState(-1);
  const [source, chooseSource] = useState<ExecutionCapture>(), [target, chooseTarget] = useState<BookingCapture>();
  const [sourceLoading, setSourceLoading] = useState(false), [targetLoading, setTargetLoading] = useState(false), [error, setError] = useState<string>();
  const scope = useRef({ source, sourceOffset, targetOffset, revision, disabled }); scope.current = { source, sourceOffset, targetOffset, revision, disabled };
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken() && scope.current.sourceOffset === sourceOffset
      && scope.current.revision === revision && scope.current.disabled === disabled;
    setSources(undefined); setTargets(undefined); chooseSource(undefined); chooseTarget(undefined); targetPage(0); setError(undefined); setSourceLoading(false);
    if (current()) onSelection(undefined);
    if (disabled || !employee) return;
    setSourceLoading(true);
    void apiGet<SourceChoices>(`${base}/employees/${encodeURIComponent(employee)}/rebooking-sources?day=${day}&limit=20&offset=${sourceOffset}`)
      .then(v => { if (!current()) return; if (!validSourceChoices(v, institute, employee, day, start, end, timezone, sourceOffset)) throw new Error("Choix de prestation à vérifier."); setSources(v); setSourceRevision(revision); })
      .catch(e => { if (current()) setError(e instanceof Error ? e.message : "Prestations indisponibles."); })
      .finally(() => { if (current()) setSourceLoading(false); });
    return () => { disposed = true; };
  }, [sourceOffset, revision, disabled]);
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken() && scope.current.source === source
      && scope.current.targetOffset === targetOffset && scope.current.revision === revision && scope.current.disabled === disabled;
    setTargets(undefined); chooseTarget(undefined); setTargetLoading(false);
    if (current()) onSelection(undefined);
    if (!source || disabled) return;
    setError(undefined);
    setTargetLoading(true);
    void apiGet<TargetChoices>(`${base}/rebooking-targets/${source.kind}/${encodeURIComponent(source.id)}?limit=20&offset=${targetOffset}`)
      .then(v => { if (!current()) return; if (!validTargetChoices(v, institute, source, targetOffset)) throw new Error("Choix de réservation à vérifier."); setTargets(v); })
      .catch(e => { if (current()) setError(e instanceof Error ? e.message : "Réservations indisponibles."); })
      .finally(() => { if (current()) setTargetLoading(false); });
    return () => { disposed = true; };
  }, [source, targetOffset, disabled]);
  const display = (value: string) => {
    const slot = instituteSlot(value, timezone)!, minutes = Math.abs(slot.offset)/60000;
    return `${new Date(value).toLocaleString("fr-CH", { timeZone: timezone })} (UTC${slot.offset < 0 ? "−" : "+"}${String(Math.floor(minutes/60)).padStart(2, "0")}:${String(minutes%60).padStart(2, "0")})`;
  };
  return <section className="rebooking-choices" aria-label="Sélection des sources de rebooking">
    <p>Prestations terminées le {day} · {timezone}. Les fins inconnues ne sont pas déduites du planning.</p>
    <button type="button" disabled={disabled || sourceLoading} onClick={() => refresh(v => v+1)}>Actualiser les choix de rebooking</button>
    {sourceLoading && <p role="status">Lecture des prestations terminées…</p>}{targetLoading && <p role="status">Lecture des réservations liées…</p>}
    {error && <p role="alert">{error}</p>}
    {sources && sourceRevision === revision && sources.page.offset === sourceOffset && <><p>Lecture des prestations au {display(sources.generated_at)} · couverture complète inconnue.</p>
      <label>Prestation terminée<select required disabled={disabled || sourceLoading} value={source ? `${source.kind}:${source.id}` : ""} onChange={e => {
        if (disabled || token !== getAccessToken()) return;
        const row = sources.rows.find(s => `${s.kind}:${s.id}` === e.target.value); chooseSource(row?.capture || undefined); chooseTarget(undefined);
        setTargets(undefined); targetPage(0); setError(undefined); onSelection(undefined);
      }}><option value="">Choisir une prestation</option>{sources.rows.map(s => <option key={`${s.kind}:${s.id}`} value={`${s.kind}:${s.id}`} disabled={s.exclusion !== null}>
        {s.kind === "session" ? "Walk-in" : "Rendez-vous"} · fin {display(s.actual_end)}{s.exclusion ? ` · ${sourceLabels[s.exclusion]}` : " · lien client enregistré"}</option>)}</select></label>
      {!sources.rows.length && <p>Aucune prestation terminée localisable sur cette page ; cela ne prouve pas une activité nulle.</p>}
      <div className="workforce-pages"><span>Prestations : {sources.rows.length ? sourceOffset+1 : 0}–{sourceOffset+sources.rows.length} / {sources.page.total}</span>
        <button type="button" disabled={disabled || sourceLoading || !sourceOffset} onClick={() => sourcePage(sourceOffset-20)}>Prestations précédentes</button>
        <button type="button" disabled={disabled || sourceLoading || sourceOffset+20 >= sources.page.total} onClick={() => sourcePage(sourceOffset+20)}>Prestations suivantes</button></div></>}
    {source && sourceRevision === revision && sources?.page.offset === sourceOffset && <details><summary>Prestation sélectionnée</summary><p>Source {source.kind} · {source.id} · prestation {source.service_id}</p><p>{source.actual_start} – {source.actual_end}</p></details>}
    {targets && targets.page.offset === targetOffset && sourceRevision === revision && sources?.page.offset === sourceOffset && source && sameExecution(targets.source, source) && <><p>Réservations du même lien client · lecture au {display(targets.generated_at)}.</p>
      <label>Réservation liée<select required disabled={disabled || targetLoading} value={target?.appointment_id || ""} onChange={e => {
        if (disabled || token !== getAccessToken() || !source || !sameExecution(targets.source, source)) return;
        const row = targets.rows.find(s => s.id === e.target.value), capture = row?.capture || undefined;
        chooseTarget(capture); onSelection(source && capture ? { source, target: capture } : undefined);
      }}><option value="">Choisir une réservation</option>{targets.rows.map(s => <option key={s.id} value={s.id} disabled={s.exclusion !== null}>
        {s.booked_start ? display(s.booked_start) : "Créneau enregistré inconnu"}{s.exclusion ? ` · ${s.exclusion === "already_attributed" ? "Réservation déjà attribuée" : "Provenance ou chronologie à vérifier"}` : " · création originale vérifiée"}</option>)}</select></label>
      {!targets.rows.length && <p>Aucune réservation active liée à ce client sur cette page.</p>}
      <div className="workforce-pages"><span>Réservations : {targets.rows.length ? targetOffset+1 : 0}–{targetOffset+targets.rows.length} / {targets.page.total}</span>
        <button type="button" disabled={disabled || targetLoading || !targetOffset} onClick={() => { targetPage(targetOffset-20); onSelection(undefined); }}>Réservations précédentes</button>
        <button type="button" disabled={disabled || targetLoading || targetOffset+20 >= targets.page.total} onClick={() => { targetPage(targetOffset+20); onSelection(undefined); }}>Réservations suivantes</button></div></>}
    {target && targets?.page.offset === targetOffset && sourceRevision === revision && <details><summary>Réservation sélectionnée</summary><p>Original {target.appointment_id} · événement {target.creation_event_id} · création {target.created_at}</p>
      <p>Créneau à la création : {target.original_start} – {target.original_end}</p><p>Créneau à la lecture : {target.current_start} – {target.current_end}</p></details>}
  </section>;
}
