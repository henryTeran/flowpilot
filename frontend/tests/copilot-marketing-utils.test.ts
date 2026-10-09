import test from "node:test";
import assert from "node:assert/strict";
import {campaignDigest,type CampaignOriginal} from "../src/marketing-campaign-utils";
import {revenueOriginalFingerprint as hash} from "../src/revenue-scenario-utils";
import {validMarketingPreview,validMarketingDraft,validMarketingRequest,type MarketingRequest} from "../src/copilot-marketing-utils";
async function fixture(){
  const content={institute_id:"own",channel:"email" as const,origin:"human" as const,subject:"Sujet revu",body:"Texte littéral {customer_name}",template_original_id:"template",audience:{id:"audience",institute_id:"own",captured_at:"2026-10-09T12:00:00.123456Z",customer_ids:["customer-b","customer-a"]}};
  const state_fingerprint=await campaignDigest(content),selection={audience_id:"audience",template_original_id:"template"},principal={actor_id:"manager",institute_id:"own",role:"responsable_institut" as const};
  const request:MarketingRequest={message:"Preparer un brouillon marketing",ui_context:selection,expected_state_fingerprint:state_fingerprint,reason:"Brouillon relu",idempotency_key:"draft-key"};
  const original:CampaignOriginal={request:{action:"create",campaign_id:null,expected_revision_id:null,content:{channel:content.channel,origin:content.origin,subject:content.subject,body:content.body,audience_id:selection.audience_id,template_original_id:selection.template_original_id},reason:request.reason,idempotency_key:request.idempotency_key},revision:{id:"original",campaign_id:"campaign",institute_id:"own",previous_id:null,state:"DRAFT",content,actor_id:"manager",reason:request.reason,created_at:"2026-10-09T12:00:02Z",reviewed_digest:null,approved_digest:null,external_message_sent:false,delivery_authorized:false}};
  const preview={principal,capability:"MARKETING_CAMPAIGN_DRAFT",selection,captured_at:"2026-10-09T12:00:01Z",channel:content.channel,recipient_count:2,state_fingerprint,effect:"draft_preview_only_no_campaign_approval_contact_or_delivery"};
  const draft={principal,capability:"MARKETING_CAMPAIGN_DRAFT",selection,original_id:original.revision.id,campaign_id:original.revision.campaign_id,created_at:original.revision.created_at,channel:content.channel,recipient_count:2,state:"DRAFT",state_fingerprint,original_fingerprint:await hash(original),effect:"retained_draft_only_no_campaign_approval_contact_or_delivery"};return {content,selection,request,original,preview,draft};
}
test("marketing preview binds explicit original content, audience order/count and template without delivery authority",async()=>{
  const f=await fixture();assert.ok(validMarketingRequest(f.request));assert.ok(await validMarketingPreview(f.preview,"own",f.selection,f.content,"manager"));
  for(const change of [{recipient_count:1},{channel:"sms"},{state_fingerprint:"0".repeat(64)},{selection:{...f.selection,template_original_id:"other"}},{captured_at:"2026-10-09T12:00:00Z"},{effect:"delivery_authorized"},{delivery_authorized:true}])assert.equal(await validMarketingPreview({...f.preview,...change},"own",f.selection,f.content,"manager"),false);
  for(const change of [{body:"Generated replacement"},{audience:{...f.content.audience,customer_ids:[...f.content.audience.customer_ids].reverse()}},{template_original_id:"other"}])assert.equal(await validMarketingPreview(f.preview,"own",f.selection,{...f.content,...change},"manager"),false);
  assert.equal(await validMarketingPreview(f.preview,"foreign",f.selection,f.content),false);assert.equal(await validMarketingPreview(f.preview,"own",f.selection,f.content,"other"),false);assert.equal(validMarketingRequest({...f.request,reason:" Border "}),false);
});
test("compact draft requires matching independent original, exact retained terms and draft-only effect",async()=>{
  const f=await fixture();assert.ok(await validMarketingDraft(f.draft,"own",f.original,f.request,"manager"));
  for(const change of [{state:"APPROVE"},{original_id:"other"},{campaign_id:"other"},{recipient_count:3},{original_fingerprint:"0".repeat(64)},{created_at:"2026-10-09T12:00:03Z"},{effect:"sent"}])assert.equal(await validMarketingDraft({...f.draft,...change},"own",f.original,f.request,"manager"),false);
  for(const change of [{reason:"Other reason"},{idempotency_key:"other"},{expected_state_fingerprint:"0".repeat(64)},{ui_context:{...f.selection,audience_id:"other"}}])assert.equal(await validMarketingDraft(f.draft,"own",f.original,{...f.request,...change},"manager"),false);
  const changed={...f.original,revision:{...f.original.revision,content:{...f.content,body:"Different retained text"}}};assert.equal(await validMarketingDraft({...f.draft,original_fingerprint:await hash(changed)},"own",changed,f.request,"manager"),false);
  assert.equal(await validMarketingDraft(f.draft,"own",{...f.original,revision:{...f.original.revision,delivery_authorized:true}} as any,f.request,"manager"),false);
});
