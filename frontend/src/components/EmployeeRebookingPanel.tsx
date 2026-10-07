import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validRebookingDay, rebookingStates, type RebookingDay, type RebookingState } from "../rebooking-utils";
import { instituteSlot } from "../institute-calendar";
type Props = { institute: string; employee: string; day: string; start: string; end: string; timezone: string };
const labels: Record<RebookingState, string> = { cancelled_declaration: "Déclarations annulées", future_recording: "Enregistrements futurs à cette lecture",
  unknown_target: "Retour non déterminable", cancelled_booking: "Réservations annulées", no_show: "Rendez-vous non honorés", booked_return: "Retours réservés", completed_return: "Retours effectivement terminés" };
export function EmployeeRebookingPanel(props: Props) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <Reading key={JSON.stringify([props, getAccessToken()])} {...props} />;
}
function Reading({ institute, employee, day, start, end, timezone }: Props) {
  const token = getAccessToken(), [offset, page] = useState(0), [revision, refresh] = useState(0);
  const [result, setResult] = useState<RebookingDay>(), [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(true);
    void apiGet<RebookingDay>(`/workforce/institutes/${encodeURIComponent(institute)}/employees/${encodeURIComponent(employee)}/rebooking-day?day=${day}&limit=20&offset=${offset}`)
      .then(v => { if (!current()) return; if (!validRebookingDay(v, institute, employee, day, start, end, timezone, offset)) throw new Error("Lecture du rebooking à vérifier."); setResult(v); })
      .catch(e => { if (current()) setError(e instanceof Error ? e.message : "Rebooking indisponible."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [offset, revision]);
  const visible = result?.page.offset === offset ? result : undefined;
  const display = (value: string) => {
    const slot = instituteSlot(value, timezone)!, minutes = Math.abs(slot.offset)/60000;
    return `${new Date(value).toLocaleString("fr-CH", { timeZone: timezone })} (UTC${slot.offset < 0 ? "−" : "+"}${String(Math.floor(minutes/60)).padStart(2, "0")}:${String(minutes%60).padStart(2, "0")})`;
  };
  return <section aria-label="Rebooking déclaré" className="employee-rebooking">
    <header><h3>Rebooking déclaré</h3><button disabled={loading} onClick={() => refresh(v => v+1)}>Actualiser le rebooking</button></header>
    <p>Déclarations enregistrées le {day} · {timezone}. Une réservation ne prouve pas un retour effectué ; l’attribution complète et le taux de conversion restent inconnus.</p>
    {loading && <p role="status">Lecture du rebooking…</p>}{error && <p role="alert">{error}</p>}
    {visible && <><p>Lecture au {new Date(visible.generated_at).toLocaleString("fr-CH", { timeZone: "UTC" })} UTC</p><p>Journal complet de ce jour : {visible.page.total} déclarations.</p>
      {rebookingStates.filter(k => visible.counts[k] > 0 || k === "booked_return" || k === "completed_return").map(k => <p key={k}>{labels[k]} : {visible.counts[k]}</p>)}
      {!visible.page.total && <p>Aucune déclaration enregistrée ce jour. Cela ne signifie pas un échec de rebooking.</p>}
      <ul className="absence-list">{visible.rows.map(s => { const o = s.original; return <li key={o.id}><strong>{labels[s.state]}</strong>
        <p>{o.source_kind === "session" ? "Prestation walk-in" : "Rendez-vous"} terminé le {display(o.source_capture.actual_end)} · réservation créée le {display(o.booking_capture.created_at)}.</p>
        <details><summary>Provenance du rebooking</summary><p>Original {o.id} · prestation {o.source_id} · réservation {o.target_appointment_id} · événement {o.booking_capture.creation_event_id}</p>
          <p>Enregistré au {o.created_at} · acteur {o.actor_id} · motif {o.reason}</p>
          <p>Début effectif original : {o.source_capture.actual_start} · fin : {o.source_capture.actual_end}</p>
          <p>Créneau à la création : {o.booking_capture.original_start} – {o.booking_capture.original_end}</p>
          <p>Créneau lors de la déclaration : {o.booking_capture.current_start} – {o.booking_capture.current_end}</p>
          <p>Lien client actuel : {!s.target_customer_id ? "Inconnu" : s.target_customer_id === o.source_capture.customer_id ? "Identique au lien déclaré" : "Différent du lien déclaré"}</p>
          <p>État actuel : {s.target_status || "Inconnu"} · début effectif du retour : {s.actual_start || "Inconnu"} · fin : {s.actual_end || "Inconnue"}</p>
          {o.cancellation && <p>Annulation {o.cancellation.id} · {o.cancellation.created_at} · acteur {o.cancellation.actor_id} · motif {o.cancellation.reason}</p>}</details></li>; })}</ul>
      <div className="workforce-pages"><span>Sources : {visible.rows.length ? offset+1 : 0}–{offset+visible.rows.length} / {visible.page.total}</span>
        <button disabled={loading || !offset} onClick={() => page(offset-20)}>Rebooking précédent</button><button disabled={loading || offset+20 >= visible.page.total} onClick={() => page(offset+20)}>Rebooking suivant</button></div></>}
  </section>;
}
