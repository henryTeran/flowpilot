import {validAudienceOriginal,validRetainedAudiencePage,type AudienceOriginal,type RetainedAudiencePage} from "./marketing-audience-utils";
import {validTemplateOriginal,type TemplateOriginal} from "./marketing-template-utils";
import {validCampaignContent,type CampaignContent} from "./marketing-campaign-utils";
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
