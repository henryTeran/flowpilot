import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {CopilotOpportunityFacts} from "../src/components/CopilotOpportunityFacts";
const render=(value:any)=>renderToStaticMarkup(<CopilotOpportunityFacts value={value} date={v=>v} employee={()=>"Anne"} service={()=>"Soin"}/>);
test("passive opportunity views preserve source limits and contain no action controls",()=>{
  const capacity=render({service_id:"service",horizon_end:"horizon",opportunity:null,unavailable_reason:"capacity_unknown"});
  assert.match(capacity,/Capacité non établie/);assert.match(capacity,/Aucun revenu estimé/);
  const returns=render({source:"observed_care_declared_rebooking_rule",examined_customers:4,total_candidates:0,already_booked_customers:2,scheduled_customers:1,disabled_customers:0,no_candidate_customers:1,candidates:[],diagnostics:{care_unavailable:1}});
  assert.match(returns,/Historique complet indisponible/);assert.match(returns,/sources CRM restent à vérifier/);assert.match(returns,/Aucun message envoyé/);
  const closures=render({source:"recorded_closure_follow_up",booking_total:0,walk_in_total:1,bookings:{window:{captured_at:"booking-clock"}},walk_ins:{window:{captured_at:"walk-in-clock"}},booking_candidates:[],walk_in_candidates:[{event_id:1,ticket_id:"ticket",occurred_at:"event-clock",retained_value:{amount_minor:"1250",currency:"CHF"}}]});
  assert.match(closures,/12.50 CHF/);assert.match(closures,/booking-clock/);assert.match(closures,/walk-in-clock/);assert.match(closures,/Aucun contact effectué/);
  for(const html of [capacity,returns,closures])assert.doesNotMatch(html,/<button|<input|<form/);
});
