import test from "node:test";
import assert from "node:assert/strict";
import { crmProfile } from "./crm-fixture";
import { crmLifecycle } from "./crm-lifecycle-fixture";
import { validAudienceOriginal, validAudienceObservation, validRetainedAudiencePage, matchesAudienceReceipt,
  sameAudienceOriginal, validAudienceCatalog, type AudienceOriginal, type AudienceObservation } from "../src/marketing-audience-utils";
const original = (): AudienceOriginal => ({ id: "capture", institute_id: "i", actor_id: "manager", captured_at: "2026-10-07T00:00:00Z",
  request: { segments: ["VIP"], channel: "email", reason: "Explicit selection", idempotency_key: "key" },
  summary: { page_count: 1, customer_count: 1, selected_count: 1, eligible_count: 0 }, complete_registered_cohort: true, delivery_authorized: false });
function observation(): AudienceObservation {
  const profile = crmProfile(), declaration = crmLifecycle().original;
  return { institute_id: "i", captured_at: profile.captured_at, selection: { segments: [profile.segment!.state!], channel: "email", after: null },
    next_after: null, items: [{ customer_id: "customer_a", profile, declaration, selected_segment: true,
      marketing_permission: "refused", eligible_by_recorded_permission: false, delivery_authorized: false }], complete_institute_audience: false, delivery_authorized: false };
}

import {marketingSourceContent,readMarketingSources} from "../src/copilot-marketing-sources";
import type {TemplateOriginal} from "../src/marketing-template-utils";
test("marketing content uses exact retained eligible recipients and literal original template",async()=>{
  const a=original(),o=observation();a.summary.eligible_count=1;a.request.segments=o.selection.segments;
  o.items[0].declaration!.declaration.communications.find(c=>c.channel==="email"&&c.purpose==="marketing")!.permission="granted";o.items[0].marketing_permission="granted";o.items[0].eligible_by_recorded_permission=true;
  const content={name:"Modèle conservé",channel:"email" as const,origin:"human" as const,subject:"Sujet",body:"Bonjour {customer_name}"};
  const t:TemplateOriginal={id:"template-original",institute_id:"i",template_id:"template",previous_id:null,actor_id:"manager",created_at:a.captured_at,request:{template_id:null,previous_id:null,content,reason:"Modèle relu",idempotency_key:"template-key"},content};const pages=[{capture_id:a.id,page_index:0,observation:o}];
  const result=marketingSourceContent("i",a,t,pages);assert.ok(result);assert.equal(result.body,content.body);assert.equal(result.template_original_id,t.id);assert.deepEqual(result.audience.customer_ids,["customer_a"]);
  assert.equal(marketingSourceContent("foreign",a,t,pages),undefined);assert.equal(marketingSourceContent("i",a,t,[]),undefined);assert.equal(marketingSourceContent("i",{...a,summary:{...a.summary,eligible_count:0}},t,pages),undefined);
  assert.equal(marketingSourceContent("i",a,{...t,content:{...content,body:"Substituted text"}},pages),undefined);
  assert.equal(marketingSourceContent("i",a,t,[{...pages[0],observation:{...o,selection:{...o.selection,after:"unexpected"}}}]),undefined);
  assert.equal(marketingSourceContent("i",a,t,[{...pages[0],observation:{...o,items:[{...o.items[0],eligible_by_recorded_permission:false}]}}]),undefined);
  const paths:string[]=[];const get=async(path:string)=>{paths.push(path);if(path.endsWith("/pages/0"))return pages[0];if(path.includes("/audience-captures/"))return a;if(path.includes("/templates/"))return t;throw Error("Unexpected read");};
  const read=await readMarketingSources("i",{audience_id:a.id,template_original_id:t.id},get,()=>true);assert.deepEqual(read?.content,result);assert.equal(paths.length,5);assert.ok(paths.includes("/marketing/institutes/i/templates/original/template-key"));
  await assert.rejects(readMarketingSources("i",{audience_id:a.id,template_original_id:t.id},async path=>path.includes("/templates/original/") ? {...t,actor_id:"other"} : get(path),()=>true));
  await assert.rejects(readMarketingSources("i",{audience_id:a.id,template_original_id:t.id},async path=>path.endsWith("/pages/0") ? {...pages[0],page_index:1} : get(path),()=>true));
  let live=true;const stalePaths:string[]=[];assert.equal(await readMarketingSources("i",{audience_id:a.id,template_original_id:t.id},async path=>{stalePaths.push(path);live=false;return path.includes("audience") ? a : t;},()=>live),undefined);assert.equal(stalePaths.length,2);
});
