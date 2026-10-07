import { certificationInstant as instant } from "./certification-utils";
import { validContactOriginal, type ContactOriginal } from "./marketing-contact-utils";
import { sameCampaignOriginal, type CampaignOriginal } from "./marketing-campaign-utils";
export type RecipientItem = { customer: { institute_id: string; customer_id: string; created_at: string }; original: ContactOriginal | null;
  reason: string; eligible_by_current_declaration: boolean };
export type RecipientPage = { institute_id: string; campaign: CampaignOriginal; expected_revision_id: string; captured_at: string;
  total: number; offset: number; limit: number; items: RecipientItem[]; complete_campaign_evaluation: false; delivery_authorized: false; external_message_sent: false };
const keys = (v: unknown, names: string[]) => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).length === names.length && names.every(n => Object.prototype.hasOwnProperty.call(v, n));
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
export async function validRecipientPage(v: unknown, campaign: CampaignOriginal, offset: number, limit: number): Promise<boolean> {
  const p = v as RecipientPage, r = campaign.revision;
  if (!keys(p, ["institute_id", "campaign", "expected_revision_id", "captured_at", "total", "offset", "limit", "items", "complete_campaign_evaluation", "delivery_authorized", "external_message_sent"])
    || p.institute_id !== r.institute_id || p.expected_revision_id !== r.id || instant(p.captured_at) === undefined
    || !count(offset) || !count(limit) || limit < 1 || limit > 50 || p.offset !== offset || p.limit !== limit || p.total !== r.content.audience.customer_ids.length
    || p.complete_campaign_evaluation !== false || p.delivery_authorized !== false || p.external_message_sent !== false
    || !Array.isArray(p.items) || !await sameCampaignOriginal(p.campaign, campaign, r.institute_id)) return false;
  const members = r.content.audience.customer_ids.slice(offset, offset + limit);
  if (p.items.length !== members.length) return false;
  for (let index = 0; index < p.items.length; index++) {
    const i = p.items[index], c = i?.customer, o = i?.original;
    if (!keys(i, ["customer", "original", "reason", "eligible_by_current_declaration"]) || !keys(c, ["institute_id", "customer_id", "created_at"])
      || c.institute_id !== r.institute_id || c.customer_id !== members[index] || instant(c.created_at) === undefined
      || o !== null && !validContactOriginal(o, r.institute_id, c.customer_id)) return false;
    const communication = o?.declaration.communications.find(c => c.channel === r.content.channel);
    const reason = !["APPROVE", "SEND"].includes(r.state) ? "campaign_not_approved" : instant(r.created_at)! > instant(p.captured_at)! ? "future_campaign"
      : instant(c.created_at)! > instant(p.captured_at)! ? "future_registration" : o === null ? "declaration_absent"
      : instant(o.created_at)! > instant(p.captured_at)! ? "future_declaration" : communication!.permission === "unknown" ? "permission_unknown"
      : communication!.permission === "refused" ? "permission_refused" : communication!.destination === null ? "destination_absent" : "declared_eligible";
    if (i.reason !== reason || i.eligible_by_current_declaration !== (reason === "declared_eligible")) return false;
  }
  return true;
}
