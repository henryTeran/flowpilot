import test from "node:test";
import assert from "node:assert/strict";
import {revenueOriginalFingerprint as hash} from "../src/revenue-scenario-utils";
import {creationUTC,canonicalCreationSelection,validCreationSelection,validCreationRequest,validCreationPreview,validCreationEnvelope,type CreationSelection,type CreationPreview,type CreationRequest} from "../src/copilot-creation-utils";
const selected:CreationSelection={employee_id:"employee",service_id:"service",customer_id:"customer",customer_name:"Cliente sélectionnée",phone:"+33999900000",notes:"Note revue",start_time:"2026-10-25T02:30:00.123456+01:00"};
const capture="2026-10-09T12:00:00.123456Z";
async function preview(change:Partial<CreationPreview>={}):Promise<CreationPreview>{
  const v:CreationPreview={principal:{actor_id:"manager",institute_id:"own",role:"responsable_institut"},capability:{name:"APPOINTMENT_CREATE",prepare_level:2,roles:["responsable_institut"],application_service:"appointments.service.preview_creation",approval:"explicit_human_approval_of_exact_retained_operation_required",execution_registered:true},selection:canonicalCreationSelection(selected),captured_at:capture,end_time:"2026-10-25T01:40:00.123456Z",resource_ids:["a-room","z-equipment"],state_fingerprint:"",basis:"exact_creation_terms_and_current_eligible_interval_resources_not_full_database_digest",effect:"creation_preview_only_no_reservation_approval_or_execution",...change};
  v.state_fingerprint=await hash({institute_id:v.principal.institute_id,selection:v.selection,end_time:v.end_time.replace(/Z$/,"+00:00"),resource_ids:v.resource_ids});return v;
}
test("creation preview binds every reviewed term, microseconds, signed actor and sorted original resources",async()=>{
  assert.ok(validCreationSelection(selected));assert.equal(creationUTC(selected.start_time),"2026-10-25T01:30:00.123456Z");assert.equal(creationUTC("2026-10-09T12:00:00.000Z"),"2026-10-09T12:00:00Z");assert.equal(creationUTC("1969-12-31T23:59:59.123456Z"),"1969-12-31T23:59:59.123456Z");
  const v=await preview();assert.ok(await validCreationPreview(v,"own",selected,"manager"));assert.ok(await validCreationPreview({...v,capability:{...v.capability,execution_registered:false}},"own",selected,"manager"));
  for(const change of [{customer_name:"Another customer"},{customer_id:null},{phone:null},{notes:null},{start_time:"2026-10-25T02:30:00.123455+01:00"},{employee_id:"another"},{service_id:"another"}])assert.equal(await validCreationPreview(v,"own",{...selected,...change},"manager"),false);
  for(const value of [{...selected,customer_name:" Client "},{...selected,phone:"x\n"},{...selected,notes:"x".repeat(501)},{...selected,start_time:"2026-10-25T02:30:00"},{...selected,actor_id:"forged"}])assert.equal(validCreationSelection(value),false);
  assert.equal(await validCreationPreview(v,"foreign",selected,"manager"),false);assert.equal(await validCreationPreview(v,"own",selected,"other"),false);
  for(const altered of [await preview({resource_ids:["z","a"]}),await preview({resource_ids:["a","a"]}),await preview({end_time:v.selection.start_time}),{...v,captured_at:"2026-10-09T12:00:00.000000Z"},{...v,reserved:true},{...v,effect:"execution_done"},{...v,state_fingerprint:"0".repeat(64)},{...v,capability:{...v.capability,execution_registered:1}}])assert.equal(await validCreationPreview(altered,"own",selected,"manager"),false);
  assert.ok(await validCreationPreview(await preview({resource_ids:["\uE000","\u{10000}"]}),"own",selected,"manager"));
  assert.equal(await validCreationPreview(await preview({resource_ids:["\u{10000}","\uE000"]}),"own",selected,"manager"),false);
});
test("retained creation operation binds exact request, actor, validity and pending-only original",async()=>{
  const p=await preview();const request:CreationRequest={capability:"APPOINTMENT_CREATE",selection:selected,expected_state_fingerprint:p.state_fingerprint,valid_until:"2026-10-09T13:00:00.000Z",reason:"Préparation revue",idempotency_key:"recovery-key"};
  assert.ok(validCreationRequest(request));const original={...request,selection:p.selection,valid_until:creationUTC(request.valid_until)!,id:"operation",institute_id:"own",actor_id:"manager",created_at:"2026-10-09T12:00:00.123457Z",preview:p,effect:"prepared_sensitive_operation_only_pending_human_approval_no_execution"};
  const envelope={original,fingerprint:await hash(original)};assert.ok(await validCreationEnvelope(envelope,"own",request,"manager"));
  for(const change of [{reason:"Different reviewed reason"},{idempotency_key:"another"},{valid_until:"2026-10-09T13:00:00.000001Z"},{selection:{...selected,phone:null}}])assert.equal(await validCreationEnvelope(envelope,"own",{...request,...change},"manager"),false);
  for(const change of [{actor_id:"other"},{institute_id:"foreign"},{created_at:capture.replace("123456","123455")},{created_at:original.valid_until},{valid_until:original.created_at},{selection:{...original.selection,notes:null}},{effect:"approved"},{approved:true}]){const damaged={...original,...change};assert.equal(await validCreationEnvelope({original:damaged,fingerprint:await hash(damaged)},"own",request,"manager"),false);}
  const noncanonical={...original,selection:selected};assert.equal(await validCreationEnvelope({original:noncanonical,fingerprint:await hash(noncanonical)},"own",request,"manager"),false);
  assert.equal(await validCreationEnvelope({...envelope,fingerprint:"0".repeat(64)},"own",request,"manager"),false);
});
