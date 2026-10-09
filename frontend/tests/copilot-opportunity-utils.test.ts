import test from "node:test";
import assert from "node:assert/strict";
import {validOpportunityFacts,validOpportunitySelection} from "../src/copilot-opportunity-utils";
const capture="2026-10-09T12:00:00.123456Z",horizon="2026-10-09T13:00:00Z";
test("opportunity sources require exclusive explicit selection and original capacity capture",()=>{
  const selection={opportunity_source:"capacity",service_id:"service",horizon_end:horizon};
  const source={institute_id:"own",service_id:"service",captured_at:capture,horizon_end:horizon,opportunity:null,unavailable_reason:"capacity_unknown"};
  assert.ok(validOpportunityFacts(source,"own",selection,capture));
  assert.equal(validOpportunityFacts(source,"own",selection,"2026-10-09T12:00:00.123455Z"),false);
  assert.equal(validOpportunityFacts(source,"foreign",selection,capture),false);
  assert.equal(validOpportunityFacts({...source,phone:"private"},"own",selection,capture),false);
  assert.equal(validOpportunityFacts(source,"own",{opportunity_source:"rebooking"},capture),false);
  for(const v of [{...selection,start:capture},{opportunity_source:"rebooking",service_id:"service"},{opportunity_source:"closures",start:capture,end:capture},{opportunity_source:"capacity",service_id:"service"}])assert.equal(validOpportunitySelection(v),false);
  assert.ok(validOpportunitySelection({opportunity_source:"rebooking"}));
  assert.ok(validOpportunitySelection({opportunity_source:"closures",start:capture,end:horizon}));
});
