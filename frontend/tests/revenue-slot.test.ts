import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validRevenueSlot } from "../src/revenue-slot-utils";
const horizon = "2026-01-05T00:00:00Z";
const fixture = JSON.parse(readFileSync(new URL("./fixtures/revenue-slot-14u.json",import.meta.url),"utf8"));
test("capacity opportunity preserves sovereign duration, scoped horizon and conditional nonreservation semantics", () => {
  assert.equal(validRevenueSlot(fixture,"own","care",horizon),true);
  for (const mutate of [
    (r: any) => { r.institute_id = "foreign"; }, (r: any) => { r.service_id = "other"; }, (r: any) => { r.horizon_end = "2026-01-06T00:00:00Z"; },
    (r: any) => { r.opportunity.capacity_reserved = 0; }, (r: any) => { r.opportunity.action_executed = true; }, (r: any) => { r.opportunity.estimated_value = "0"; },
    (r: any) => { r.unavailable_reason = "capacity_unknown"; }, (r: any) => { r.opportunity.evidence.projected_start = "2026-01-02T11:00:00Z"; },
    (r: any) => { r.opportunity.evidence.projected_end = "2026-01-02T13:21:00Z"; }, (r: any) => { r.opportunity.evidence.duration_minutes = 20.5; },
    (r: any) => { r.opportunity.evidence.required_skills = ["skill","skill"]; }, (r: any) => { r.opportunity.evidence.resource_needs[0].quantity = 11; },
    (r: any) => { r.opportunity.evidence.resource_needs.push(r.opportunity.evidence.resource_needs[0]); }, (r: any) => { r.opportunity.evidence.unprojectable_prior_queue_count = 2; },
    (r: any) => { r.opportunity.evidence.institute_id = "foreign"; }, (r: any) => { r.opportunity.evidence.captured_at = "2026-01-02T12:00:01Z"; },
  ]) { const r = structuredClone(fixture); mutate(r); assert.equal(validRevenueSlot(r,"own","care",horizon),false); }
  for (const reason of ["capacity_unknown","outside_horizon","resource_configuration_missing"]) assert.equal(validRevenueSlot({ ...fixture, opportunity: null, unavailable_reason: reason },"own","care",horizon),true);
  assert.equal(validRevenueSlot({ ...fixture, opportunity: null },"own","care",horizon),false);
  assert.equal(validRevenueSlot(fixture,"own","care","2026-01-05T01:00:00+01:00"),true);
});
