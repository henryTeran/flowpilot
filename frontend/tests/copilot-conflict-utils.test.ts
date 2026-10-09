import test from "node:test";
import assert from "node:assert/strict";
import {validConflictRead} from "../src/copilot-conflict-utils";
const capture="2026-10-09T12:00:00Z",day="2025-10-26";
const left={kind:"appointment",id:"a",start_at:"2025-10-26T10:00:00.000001Z",end_at:"2025-10-26T11:00:00Z"};
const right={...left,kind:"session",id:"b",start_at:"2025-10-26T10:30:00Z"};
const overlap={left,right,start_at:right.start_at,end_at:left.end_at,duration_us:"1800000000"};
const source={institute_id:"own",employee_id:"employee",day,captured_at:capture,start_at:"2025-10-25T22:00:00Z",end_at:"2025-10-26T23:00:00Z",source_digest:"a".repeat(64),source_count:2,invalid_source_count:0,overdue_open_source_count:2,overlap_count:1,overlaps:[overlap],page_limit:50,basis:"current_recorded_employee_commitments_half_open",resource_conflicts_covered:false,physical_activity_proven:false};
test("employee conflicts retain DST day, exact intersections and source boundaries",()=>{
  const valid=(v:unknown)=>validConflictRead(v,"own",day,"Europe/Zurich",{employee_id:"employee"},capture);
  assert.ok(valid(source));
  for(const change of [{institute_id:"foreign"},{employee_id:"other"},{resource_conflicts_covered:true},{phone:"private"},{source_digest:"invalid"},{overlap_count:2},{overlaps:[{...overlap,duration_us:"1800000001"}]},{overlaps:[{...overlap,start_at:"2025-10-26T10:30:00.000001Z",duration_us:"1799999999"}]}])assert.equal(valid({...source,...change}),false);
  assert.equal(validConflictRead(source,"own",day,"Europe/Zurich",{employee_id:"employee",resource_id:"resource"},capture),false);
});
test("resource reservation conflicts preserve absent booking authority",()=>{
  const {employee_id,overdue_open_source_count,resource_conflicts_covered,...common}=source;
  const resource={...common,resource_id:"room",resource_status:"maintenance",overdue_unreleased_source_count:2,complete_institute_conflict_coverage:false,booking_authorized:false,basis:"current_unreleased_resource_reservations_half_open",overlaps:[{...overlap,left:{...left,kind:"reservation"},right:{...right,kind:"reservation"}}]};
  const valid=(v:unknown)=>validConflictRead(v,"own",day,"Europe/Zurich",{resource_id:"room"},capture);
  assert.ok(valid(resource));assert.equal(valid({...resource,booking_authorized:true}),false);
  assert.equal(valid({...resource,overlaps:[overlap]}),false);
  assert.equal(valid({...resource,overlap_count:2,overlaps:[resource.overlaps[0],resource.overlaps[0]]}),false);
});
