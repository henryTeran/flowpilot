import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { instituteMidnight } from "../outlook-utils";
import { validBookingClosures, validPriceReferences, compatibleReference, type BookingClosures, type ClosureEvidence, type PriceReferences, type PriceReference } from "../revenue-closure-utils";
import { revenueMoney } from "../revenue-utils";
import { RevenueClosureWriter } from "./RevenueClosureWriter";
import { RevenueClosureHistory } from "./RevenueClosureHistory";
export function RevenueBookingClosures(props: { institute: string; timezone?: string }) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Workspace key={JSON.stringify([props.institute, props.timezone, getAccessToken()])} {...props} />;
}
function Workspace({ institute, timezone }: { institute: string; timezone?: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [start, setStart] = useState(""), [end, setEnd] = useState(""), [report, setReport] = useState<BookingClosures>(), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const [closure, setClosure] = useState<ClosureEvidence>(), [reference, setReference] = useState<PriceReference>(), [revision, setRevision] = useState(0);
  useEffect(() => () => { sequence.current++; }, []);
  function change(which: "start" | "end", value: string) { sequence.current++; setReport(undefined); setClosure(undefined); setReference(undefined); setError(undefined); setBusy(false); (which === "start" ? setStart : setEnd)(value); }
  async function load(offset = 0) {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    if (!current()) return;
    setReport(undefined); setClosure(undefined); setReference(undefined); setBusy(true); setError(undefined);
    try {
      const period = timezone ? { start: instituteMidnight(start, timezone), end: instituteMidnight(end, timezone) } : undefined;
      if (!period?.start || !period.end) throw new Error();
      const value = await apiGet<BookingClosures>(`/revenue/institutes/${encodeURIComponent(institute)}/booking-closures?${new URLSearchParams({ start: period.start, end: period.end, offset: String(offset), limit: "20" })}`);
      if (!validBookingClosures(value, institute, { start: period.start, end: period.end }, offset)) throw new Error();
      if (current()) setReport(value);
    } catch { if (current()) setError("Annulations à vérifier. Choisissez des journées terminées et relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <><section className="revenue-guardian-panel" aria-label="Annulations et absences déclarées">
    <h2>Annulations et absences déclarées</h2><p>Événements de réservation enregistrés, sans perte de revenu établie ni preuve de présence physique. La lecture ne déclenche aucun suivi.</p>
    <p>Journées terminées de l’institut · {timezone || "Fuseau indisponible"}. Début inclus, fin exclue ; période fondée sur la date de l’événement.</p>
    <div className="revenue-guardian-period"><label>Début des événements <input type="date" value={start} onChange={e => change("start", e.target.value)} /></label><label>Fin des événements exclue <input type="date" value={end} onChange={e => change("end", e.target.value)} /></label>
      <button disabled={busy} onClick={() => void load()}>Lire les événements terminaux</button></div>
    {busy && <p role="status">Lecture des événements…</p>}{error && <p role="alert">{error}</p>}
    {report && <><p>{report.cancelled_count} annulations · {report.no_show_count} absences déclarées · {report.unpriced_count} événements sans valeur de revenu établie. Totaux de toute la période, indépendants de la page.</p>
      <p>{report.institute_terminal_bookings_without_closure_event} réservations terminales sans événement exploitable dans tout l’institut, hors attribution à cette période. L’historique complet des réservations n’est pas établi.</p>
      <p>Capture : {report.window.captured_at} · {report.opportunities.length ? `${report.page.offset+1}–${report.page.offset+report.opportunities.length}` : "0"} sur {report.page.total}. Chaque page est une nouvelle lecture.</p>
      {report.opportunities.map(o => <article key={o.evidence.event_id}><h3>{o.evidence.event_type === "cancelled" ? "Annulation enregistrée" : "Absence déclarée"}</h3><p>Réservation {o.evidence.appointment_id} · Événement {o.evidence.event_id}</p>
        <p>Auteur {o.evidence.actor_id ?? "non renseigné"} · {o.evidence.occurred_at}</p><p>Collaboratrice {o.evidence.after.employee_id} · Prestation {o.evidence.after.service_id} · {o.evidence.after.start_time} → {o.evidence.after.end_time}</p>
        <p>Transition {o.evidence.before.status} → {o.evidence.after.status} · Aucun début, fin de prestation ou ticket d’encaissement déclaré dans cette preuve.</p>
        <p>Valeur estimée indisponible. Vérifiez la réservation et l’autorisation de contact avant tout suivi.</p>
        <div className="revenue-guardian-period"><button aria-label={`Lire les références tarifaires ${o.evidence.appointment_id}`} onClick={() => { setClosure(o.evidence); setReference(undefined); }}>Lire les références tarifaires</button></div></article>)}
      <div className="revenue-guardian-period"><button disabled={report.page.offset === 0} onClick={() => void load(Math.max(0, report.page.offset-20))}>Événements précédents</button><button disabled={report.page.offset+report.opportunities.length >= report.page.total} onClick={() => void load(report.page.offset+20)}>Événements suivants</button></div></>}
  </section>
  {closure && <References key={JSON.stringify([closure.appointment_id, closure.event_id, closure.captured_at])} institute={institute} closure={closure} onSelect={setReference} />}
  <RevenueClosureWriter institute={institute} closure={closure} reference={reference} onRetained={() => setRevision(n => n+1)} />
  <RevenueClosureHistory key={revision} institute={institute} /></>;
}
function References({ institute, closure, onSelect }: { institute: string; closure: ClosureEvidence; onSelect: (r?: PriceReference) => void }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [report, setReport] = useState<PriceReferences>(), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  useEffect(() => { void load(); return () => { sequence.current++; }; }, []); // Explicit opening of this reader is the user's read action.
  async function load(offset = 0) {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    if (!current()) return;
    setReport(undefined); setBusy(true); setError(undefined); onSelect(undefined);
    try {
      const value = await apiGet<PriceReferences>(`/revenue/institutes/${encodeURIComponent(institute)}/appointments/${encodeURIComponent(closure.appointment_id)}/price-references?offset=${offset}&limit=20`);
      if (!await validPriceReferences(value, institute, closure.appointment_id, offset)) throw new Error();
      if (current()) setReport(value);
    } catch { if (current()) setError("Références tarifaires à vérifier. Relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <section className="revenue-guardian-panel" aria-label="Références tarifaires de la réservation"><h2>Références tarifaires historiques</h2><p>Réservation {closure.appointment_id}. Ces tarifs de catalogue ne prouvent ni un prix convenu, ni l’éligibilité au tarif membre, ni un paiement.</p>
    <div className="revenue-guardian-period"><button disabled={busy} onClick={() => void load()}>Relire les références tarifaires</button></div>{busy && <p role="status">Vérification des références…</p>}{error && <p role="alert">{error}</p>}
    {report && <><p>{report.legacy_service_selection_events} sélections de prestation sans référence conservée. Capture {report.captured_at}.</p><p>{report.originals.length ? `${report.page.offset+1}–${report.page.offset+report.originals.length}` : "0"} sur {report.page.total} références.</p>
      {report.originals.map(r => <article key={r.terms.event_id}><h3>Référence du {r.terms.occurred_at}</h3><p>Prestation {r.terms.service_id} · Durée catalogue {r.terms.duration_min}–{r.terms.duration_max ?? "maximum non renseigné"} min · Auteur {r.terms.actor_id ?? "non renseigné"}.</p>
        {(["member", "passage"] as const).map(rate => <p key={rate}>Tarif {rate === "member" ? "membre" : "passage"} : {r.terms.currency && r.terms[`${rate}_minor`] !== null ? `${revenueMoney(r.terms[`${rate}_minor`]!)} ${r.terms.currency}` : "montant monétaire indisponible"} · {r.terms[`${rate}_quality`] === "known" ? "montant connu" : r.terms[`${rate}_quality`] === "missing" ? "montant manquant" : "montant invalide"}.</p>)}
        {!r.terms.currency && <p>Devise non établie · {r.terms.currency_unavailable_reason === "future_settings" ? "Configuration postérieure à la référence" : r.terms.currency_unavailable_reason === "settings_clock_missing" ? "Configuration non datée" : "Configuration absente"}.</p>}
        <details><summary>Voir la preuve tarifaire</summary><p>Événement {r.terms.event_id} · {r.terms.event_type} · Devise configurée le {r.terms.currency_settings_at ?? "non renseigné"} par {r.terms.currency_settings_actor_id ?? "non renseigné"}.</p><p>Empreinte : {r.fingerprint}</p></details>
        <div className="revenue-guardian-period"><button aria-label={`Choisir cette référence ${r.terms.event_id}`} disabled={!compatibleReference(r, closure)} onClick={() => onSelect(r)}>Choisir cette référence</button></div>
        {!compatibleReference(r, closure) && <p>Cette référence ne correspond pas à la prestation ou à la chronologie de l’événement terminal.</p>}</article>)}
      <div className="revenue-guardian-period"><button disabled={report.page.offset === 0} onClick={() => void load(Math.max(0, report.page.offset-20))}>Références précédentes</button><button disabled={report.page.offset+report.originals.length >= report.page.total} onClick={() => void load(report.page.offset+20)}>Références suivantes</button></div></>}
  </section>;
}
