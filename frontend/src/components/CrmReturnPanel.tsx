import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validReturnRead, type ReturnRead } from "../crm-return-utils";

type Props = { institute: string; customer: string; start: string; end: string };
export function CrmReturnPanel(props: Props) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <ReturnPanel key={JSON.stringify([props.institute, props.customer, props.start, props.end, getAccessToken()])} {...props} />;
}
export function returnDays(numerator: string, denominator: string) {
  const scale = BigInt(denominator)*86400000000n;
  const hundredths = (BigInt(numerator)*200n+scale)/(2n*scale);
  return `${hundredths/100n},${String(hundredths%100n).padStart(2,"0")}`;
}
function ReturnPanel({ institute, customer, start, end }: Props) {
  const token = getAccessToken(), [offset, setOffset] = useState(0), [revision, refresh] = useState(0);
  const [result, setResult] = useState<ReturnRead>(), [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(true);
    const params = new URLSearchParams({ start, end, offset: String(offset), limit: "20" });
    void apiGet<unknown>(`/crm/institutes/${encodeURIComponent(institute)}/customers/${encodeURIComponent(customer)}/return-cycle?${params}`)
      .then(v => { if (!current()) return; if (!validReturnRead(v,institute,customer,start,end,offset)) throw new Error("Cycle de retour à vérifier."); setResult(v); })
      .catch(e => { if (current()) setError(e instanceof Error ? e.message : "Cycle de retour indisponible."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [offset, revision]);
  const mean = result?.summary.average_return_gap_us;
  function changePage(next: number) { setResult(undefined); setError(undefined); setLoading(true); setOffset(next); }
  return <section aria-label="Cycle de retour observé"><header><h4>Cycle de retour observé</h4>
    <button disabled={loading} onClick={() => { setResult(undefined); setLoading(true); refresh(v => v+1); }}>Actualiser le cycle</button></header>
    <p>Période : {start} — {end}</p>
    <p>Soins terminés reliés aux tickets. La couverture des soins et l’historique sont incomplets ; aucun crédit de réservation n’est déduit.</p>
    {loading && <p role="status">Lecture des soins…</p>}{error && <p role="alert">{error}</p>}
    {result && <><p>Épisodes de soins enregistrés : {result.summary.episode_count} · exécutions : {result.summary.execution_count}</p>
      <p>Intervalle moyen entre soins : {mean ? `${returnDays(mean.numerator,mean.denominator)} jours (arrondi)` : "Non déterminé"}</p>
      <p>Intervalles connus : {result.summary.known_gap_count} · chevauchements : {result.summary.overlapping_gap_count}</p>
      {Object.values(result.diagnostics).some(Boolean) && <p>Sources à vérifier : liens absents {result.diagnostics.unlinked_ticket}, identité ou soin incohérent {result.diagnostics.invalid_owner_or_service}, dates incohérentes {result.diagnostics.invalid_actual_times}.</p>}
      <p>Lecture des soins : {result.summary.window.captured_at}. Lecture distincte du profil de paiement.</p>
      <ol start={offset+1}>{result.episodes.map(e => {
        const gap = result.gaps.find(g => g.next_ticket_id === e.ticket_id);
        return <li key={e.ticket_id}>Ticket {e.ticket_id} · {e.started_at} — {e.completed_at} · {e.execution_count} exécution(s)
          {gap && <p>Depuis le ticket {gap.previous_ticket_id} : {gap.quality === "known" ? `${returnDays(gap.gap_us!,"1")} jours (arrondi)` : "Soins chevauchants — intervalle indéterminé"}</p>}</li>;
      })}</ol>
      <p>Épisodes affichés : {result.episodes.length ? `${offset+1}–${offset+result.episodes.length}` : "0"} sur {result.page.total}. Les totaux portent sur toute la période.</p>
      <button disabled={offset === 0} onClick={() => changePage(Math.max(0,offset-20))}>Épisodes précédents</button>
      <button disabled={offset+20 >= result.page.total} onClick={() => changePage(offset+20)}>Épisodes suivants</button></>}
  </section>;
}
