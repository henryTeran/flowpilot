import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { instituteTimeZone } from "../institute-time";
import { certificationInstant } from "../certification-utils";
import { validRevenueRebooking, rebookingDiagnostics, type RevenueRebooking } from "../revenue-rebooking-utils";
export function RevenueRebookingReview(props: { institute: string; timezone?: string }) {
  if(!props.institute || getOperatorRole()!=="responsable_institut") return null;
  return <Reader key={JSON.stringify([props.institute,props.timezone,getAccessToken()])} {...props} />;
}
function Reader({ institute,timezone }: { institute: string; timezone?: string }) {
  const token=getAccessToken(),sequence=useRef(0);
  const [report,setReport]=useState<RevenueRebooking>(),[busy,setBusy]=useState(false),[error,setError]=useState<string>();
  useEffect(()=>()=>{ sequence.current++; },[]);
  async function read(offset=0) {
    const request=++sequence.current,current=()=>request===sequence.current && token===getAccessToken() && getOperatorRole()==="responsable_institut";
    if(!current()) return; setReport(undefined); setBusy(true); setError(undefined);
    try { const result=await apiGet<unknown>(`/revenue/institutes/${encodeURIComponent(institute)}/rebooking?${new URLSearchParams({ offset:String(offset),limit:"20" })}`);
      if(!validRevenueRebooking(result,institute,offset)) throw new Error(); if(current()) setReport(result);
    } catch { if(current()) setError("Retours indisponibles. Relancez la lecture pour vérifier les sources actuelles."); }
    finally { if(current()) setBusy(false); }
  }
  const clock=(at:string)=>new Intl.DateTimeFormat("fr-CH",{ timeZone:instituteTimeZone(timezone),year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit" }).format(new Date(at));
  const diagnosticLabels:Record<string,string>={ policy_absent:"Règle CRM absente",future_policy:"Règle CRM datée dans le futur",future_registration:"Inscription datée dans le futur",invalid_event_timing:"Délai de règle inexploitable",
    care_unavailable:"Soin observé indisponible",care_unlinked_ticket:"Soin sans ticket lié",care_invalid_owner_or_service:"Propriétaire ou prestation du soin incohérent",care_invalid_actual_times:"Horaires réels du soin incohérents" };
  return <section className="revenue-guardian-panel" aria-label="Retours clients à examiner" style={{ overflowWrap:"anywhere" }}>
    <h2>Retours clients à examiner</h2><p>Dernier soin observé et règle de retour déclarée. Les retours actifs enregistrés sont écartés. Cette lecture ne prouve pas un besoin réel de retour, l’historique complet ou une autorisation de contact.</p>
    <div className="revenue-guardian-period"><button disabled={busy} onClick={()=>void read()}>Lire les retours à examiner</button></div>
    {busy && <p role="status">Lecture des retours…</p>}{error && <p role="alert">{error}</p>}
    {report && <><p>{report.examined_customers} clientes enregistrées examinées · {report.page.total} retours à examiner · {report.already_booked_customers} avec retour actif enregistré · {report.scheduled_customers} pas encore dus · {report.disabled_customers} avec règle désactivée · {report.no_candidate_customers} sans candidate exploitable. Totaux indépendants de la page.</p>
      <p>Capture : {report.captured_at} · {report.opportunities.length ? `${report.page.offset+1}–${report.page.offset+report.opportunities.length}` : "0"} sur {report.page.total}. Chaque page est une nouvelle lecture.</p>
      {rebookingDiagnostics.some(k=>(report.diagnostics[k]||0)>0) && <details><summary>Voir les diagnostics de source</summary>{rebookingDiagnostics.filter(k=>(report.diagnostics[k]||0)>0).map(k=><p key={k}>{diagnosticLabels[k]} : {report.diagnostics[k]}.</p>)}<p>Les diagnostics peuvent se recouper ; ils ne s’additionnent pas en un nombre de clientes.</p></details>}
      {report.opportunities.map(o=>{ const e=o.evidence,c=o.candidate,p=e.policy_original,life=e.lifecycle_original,future=life && certificationInstant(life.created_at)!>certificationInstant(e.captured_at)!;
        return <article key={e.customer_id}><h3>Retour à examiner · Cliente {e.customer_id}</h3><p>Soin observé le {clock(c.source.occurred_at)} · Échéance déclarée : {clock(c.due_at)}.</p>
          <p>Valeur estimée indisponible. Vérifiez le besoin de retour, la permission de contact et un créneau faisable avant tout suivi. Aucun message n’a été envoyé.</p>
          <details><summary>Voir le soin et la règle de retour</summary><p>Source soin : ticket {c.source.source_id} · Fin observée {c.source.occurred_at} · Inscription {e.customer.created_at}.</p>
            <p>Règle originale {p.id} · Auteur {p.actor_id} · {p.created_at} · Motif : {p.reason}.</p><p>Délai déclaré : {c.rule.offset_us} microsecondes · Échéance exacte {c.due_at}. Cette règle ne prédit pas une visite.</p></details>
          <details><summary>Voir les déclarations de contact</summary>{life ? <><p>Déclaration originale {life.id} · Auteur {life.actor_id} · {life.created_at} · Motif : {life.reason}.</p>
            {future && <p>Déclaration postérieure à la capture : ne pas l’utiliser comme permission actuelle.</p>}
            {life.declaration.communications.map(d=><p key={`${d.channel}:${d.purpose}`}>{d.channel==="email" ? "E-mail" : "SMS"} · {d.purpose==="marketing" ? "Marketing" : "Suivi de service"} : {d.permission==="granted" ? "permission déclarée accordée" : d.permission==="refused" ? "permission déclarée refusée" : "permission inconnue"}{d.evidence ? ` · Preuve déclarée : ${d.evidence}` : ""}.</p>)}</> : <p>Aucune déclaration de contact conservée pour cette cliente. Permission inconnue.</p>}
            <p>Ces déclarations ne constituent pas une autorisation d’envoi. Aucune coordonnée ni faisabilité de créneau n’est déduite.</p></details></article>; })}
      <div className="revenue-guardian-period"><button disabled={report.page.offset===0} onClick={()=>void read(Math.max(0,report.page.offset-20))}>Retours précédents</button><button disabled={report.page.offset+report.opportunities.length>=report.page.total} onClick={()=>void read(report.page.offset+20)}>Retours suivants</button></div>
    </>}
  </section>;
}
