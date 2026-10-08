import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { instituteMidnight } from "../outlook-utils";
import { instituteTimeZone } from "../institute-time";
import { validRevenueSlot, type RevenueSlot } from "../revenue-slot-utils";
import type { Service } from "../types";
type Props = { institute: string; timezone?: string; services: Service[] };
export function RevenueSlotOpportunity(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([props.institute, props.timezone, getAccessToken()])} {...props} />;
}
function Reader({ institute, timezone, services }: Props) {
  const token = getAccessToken(), sequence = useRef(0);
  const [service, setService] = useState(""), [horizon, setHorizon] = useState(""), [report, setReport] = useState<RevenueSlot>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const active = services.filter(s => s.status === "active"), selected = active.find(s => s.id === service);
  useEffect(() => () => { sequence.current++; }, []);
  useEffect(() => { sequence.current++; setReport(undefined); setBusy(false); setError(undefined); }, [selected?.id]);
  function change(which: "service" | "horizon", value: string) { sequence.current++; setReport(undefined); setBusy(false); setError(undefined); (which === "service" ? setService : setHorizon)(value); }
  async function read() {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    if (!current()) return;
    setReport(undefined); setBusy(true); setError(undefined);
    try {
      const end = timezone && instituteMidnight(horizon, timezone); if (!selected || !end) throw new Error();
      const result = await apiGet<unknown>(`/revenue/institutes/${encodeURIComponent(institute)}/capacity-opportunity?${new URLSearchParams({ service_id: selected.id, horizon_end: end })}`);
      if (!validRevenueSlot(result, institute, selected.id, end)) throw new Error();
      if (current()) setReport(result);
    } catch { if (current()) setError("Projection indisponible. Vérifiez la prestation et choisissez un horizon futur, puis relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  const e = report?.opportunity?.evidence;
  const clock = (at: string) => new Intl.DateTimeFormat("fr-CH", { timeZone: instituteTimeZone(timezone), year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(at));
  return <section className="revenue-guardian-panel" aria-label="Créneau potentiel sans rendez-vous" style={{ overflowWrap: "anywhere" }}>
    <h2>Créneau potentiel sans rendez-vous</h2><p>Projection d’une arrivée supplémentaire après la file actuelle, selon les compétences et ressources enregistrées. Ce créneau n’est pas réservé ; aucune affectation n’est exécutée.</p>
    <div className="revenue-guardian-period"><label>Prestation à examiner <select value={service} onChange={event => change("service",event.target.value)}><option value="">Choisir une prestation</option>{active.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>Fin de l’horizon exclue <input type="date" value={horizon} onChange={event => change("horizon",event.target.value)} /></label>
      <button disabled={busy} onClick={() => void read()}>Examiner un créneau potentiel</button></div>
    <p>Horizon jusqu’à minuit dans le fuseau de l’institut · {timezone || "Fuseau indisponible"}. Les horaires d’ouverture et la présence physique ne sont pas établis par cette projection.</p>
    {busy && <p role="status">Lecture de la capacité…</p>}{error && <p role="alert">{error}</p>}
    {report && <><p>Capture : {report.captured_at} · Fin de l’horizon : {report.horizon_end}.</p>
      {e ? <article><h3>Créneau conditionnel · {selected?.name || e.service_id}</h3><p>Collaboratrice {e.employee_id} · {clock(e.projected_start)} → {clock(e.projected_end)} · {e.duration_minutes} min.</p>
        <p>{e.prior_queue_count} tickets déjà dans la file · {e.unprojectable_prior_queue_count} sans projection exploitable. Aucune valeur de revenu estimée.</p>
        <p>Vérifiez les horaires d’ouverture et relisez la capacité avant toute affectation.</p><details><summary>Voir les conditions de projection</summary>
          <p>Prestation {e.service_id} · Début {e.projected_start} · Fin {e.projected_end}.</p><p>Compétences requises : {e.required_skills.length ? e.required_skills.join(", ") : "aucune exigence enregistrée"}.</p>
          <p>Ressources requises : {e.resource_needs.length ? "conditions ci-dessous" : "aucune exigence enregistrée"}.</p>{e.resource_needs.map(n => <p key={JSON.stringify([n.kind,n.capability])}>{n.quantity} × {({ room: "cabine", equipment: "équipement", bed: "lit", chair: "fauteuil", device: "appareil" })[n.kind]} · Capacité : {n.capability || "sans capacité spécifique"}</p>)}
          <p>État courant du moteur de file ; aucune heure d’ouverture, disponibilité physique, réservation ni promesse de prise en charge déduite.</p></details></article>
        : <p>{report.unavailable_reason === "resource_configuration_missing" ? "Configuration des ressources manquante pour cette prestation." : report.unavailable_reason === "outside_horizon" ? "Le créneau projeté se termine après l’horizon choisi." : "Capacité inconnue pour cette arrivée supplémentaire."} Aucun créneau ni montant déduit.</p>}</>}
  </section>;
}
