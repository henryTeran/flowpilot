import { campaignDigest, type CampaignOriginal } from "../src/marketing-campaign-utils";
import type { ContactOriginal } from "../src/marketing-contact-utils";
import type { RecipientPage } from "../src/marketing-recipient-utils";
export async function recipientFixture(channel: "email" | "sms" | "push" = "email") {
  const content = { institute_id: "i", channel, origin: "human" as const, subject: channel === "email" ? "Subject" : null,
    body: "Literal message", template_original_id: null, audience: { id: "audience", institute_id: "i", captured_at: "2026-10-07T00:00:00Z", customer_ids: ["customer"] } };
  const digest = await campaignDigest(content);
  const campaign: CampaignOriginal = { request: { action: "approve", campaign_id: "campaign", expected_revision_id: "review", content: null, reason: "Approve", idempotency_key: "approval-key" },
    revision: { id: "approval", campaign_id: "campaign", institute_id: "i", previous_id: "review", state: "APPROVE", content, actor_id: "manager", reason: "Approve",
      created_at: "2026-10-07T00:00:01Z", reviewed_digest: digest, approved_digest: digest, external_message_sent: false, delivery_authorized: false } };
  const contact: ContactOriginal = { id: "contact", previous_id: null, actor_id: "manager", created_at: "2026-10-07T00:00:00Z", reason: "Declare", idempotency_key: "contact-key",
    declaration: { institute_id: "i", customer_id: "customer", purpose: "marketing", communications: ["email", "sms", "push"].map(c => ({ channel: c as "email" | "sms" | "push",
      permission: "granted", permission_evidence: "Explicit permission", destination: { channel: c as "email" | "sms" | "push", email: c === "email" ? "customer@example.com" : null,
        phone: c === "sms" ? "+41791234567" : null, push_application: c === "push" ? "app" : null, push_token: c === "push" ? "secret-token" : null, evidence: "Explicit destination" } })) } };
  const page: RecipientPage = { institute_id: "i", campaign, expected_revision_id: "approval", captured_at: "2026-10-07T00:00:02Z", total: 1, offset: 0, limit: 20,
    items: [{ customer: { institute_id: "i", customer_id: "customer", created_at: "2026-10-06T00:00:00Z" }, original: contact, reason: "declared_eligible", eligible_by_current_declaration: true }],
    complete_campaign_evaluation: false, delivery_authorized: false, external_message_sent: false };
  return { campaign, contact, page };
}
