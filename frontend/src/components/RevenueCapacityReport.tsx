import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { capacityDayWindow, validRevenueCapacity, type RevenueCapacity } from "../revenue-capacity-utils";
import { formatWorkDuration } from "../work-hours-utils";
import { occupationDiagnosticKeys } from "../occupation-math";
function utilization(v: { numerator: string; denominator: string } | null) {
  if (!v) return "indisponible";
  const n = BigInt(v.numerator) * 10000n, d = BigInt(v.denominator), rounded = (2n*n + d)/(2n*d);
  return `${n % d ? "≈ " : ""}${rounded/100n},${String(rounded%100n).padStart(2, "0")} %`;
}
export function RevenueCapacityReport({ institute, timezone }: { institute: string; timezone?: string }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([institute, timezone, getAccessToken()])} institute={institute} timezone={timezone} />;
}
function Reader({ institute, timezone }: { institute: string; timezone?: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [day, setDay] = useState(""), [report, setReport] = useState<RevenueCapacity>();
  const [loading, setLoading] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  function change(value: string) { sequence.current++; setDay(value); setReport(undefined); setLoading(false); setError(undefined); }
  async function load(offset = 0) {
    const request = ++sequence.current, current = () => sequence.current === request && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    setReport(undefined); setError(undefined);
    if (!timezone || !capacityDayWindow(day, timezone)) { setError("Choisissez une journée terminée et vérifiez le fuseau de l’institut."); return; }
    setLoading(true);
    try {
      const params = new URLSearchParams({ day, offset: String(offset), limit: "20" });
      const value = await apiGet<unknown>(`/revenue/institutes/${encodeURIComponent(institute)}/capacity?${params}`);
      if (!validRevenueCapacity(value, institute, day, timezone, offset)) throw new Error("Invalid recorded capacity");
      if (current()) setReport(value);
    } catch { if (current()) setError("Capacités enregistrées indisponibles. Vérifiez la journée et relancez la lecture."); }
    finally { if (current()) setLoading(false); }
  }
  return <section className="revenue-guardian-panel" aria-label="Capacités enregistrées">
    <h2>Capacités enregistrées</h2>
    <p>Horaires déclarés et activités terminées enregistrées. Les durées additionnent le temps des collaboratrices ; elles ne prouvent ni leur présence réelle ni des créneaux réservables.</p>
    <p>Journée de l’institut · {timezone || "Fuseau indisponible"}</p>
    <div className="revenue-guardian-period"><label>Journée des capacités <input type="date" value={day} onChange={e => change(e.target.value)} /></label>
      <button disabled={loading} onClick={() => void load()}>Lire les capacités enregistrées</button></div>
    {loading && <p role="status">Lecture des capacités…</p>}{error && <p role="alert">{error}</p>}
    {report && <>
      <p>Lecture du {report.window.captured_at} · {report.employee_count} collaboratrices dans l’institut, y compris les profils indisponibles ou archivés.</p>
      <h3>Totaux de toutes les collaboratrices</h3>
      <p>Horaires déclarés connus : {formatWorkDuration(report.known_declared_union_duration_us)}.</p>
      <p>Activité terminée dans les horaires déclarés : {formatWorkDuration(report.known_covered_busy_duration_us)}.</p>
      <p>Activité terminée hors horaires déclarés : {formatWorkDuration(report.known_outside_declared_work_duration_us)}.</p>
      <p>Durée déclarée sans activité enregistrée : {report.recorded_unoccupied_duration_us === null ? "indisponible" : formatWorkDuration(report.recorded_unoccupied_duration_us)}.</p>
      <p>Utilisation enregistrée : {utilization(report.recorded_utilization_ratio)}.</p>
      <p>{report.employees_without_usable_hours} collaboratrices sans horaires exploitables · {report.employees_with_uncertain_activity} avec activité incertaine. Ces catégories peuvent se recouper.</p>
      <h3>Preuves de la page courante</h3>
      <p>{report.rows.length ? `${report.page.offset + 1}–${report.page.offset + report.rows.length}` : "0"} sur {report.page.total} collaboratrices. Chaque page est une nouvelle lecture ; les totaux couvrent tout l’institut.</p>
      {report.rows.map(r => <article key={r.employee_id}>
        <h4>Collaboratrice {r.employee_id}</h4>
        <p>Horaires connus : {formatWorkDuration(r.evidence.work_hours.known_union_duration_us)} · Activité dans ces horaires : {formatWorkDuration(r.evidence.covered_busy_duration_us)}.</p>
        <p>Durée déclarée sans activité enregistrée : {r.recorded_unoccupied_duration_us === null ? "indisponible" : formatWorkDuration(r.recorded_unoccupied_duration_us)} · Utilisation : {utilization(r.recorded_utilization_ratio)}.</p>
        <p>{r.evidence.work_hours.active_sources} déclarations actives · {r.evidence.work_hours.overlap_sources} chevauchements · {r.evidence.page.total} sources d’activité.</p>
        <p>Activités incertaines : {occupationDiagnosticKeys.filter(k => k !== "retained").reduce((n, k) => n + r.evidence.diagnostics[k], 0)}. Au plus une source d’activité est visible par collaboratrice dans cette synthèse.</p>
        <details><summary>Voir les sources visibles de {r.employee_id}</summary>
          {r.evidence.rows.map(s => <p key={`${s.kind}/${s.id}`}>{s.kind === "session" ? "Session" : "Rendez-vous"} {s.id} · {s.exclusion ? "Activité exclue ou incomplète" : `${formatWorkDuration(s.duration_us!)} retenues`}.</p>)}
          {!r.evidence.rows.length && <p>Aucune source d’activité dans la journée.</p>}
          <p>{r.evidence.work_hours.rows.length} déclarations horaires visibles sur {r.evidence.work_hours.page.total}.</p>
          {r.evidence.work_hours.rows.map(s => <p key={s.interval.id}>Déclaration {s.interval.id} · {s.interval.start_time} → {s.interval.end_time} · {s.exclusion ? "Exclue de la durée enregistrée" : "Retenue"}.</p>)}
        </details>
      </article>)}
      <div className="revenue-guardian-period"><button disabled={report.page.offset === 0} onClick={() => void load(Math.max(0, report.page.offset - 20))}>Collaboratrices précédentes</button>
        <button disabled={report.page.offset + report.rows.length >= report.page.total} onClick={() => void load(report.page.offset + 20)}>Collaboratrices suivantes</button></div>
    </>}
  </section>;
}
