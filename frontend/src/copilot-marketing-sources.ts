import {validAudienceOriginal,validRetainedAudiencePage,sameAudienceOriginal,type AudienceOriginal,type RetainedAudiencePage} from "./marketing-audience-utils";
import {validTemplateOriginal,sameTemplateOriginal,type TemplateOriginal} from "./marketing-template-utils";
import {validCampaignContent,type CampaignContent} from "./marketing-campaign-utils";
import {validMarketingSelection,type MarketingSelection} from "./copilot-marketing-utils";
export async function readMarketingSources(institute:string,selection:MarketingSelection,get:(path:string)=>Promise<unknown>,current:()=>boolean):Promise<{audience:AudienceOriginal;template:TemplateOriginal;content:CampaignContent}|undefined>{
  if(!validMarketingSelection(selection) || !current())return;
  const base=`/marketing/institutes/${encodeURIComponent(institute)}`;
  const [a,t]=await Promise.all([get(`${base}/audience-captures/${encodeURIComponent(selection.audience_id)}`),get(`${base}/templates/${encodeURIComponent(selection.template_original_id)}`)]);
  if(!current())return;
  if(!validAudienceOriginal(a,institute) || a.id!==selection.audience_id || !validTemplateOriginal(t,institute) || t.id!==selection.template_original_id || a.request.channel!==t.content.channel || !a.summary.eligible_count)throw Error("Invalid selected marketing originals");
  const [ak,tk]=await Promise.all([get(`${base}/audience-captures/original/${encodeURIComponent(a.request.idempotency_key)}`),get(`${base}/templates/original/${encodeURIComponent(t.request.idempotency_key)}`)]);
  if(!current())return;
  if(!validAudienceOriginal(ak,institute) || !sameAudienceOriginal(a,ak) || !validTemplateOriginal(tk,institute) || !sameTemplateOriginal(t,tk))throw Error("Independent selected originals differ");
  const pages:RetainedAudiencePage[]=[];let after:string|null=null;
  for(let i=0;i<a.summary.page_count;i++){
    if(!current())return;const p=await get(`${base}/audience-captures/${encodeURIComponent(a.id)}/pages/${i}`);if(!current())return;
    if(!validRetainedAudiencePage(p,a,i,after))throw Error("Invalid retained audience page");pages.push(p);after=p.observation.next_after;
  }
  const content=marketingSourceContent(institute,a,t,pages);if(!content)throw Error("Incoherent historical marketing sources");
  return current() ? {audience:a,template:t,content} : undefined;
}
// Reconstruct historical recipient terms from every retained page, never the current CRM cohort.
export function marketingSourceContent(institute:string,audience:AudienceOriginal,template:TemplateOriginal,pages:RetainedAudiencePage[]):CampaignContent|undefined{
  if(!validAudienceOriginal(audience,institute) || !validTemplateOriginal(template,institute) || template.content.channel!==audience.request.channel || !Array.isArray(pages) || pages.length!==audience.summary.page_count)return;
  let after:string|null=null,customers=0,selected=0,eligible=0;const seen=new Set<string>(),recipients:string[]=[];
  for(let i=0;i<pages.length;i++){
    const p=pages[i];if(!validRetainedAudiencePage(p,audience,i,after))return;
    for(const item of p.observation.items){if(seen.has(item.customer_id))return;seen.add(item.customer_id);customers++;if(item.selected_segment)selected++;if(item.eligible_by_recorded_permission){eligible++;recipients.push(item.customer_id);}}
    after=p.observation.next_after;
  }
  if(customers!==audience.summary.customer_count || selected!==audience.summary.selected_count || eligible!==audience.summary.eligible_count || !eligible)return;
  const t=template.content,content:CampaignContent={institute_id:institute,channel:t.channel,origin:t.origin,subject:t.subject,body:t.body,template_original_id:template.id,audience:{id:audience.id,institute_id:institute,captured_at:audience.captured_at,customer_ids:recipients}};
  return validCampaignContent(content,institute) ? content : undefined;
}
