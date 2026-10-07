import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validLifecycleRead, type LifecycleRead } from "../crm-lifecycle-utils";
import { CrmLifecycleEditor } from "./CrmLifecycleEditor";
const reasons: Record<string,string> = { declaration_absent: "Déclaration cliente absente",calendar_absent: "Calendrier anniversaire absent",future_declaration: "Date de déclaration à vérifier",future_calendar: "Date du calendrier à vérifier",future_registration: "Date d’inscription à vérifier",birthday_unknown: "Anniversaire inconnu",absent_in_calendar_year: "Pas d’anniversaire dans cette année selon la règle déclarée",not_today: "Anniversaire hors de la journée locale",birthday_today: "Anniversaire dans la journée locale" };
const leapLabels = { leap_year_only: "années bissextiles uniquement",february_28: "28 février hors année bissextile",march_1: "1er mars hors année bissextile" };
const permissionLabels = { unknown: "permission inconnue",granted: "accord déclaré",refused: "refus déclaré" };
export function CrmLifecyclePanel(props: { institute: string; customer: string }) {
  if (!props.institute || !props.customer || getOperatorRole() !== "responsable_institut") return null;
  return <Panel key={JSON.stringify([props.institute,props.customer,getAccessToken()])} {...props} />;
}
function Panel({ institute,customer }: { institute: string; customer: string }) {
  const [revision,refresh] = useState(0);
  return <><details><summary>Déclarer anniversaire et permissions</summary><CrmLifecycleEditor institute={institute} customer={customer} onChanged={() => refresh(v => v+1)} /></details>
    <Observation key={revision} institute={institute} customer={customer} /></>;
}
function Observation({ institute,customer }: { institute: string; customer: string }) {
  const token = getAccessToken(), [revision,refresh] = useState(0), [result,setResult] = useState<LifecycleRead>();
  const [loading,setLoading] = useState(true), [error,setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(true);
    void apiGet<unknown>(`/crm/institutes/${encodeURIComponent(institute)}/customers/${encodeURIComponent(customer)}/lifecycle`)
      .then(v => { if (!current()) return; if (!validLifecycleRead(v,institute,customer)) throw new Error("Observation anniversaire à vérifier."); setResult(v); })
      .catch(e => { if (current()) setError(e instanceof Error ? e.message : "Observation indisponible."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [revision]);
  const b = result?.birthday;
  return <section aria-label="Observation anniversaire"><h4>Anniversaire observé</h4>
    <button disabled={loading} onClick={() => { setResult(undefined); setLoading(true); refresh(v => v+1); }}>Actualiser l’observation anniversaire</button>
    <p>Cette lecture ne programme ni n’envoie de message. L’autorisation de livraison reste non certifiée.</p>
    {loading && <p role="status">Lecture de l’anniversaire…</p>}{error && <p role="alert">{error}</p>}
    {result && <><p>Capture : {result.captured_at}. Lecture distincte du profil, des soins et du scénario CLV.</p>
      <p>{reasons[result.unavailable_reason || b!.reason]}</p>
      {b && <><p>Journée locale : {b.local_date} · fuseau : {b.policy.timezone} · 29 février : {leapLabels[b.policy.leap_day]}</p>
        <p>Anniversaire dans l’année : {b.anniversary_on || "Non déterminé"}</p>
        {b.occurrence_start && <p>Bornes UTC de l’anniversaire : {b.occurrence_start} — {b.occurrence_end} (fin exclue)</p>}</>}
      <details><summary>Sources anniversaire et permissions</summary>
        <p>Inscription : {result.customer.created_at}</p>
        {result.original && <><p>Déclaration {result.original.id} · acteur {result.original.actor_id} · motif : {result.original.reason}</p>
          <p>Anniversaire déclaré : {result.original.declaration.birthday ? `${result.original.declaration.birthday.day}/${result.original.declaration.birthday.month}` : "Inconnu"} · preuve : {result.original.declaration.birthday_evidence || "Absente"}</p>
          {result.original.declaration.communications.map(c => <p key={`${c.channel}:${c.purpose}`}>{c.channel === "email" ? "Email" : "SMS"} · {c.purpose === "marketing" ? "marketing" : "suivi de soin"} · {permissionLabels[c.permission]} · preuve : {c.evidence || "Absente"}</p>)}</>}
        {result.calendar_original && <p>Calendrier {result.calendar_original.id} · acteur {result.calendar_original.actor_id} · motif : {result.calendar_original.reason}</p>}
      </details></>}
  </section>;
}
