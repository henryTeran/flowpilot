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

import {createMarketingIntent,marketingIntentKey} from "../src/copilot-marketing-intent";
const storage=()=>{const values=new Map<string,string>();return {getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v);},removeItem:(k:string)=>{values.delete(k);}};};
test("lost draft acknowledgement recovers exact original without another POST or replacement terms",async()=>{
  const f=await fixture(),saved=storage();let retained:unknown=null,writes=0;const reads:string[]=[];
  const options={institute:"own",actor:"manager",storage:saved,current:()=>true,get:async(path:string)=>{reads.push(path);return path.includes("/original/") ? retained : f.original;},post:async(path:string,body:MarketingRequest)=>{assert.equal(path,"/copilot/prepare/marketing");assert.deepEqual(body,f.request);writes++;retained=f.original;throw Error("Lost response");}};
  const first=createMarketingIntent(options);await assert.rejects(first.submit(f.request));assert.equal(first.state().status,"frozen");const reload=createMarketingIntent(options);const r=await reload.submit({...f.request,reason:"Replacement reason"});assert.equal(r.status,"confirmed");assert.equal(writes,1);assert.equal(reload.state().status,"empty");assert.ok(reads.includes("/marketing/institutes/own/campaigns/original/draft-key"));assert.ok(reads.includes("/marketing/institutes/own/campaigns/original"));
});
test("compact response and independent original damage stay frozen; definitive rejection alone permits correction",async()=>{
  const f=await fixture();
  for(const damaged of ["compact","independent"]){const saved=storage();let writes=0;const driver=createMarketingIntent({institute:"own",actor:"manager",storage:saved,current:()=>true,get:async(path)=>path.endsWith("/original/draft-key") ? writes ? f.original : null : {...f.original,revision:{...f.original.revision,id:"substituted"}},post:async()=>{writes++;return damaged==="compact" ? {...f.draft,campaign_id:"substituted"} : f.draft;}});await assert.rejects(driver.submit(f.request));assert.equal(driver.state().status,"frozen");assert.equal(driver.canCorrect(),false);}
  for(const status of [400,500]){let reads=0;const driver=createMarketingIntent({institute:"own",actor:"manager",storage:storage(),current:()=>true,get:async()=>{reads++;return null;},post:async()=>{throw Object.assign(Error("Rejected"),{status});}});await assert.rejects(driver.submit(f.request));assert.equal(driver.canCorrect(),status===400);if(status===400){assert.equal((await driver.correct()).status,"correctable");assert.equal(reads,2);}else{await assert.rejects(driver.correct());assert.equal(driver.state().status,"frozen");}}
});
test("corrupt storage, changed session and concurrent reload block new draft writes",async()=>{
  const f=await fixture(),saved=storage();saved.setItem(marketingIntentKey("own","manager"),"invalid");let writes=0;const broken=createMarketingIntent({institute:"own",actor:"manager",storage:saved,current:()=>true,get:async()=>null,post:async()=>{writes++;return f.draft;}});await assert.rejects(broken.submit(f.request));assert.equal(writes,0);
  let live=true,release:(v:unknown)=>void=()=>{};const options={institute:"own",actor:"manager",storage:storage(),current:()=>live,get:async()=>new Promise(resolve=>{release=resolve;}),post:async()=>{writes++;return f.draft;}};const first=createMarketingIntent(options),second=createMarketingIntent(options),pending=first.submit(f.request);assert.equal((await second.submit(f.request)).status,"busy");live=false;release(null);assert.equal((await pending).status,"stale");assert.equal(first.state().status,"frozen");assert.equal(writes,0);
});
test("recovery refuses an original backdated before its selected audience",async()=>{
  const f=await fixture(),saved=storage(),backdated={...f.original,revision:{...f.original.revision,created_at:"2026-10-09T12:00:00Z"}};let writes=0;const driver=createMarketingIntent({institute:"own",actor:"manager",storage:saved,current:()=>true,get:async()=>backdated,post:async()=>{writes++;return f.draft;}});await assert.rejects(driver.submit(f.request));assert.equal(writes,0);assert.equal(driver.state().status,"frozen");
});
