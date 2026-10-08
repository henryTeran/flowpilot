import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validWaitlistOriginalAudit, type WaitlistOriginalAudit } from "../waitlist-original-utils";

export function WaitlistOriginalHistory({ institute, timezone }: { institute: string; timezone?: string }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([institute, timezone, getAccessToken()])} institute={institute} timezone={timezone} />;
}
function Reader({ institute, timezone }: { institute: string; timezone?: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [report, setReport] = useState<WaitlistOriginalAudit>(), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  function date(value: string) {
    try { return new Intl.DateTimeFormat("fr-CH", { timeZone: timezone || "UTC", dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
    catch { return value; }
  }
  async function load(offset = 0) {
    const request = ++sequence.current;
    const current = () => request === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    setReport(undefined); setError(undefined); setBusy(true);
    try {
      const value = await apiGet<WaitlistOriginalAudit>(`/waitlist/institutes/${encodeURIComponent(institute)}/originals?offset=${offset}&limit=20`);
      if (!await validWaitlistOriginalAudit(value, institute, offset)) throw new Error("Invalid waitlist original audit");
      if (current()) setReport(value);
    } catch { if (current()) setError("Originaux de liste d’attente à vérifier. Relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <section className="revenue-guardian-panel" aria-label="Demandes de liste d’attente conservées">
    <h2>Demandes de liste d’attente conservées</h2>
    <p>Déclarations originales : leur conservation ne prouve ni activation actuelle, ni créneau disponible, ni autorisation de contact.</p>
    <p>Horaires : {timezone || "UTC — fuseau institut indisponible"}.</p>
    <div className="revenue-guardian-period"><button disabled={busy} onClick={() => void load()}>Lire les demandes conservées</button></div>
    {busy && <p role="status">Lecture des originaux…</p>}{error && <p role="alert">{error}</p>}
    {report && <>
      <p>{report.total} déclarations conservées · lecture au {date(report.captured_at)}.</p>
      <p>{report.originals.length ? `${report.offset+1}–${report.offset+report.originals.length}` : "0"} sur {report.total}. Chaque page relit les sources.</p>
      {report.originals.map(({ original: o, fingerprint }) => <article key={o.id}>
        <h3>{o.reason}</h3><p>Cliente {o.demand.customer_id} · prestation {o.demand.service_id} · durée déclarée {o.demand.duration_minutes} min.</p>
        <p>Conservée le {date(o.created_at)} · auteur {o.actor_id}.</p>
        <p>Contraintes {o.demand.constraints_review === "confirmed" ? "relues selon déclaration" : "inconnues : matching à vérifier"}.</p>
        <ul>{o.demand.availability.map((window, index) => <li key={index}>Disponibilité déclarée du {date(window.start)} au {date(window.end)}.</li>)}</ul>
        <details><summary>Voir l’original et les sources de cette demande</summary>
          <p>Original {o.id} · clé {o.idempotency_key} · empreinte {fingerprint}.</p>
          <p>Inscription enregistrée le {date(o.source.registered_at)} · prestation source {o.source.service_id} · durée {o.source.duration_minutes} min.</p>
          <p>Disponibilité : {o.demand.availability_evidence}</p><p>Contraintes : {o.demand.constraints_evidence || "Aucune preuve déclarée"}</p>
          <p>Collaboratrices autorisées selon déclaration : {o.demand.allowed_employee_ids.length ? o.demand.allowed_employee_ids.join(", ") : "aucune restriction déclarée"}.</p>
          <pre>{JSON.stringify(o, null, 2)}</pre>
        </details>
      </article>)}
      <div className="revenue-guardian-period">
        <button disabled={busy || report.offset === 0} onClick={() => void load(Math.max(0, report.offset-20))}>Demandes précédentes</button>
        <button disabled={busy || report.offset+report.originals.length >= report.total} onClick={() => void load(report.offset+20)}>Demandes suivantes</button>
      </div>
    </>}
  </section>;
}
