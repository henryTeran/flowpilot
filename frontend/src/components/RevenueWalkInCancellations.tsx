import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { instituteMidnight } from "../outlook-utils";
import { certificationInstant } from "../certification-utils";
import { revenueMoney } from "../revenue-utils";
import { validWalkInCancellations, type WalkInCancellations } from "../revenue-walk-in-utils";

export function RevenueWalkInCancellations(props: { institute: string; timezone?: string }) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([props.institute, props.timezone, getAccessToken()])} {...props} />;
}
function Reader({ institute, timezone }: { institute: string; timezone?: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [start, setStart] = useState(""), [end, setEnd] = useState(""), [report, setReport] = useState<WalkInCancellations>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  function change(which: "start" | "end", value: string) { sequence.current++; setReport(undefined); setBusy(false); setError(undefined); (which === "start" ? setStart : setEnd)(value); }
  async function load(offset = 0) {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    if (!current()) return;
    setReport(undefined); setBusy(true); setError(undefined);
    try {
      const from = timezone && instituteMidnight(start, timezone), until = timezone && instituteMidnight(end, timezone);
      if (!from || !until || certificationInstant(from)! >= certificationInstant(until)!) throw new Error();
      const period = { start: from, end: until };
      const result = await apiGet<WalkInCancellations>(`/revenue/institutes/${encodeURIComponent(institute)}/walk-in-cancellations?${new URLSearchParams({ ...period, offset: String(offset), limit: "20" })}`);
      if (!await validWalkInCancellations(result, institute, period, offset)) throw new Error();
      if (current()) setReport(result);
    } catch { if (current()) setError("Annulations indisponibles. Vérifiez la période et relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <section className="revenue-guardian-panel" aria-label="Annulations sans rendez-vous" style={{ overflowWrap: "anywhere" }}>
    <h2>Annulations sans rendez-vous</h2>
    <p>Conditions commerciales enregistrées à l’annulation. Elles ne prouvent ni paiement, ni perte de revenu, ni présence physique. Aucun suivi n’est déclenché.</p>
    <p>Journées terminées de l’institut · {timezone || "Fuseau indisponible"}. Date d’annulation : début inclus, fin exclue.</p>
    <div className="revenue-guardian-period"><label>Début des annulations <input type="date" value={start} onChange={e => change("start", e.target.value)} /></label>
      <label>Fin des annulations exclue <input type="date" value={end} onChange={e => change("end", e.target.value)} /></label>
      <button disabled={busy} onClick={() => void load()}>Lire les annulations sans rendez-vous</button></div>
    {busy && <p role="status">Lecture des annulations…</p>}{error && <p role="alert">{error}</p>}
    {report && <>
      <p>{report.page.total} annulations · {report.retained_terms_count} avec conditions conservées · {report.legacy_unpriced_count} anciennes sans preuve tarifaire. Totaux de toute la période, indépendants de la page.</p>
      {report.retained_amounts.map(g => <article key={g.currency || "unknown"}><h3>{g.currency || "Devise inconnue"} · {g.source_count} paniers conservés</h3>
        {g.currency ? <p>{g.known_amount_count ? `${revenueMoney(g.known_gross_minor)} ${g.currency}` : "Aucun montant connu"} · {g.complete_gross_minor === null ? "Sous-total connu, incomplet" : "Total commercial enregistré de ce groupe"}.</p> : <p>Devise inconnue : aucun montant monétaire affiché.</p>}
        <p>{g.known_amount_count} montants connus · {g.missing_amount_count} manquants · {g.invalid_amount_count} invalides. Les annulations anciennes sans preuve sont exclues de ces groupes.</p></article>)}
      <p>Capture : {report.window.captured_at} · {report.opportunities.length ? `${report.page.offset+1}–${report.page.offset+report.opportunities.length}` : "0"} sur {report.page.total}. Chaque page est une nouvelle lecture.</p>
      {report.opportunities.map(o => { const e = o.evidence, saved = e.original, t = saved?.terms; return <article key={e.event_id}>
        <h3>Ticket annulé {e.ticket_id}</h3><p>Événement {e.event_id} · {e.occurred_at}</p>
        <p>{o.estimated_value ? `Valeur commerciale conservée : ${revenueMoney(o.estimated_value.amount_minor)} ${o.estimated_value.currency}.` : !saved ? "Annulation ancienne sans preuve tarifaire : valeur indisponible." : t?.currency === null ? "Devise inconnue : valeur indisponible." : `Montant ${t?.amount_quality === "missing" ? "manquant" : "invalide"} : valeur indisponible.`}</p>
        <p>Vérifiez l’annulation et ses conditions sources avant toute démarche de récupération.</p>
        {t && saved && <details><summary>Voir les conditions conservées</summary><p>Auteur {t.actor_id ?? "non renseigné"} · Transition {t.previous_status} → {t.status} · Cliente {t.customer_id ?? "non renseignée"}</p>
          <p>Empreinte : {saved.fingerprint}</p><p>{t.lines.length} lignes du panier, y compris les lignes retirées. Les totaux de ligne ne remplacent pas le montant du panier.</p>
          {t.lines.map(l => <div key={l.id}><h4>Ligne {l.id} · Prestation {l.service_id}</h4><p>{l.quantity} unités · Durée unitaire {l.duration_minutes} min · Catégorie enregistrée : {l.category || "non renseignée"}</p>
            <p>Prix unitaire : {t.currency && l.unit_quality === "known" ? `${revenueMoney(l.unit_minor!)} ${t.currency}` : t.currency === null ? "devise inconnue" : l.unit_quality === "missing" ? "manquant" : "invalide"} · Total de ligne : {t.currency && l.total_quality === "known" ? `${revenueMoney(l.total_minor!)} ${t.currency}` : t.currency === null ? "devise inconnue" : l.total_quality === "missing" ? "manquant" : "invalide"}.</p>
            <p>{l.removed_at ? `Retirée de la facture le ${l.removed_at}` : "Non retirée de la facture à l’annulation"}.</p></div>)}</details>}
      </article>; })}
      <div className="revenue-guardian-period"><button disabled={report.page.offset === 0} onClick={() => void load(Math.max(0, report.page.offset-20))}>Annulations précédentes</button>
        <button disabled={report.page.offset+report.opportunities.length >= report.page.total} onClick={() => void load(report.page.offset+20)}>Annulations suivantes</button></div>
    </>}
  </section>;
}
