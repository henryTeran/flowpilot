import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validWaitlistLifecycleAudit, type WaitlistLifecycleAudit, type WaitlistLifecycleState } from "../waitlist-lifecycle-utils";
type Props = { institute: string; timezone?: string; onManage?: (value: WaitlistLifecycleState) => void };

export function WaitlistLifecycleHistory(props: Props) {
  const { institute, timezone } = props;
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([institute, timezone, getAccessToken()])} {...props} />;
}
function Reader({ institute, timezone, onManage }: Props) {
  const token = getAccessToken(), sequence = useRef(0);
  const [report, setReport] = useState<WaitlistLifecycleAudit>(), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  function date(value: string) {
    try { return new Intl.DateTimeFormat("fr-CH", { timeZone: timezone || "UTC", dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); } catch { return value; }
  }
  async function load(offset = 0) {
    const request = ++sequence.current;
    const current = () => request === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    setReport(undefined); setError(undefined); setBusy(true);
    try {
      const value = await apiGet<WaitlistLifecycleAudit>(`/waitlist/institutes/${encodeURIComponent(institute)}/lifecycle?offset=${offset}&limit=20`);
      if (!await validWaitlistLifecycleAudit(value, institute, offset)) throw new Error("Invalid waitlist lifecycle audit");
      if (current()) setReport(value);
    } catch { if (current()) setError("États de liste d’attente à vérifier. Relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <section className="revenue-guardian-panel" aria-label="États de liste d’attente conservés">
    <h2>États de liste d’attente conservés</h2><p>Une liste active administrativement n’est pas une preuve de disponibilité actuelle ou d’autorisation de contact. L’annulation conserve les déclarations et les actions antérieures.</p>
    <p>Horaires : {timezone || "UTC — fuseau institut indisponible"}.</p>
    <div className="revenue-guardian-period"><button disabled={busy} onClick={() => void load()}>Lire les états de liste d’attente</button></div>
    {busy && <p role="status">Lecture des chaînes conservées…</p>}{error && <p role="alert">{error}</p>}
    {report && <><p>{report.total} listes conservées · {report.active} actives · {report.cancelled} annulées · lecture au {date(report.captured_at)}.</p>
      <p>{report.states.length ? `${report.offset+1}–${report.offset+report.states.length}` : "0"} sur {report.total}. Chaque page relit les sources.</p>
      {report.states.map(s => <article key={s.root.original.id}><h3>{s.root.original.reason}</h3>
        <p>Liste {s.state === "active" ? "active administrativement : éligibilité actuelle à relire" : "annulée : chaîne fermée"}.</p>
        <p>Déclaration courante : {s.current_demand.original.reason}.</p>
        <p>Cliente {s.current_demand.original.demand.customer_id} · prestation {s.current_demand.original.demand.service_id} · durée déclarée {s.current_demand.original.demand.duration_minutes} min.</p>
        <p>Contraintes {s.current_demand.original.demand.constraints_review === "confirmed" ? "relues selon déclaration" : "inconnues : matching à vérifier"}.</p>
        <ul>{s.current_demand.original.demand.availability.map((w, i) => <li key={i}>Disponibilité déclarée du {date(w.start)} au {date(w.end)}.</li>)}</ul>
        <p>{s.events.length} actions conservées. Dernière action : {date(s.events[s.events.length-1].original.created_at)} · {s.events[s.events.length-1].original.actor_id}.</p>
        {onManage && <div className="revenue-guardian-period"><button onClick={() => onManage(s)}>Relire pour gérer cette liste</button></div>}
        <details><summary>Voir les actions et leurs preuves</summary>
          {s.events.map(e => <div key={e.original.id}><h4>{({ activate: "Activation", revise: "Révision", cancel: "Annulation" })[e.original.action]}</h4>
            <p>{e.original.reason} · {date(e.original.created_at)} · auteur {e.original.actor_id}.</p>
            <p>Action {e.original.id} · clé {e.original.idempotency_key} · empreinte {e.fingerprint}.</p>
            <p>Déclaration sélectionnée {e.original.target_id} · empreinte {e.original.target_fingerprint}.</p>
            {e.original.activation_source ? <p>Source à cette action : inscription du {date(e.original.activation_source.registered_at)} · prestation {e.original.activation_source.service_id} · durée {e.original.activation_source.duration_minutes} min · restrictions {e.original.activation_source.allowed_employee_ids.join(", ") || "aucune déclarée"}.</p>
              : <p>Annulation : aucune nouvelle capture d’éligibilité.</p>}
            <details><summary>Voir l’original de cette action</summary><pre>{JSON.stringify(e.original, null, 2)}</pre></details>
          </div>)}
        </details>
        <details><summary>Voir les déclarations racine et courante</summary>
          <p>Racine {s.root.original.id} · empreinte {s.root.fingerprint}.</p><pre>{JSON.stringify(s.root.original, null, 2)}</pre>
          <p>Courante {s.current_demand.original.id} · empreinte {s.current_demand.fingerprint}.</p><pre>{JSON.stringify(s.current_demand.original, null, 2)}</pre>
        </details>
      </article>)}
      <div className="revenue-guardian-period"><button disabled={busy || report.offset === 0} onClick={() => void load(Math.max(0, report.offset-20))}>États précédents</button>
        <button disabled={busy || report.offset+report.states.length >= report.total} onClick={() => void load(report.offset+20)}>États suivants</button></div>
    </>}
  </section>;
}
