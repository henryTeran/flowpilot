import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validClosureAudit, type ClosureAudit, type ClosureEnvelope } from "../revenue-closure-utils";
import { revenueMoney } from "../revenue-utils";
export function ClosureReceipt({ value }: { value: ClosureEnvelope }) {
  const o = value.original;
  return <article><h3>{o.request.reason}</h3><p>Valorisation conservée : {o.estimated_value ? `${revenueMoney(o.estimated_value.amount_minor)} ${o.estimated_value.currency}` : "indisponible"} · Tarif {o.request.rate === "member" ? "membre" : "passage"} déclaré.</p>
    {o.unavailable_reason && <p>{o.unavailable_reason === "unknown_currency" ? "Devise non établie" : o.unavailable_reason === "missing_rate" ? "Tarif manquant" : "Tarif invalide"}.</p>}
    <p>Scénario de tarif historique : aucun prix convenu, paiement, éligibilité membre ou perte causale n’est établi. Aucun suivi n’a été déclenché.</p>
    <details><summary>Voir l’original de valorisation</summary><p>Original {o.id} · Réservation {o.appointment_id} · Auteur {o.actor_id} · {o.created_at}</p>
      <p>Référence {o.request.reference_event_id} · {o.reference.terms.occurred_at} · {o.reference.terms.service_id} · {o.reference.fingerprint}</p>
      <p>Événement terminal {o.evidence.event_id} · {o.evidence.event_type} · {o.evidence.occurred_at} · Auteur {o.evidence.actor_id ?? "non renseigné"}</p>
      <p>Créneau {o.evidence.after.start_time} → {o.evidence.after.end_time} · Collaboratrice {o.evidence.after.employee_id}</p><p>Clé : {o.idempotency_key}</p><p>Empreinte de l’original : {value.fingerprint}</p></details></article>;
}
export function RevenueClosureHistory({ institute }: { institute: string }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([institute, getAccessToken()])} institute={institute} />;
}
function Reader({ institute }: { institute: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [report, setReport] = useState<ClosureAudit>(), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  async function load(offset = 0) {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    if (!current()) return;
    setReport(undefined); setBusy(true); setError(undefined);
    try {
      const value = await apiGet<ClosureAudit>(`/revenue/institutes/${encodeURIComponent(institute)}/closure-value-originals?offset=${offset}&limit=20`);
      if (!await validClosureAudit(value, institute, offset)) throw new Error();
      if (current()) setReport(value);
    } catch { if (current()) setError("Historique des valorisations à vérifier. Relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <section className="revenue-guardian-panel" aria-label="Valorisations conservées"><h2>Valorisations conservées</h2><p>Décisions indépendantes, y compris plusieurs scénarios d’un même événement. Leurs montants ne sont pas additionnés.</p>
    <div className="revenue-guardian-period"><button disabled={busy} onClick={() => void load()}>Lire les valorisations conservées</button></div>{busy && <p role="status">Vérification des valorisations…</p>}{error && <p role="alert">{error}</p>}
    {report && <><p>{report.total} valorisations · Capture {report.captured_at} · {report.originals.length ? `${report.offset+1}–${report.offset+report.originals.length}` : "0"} sur {report.total}. Chaque page est une nouvelle lecture.</p>
      {report.originals.map(e => <ClosureReceipt key={e.original.id} value={e} />)}<div className="revenue-guardian-period"><button disabled={report.offset === 0} onClick={() => void load(Math.max(0, report.offset-20))}>Valorisations précédentes</button><button disabled={report.offset+report.originals.length >= report.total} onClick={() => void load(report.offset+20)}>Valorisations suivantes</button></div></>}
  </section>;
}
