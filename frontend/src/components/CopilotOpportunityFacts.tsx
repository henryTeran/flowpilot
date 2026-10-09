import type {OpportunityFacts} from "../copilot-opportunity-utils";
import {revenueMoney} from "../revenue-utils";

export function CopilotOpportunityFacts({value,date,employee,service}:{value:OpportunityFacts;date:(v:string)=>string;employee:(id:string)=>string;service:(id:string)=>string}){
  if("service_id" in value){
    const labels={resource_configuration_missing:"Configuration des ressources manquante",capacity_unknown:"Capacité non établie",outside_horizon:"Aucun créneau dans l’horizon choisi"};
    return <><p>Projection conditionnelle de la file actuelle pour {service(value.service_id)}, jusqu’au {date(value.horizon_end)}.</p>
      {value.opportunity ? <><h4>Créneau à examiner</h4><p>{employee(value.opportunity.evidence.employee_id)} · {date(value.opportunity.evidence.projected_start)} — {date(value.opportunity.evidence.projected_end)}.</p>
        <p>{value.opportunity.evidence.prior_queue_count} passage(s) précédent(s), dont {value.opportunity.evidence.unprojectable_prior_queue_count} non projetable(s).</p>
        <p>Vérifiez les horaires d’ouverture et actualisez la capacité avant une affectation. Ce créneau n’est pas réservé.</p></> : <p>{labels[value.unavailable_reason!] || "Projection indisponible"}.</p>}
      <p>Aucun revenu estimé ni affectation effectuée.</p></>;
  }
  if(value.source==="observed_care_declared_rebooking_rule"){
    return <><p>Reprises à examiner selon les soins observés et la règle CRM enregistrée. Historique complet indisponible.</p>
      <dl><dt>Clientes examinées</dt><dd>{value.examined_customers}</dd><dt>Reprises à examiner</dt><dd>{value.total_candidates}</dd><dt>Déjà réservées</dt><dd>{value.already_booked_customers}</dd><dt>Échéance future</dt><dd>{value.scheduled_customers}</dd><dt>Règle désactivée</dt><dd>{value.disabled_customers}</dd><dt>Sans candidate établie</dt><dd>{value.no_candidate_customers}</dd></dl>
      <p>Premières {value.candidates.length} candidates sur {value.total_candidates}. Vérifiez le besoin de retour, la permission de contact et un créneau réalisable.</p>
      <ul>{value.candidates.map(c=><li key={c.customer_id}>Référence cliente : {c.customer_id} · soin observé le {date(c.source.occurred_at)} · échéance le {date(c.due_at)}.</li>)}</ul>
      {!!Object.values(value.diagnostics).some(n=>n>0) && <p>Des sources CRM restent à vérifier avant tout suivi.</p>}
      <p>Aucun message envoyé ni revenu estimé.</p></>;
  }
  return <><p>Suivis à examiner sur les événements de clôture enregistrés. Historique complet et perte financière causale non établis.</p>
    <h4>Rendez-vous</h4><p>{value.booking_total} événement(s), jusqu’à 20 affichés. Sources lues le {date(value.bookings.window.captured_at)}.</p>
    <ul>{value.booking_candidates.map(c=><li key={c.event_id}>{c.type==="review_no_show_booking" ? "Absence au rendez-vous" : "Annulation de rendez-vous"} · {date(c.occurred_at)} · référence {c.appointment_id}.</li>)}</ul>
    <h4>Passages sans rendez-vous</h4><p>{value.walk_in_total} événement(s), jusqu’à 20 affichés. Sources lues le {date(value.walk_ins.window.captured_at)}.</p>
    <ul>{value.walk_in_candidates.map(c=><li key={c.event_id}>Annulation · {date(c.occurred_at)} · référence {c.ticket_id}. {c.retained_value ? `Valeur commerciale conservée : ${revenueMoney(c.retained_value.amount_minor)} ${c.retained_value.currency}.` : "Valeur non établie."}</li>)}</ul>
    <p>Vérifiez les sources et les permissions avant tout suivi. Aucun contact effectué ni revenu récupéré établi.</p></>;
}
