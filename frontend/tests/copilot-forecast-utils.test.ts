import test from "node:test";
import assert from "node:assert/strict";
import {validForecastSelection,validForecastFacts} from "../src/copilot-forecast-utils";
const capture="2026-10-09T12:00:00.123456Z";
const scenario={starts_at:"2026-10-10T00:00:00Z",ends_at:"2026-10-11T00:00:00Z",demands:[{service_id:"service",recipe_id:null,quantity:3}]};
test("forecast selection retains explicit missing norms and original selected scenario",()=>{
  assert.ok(validForecastSelection({scenario}));
  for(const value of [{scenario,customer_id:"private"},{scenario:{...scenario,phone:"private"}},{scenario:{...scenario,demands:[{...scenario.demands[0],quantity:0}]}},{scenario:{...scenario,demands:[scenario.demands[0],scenario.demands[0]]}}])assert.equal(validForecastSelection(value),false);
  const source={institute_id:"own",generated_at:capture,starts_at:scenario.starts_at,ends_at:scenario.ends_at,source:"explicit_service_volume_scenario",coverage:"partial_selected_norms",demands:[{...scenario.demands[0],service_name:"Soin",recipe_revision:null,state:"missing_norm"}],limit:50,offset:0,items:[]};
  assert.equal(validForecastFacts(source,"own",{scenario},capture),false);
  const valid={...source,demands:[{...source.demands[0],state:"missing_selected_norm"}]};
  assert.ok(validForecastFacts(valid,"own",{scenario},capture));
  for(const change of [{coverage:"complete_selected_norms"},{institute_id:"foreign"},{generated_at:"2026-10-09T12:00:00.123455Z"},{limit:20},{starts_at:"2026-10-10T00:00:00.000001Z"},{demands:[{...valid.demands[0],quantity:4}]}])assert.equal(validForecastFacts({...valid,...change},"own",{scenario},capture),false);
});
