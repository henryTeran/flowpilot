import test from "node:test";
import assert from "node:assert/strict";
import { validRecipientPage } from "../src/marketing-recipient-utils";
import { recipientFixture } from "./marketing-recipient-fixture";
import { campaignDigest } from "../src/marketing-campaign-utils";
test("recipient page bounds preserve retained membership order without a whole-cohort claim", async () => {
  const { campaign, page } = await recipientFixture();
  campaign.revision.content.audience.customer_ids = Array.from({ length: 21 }, (_, i) => `customer-${i}`);
  const digest = await campaignDigest(campaign.revision.content);
  campaign.revision.reviewed_digest = campaign.revision.approved_digest = digest;
  page.total = 21; page.offset = 20; page.items[0].customer.customer_id = "customer-20";
  page.items[0].original!.declaration.customer_id = "customer-20";
  assert.equal(await validRecipientPage(page, campaign, 20, 20), true);
  assert.equal(await validRecipientPage(page, campaign, 0, 20), false);
  assert.equal(await validRecipientPage({ ...page, items: [...page.items, ...page.items] }, campaign, 20, 20), false);
  assert.equal(await validRecipientPage({ ...page, offset: 21, items: [] }, campaign, 21, 20), true);
  assert.equal(await validRecipientPage({ ...page, complete_campaign_evaluation: true }, campaign, 20, 20), false);
});
test("recipient observations recompute current eligibility across all channels", async () => {
  for (const channel of ["email", "sms", "push"] as const) {
    const { campaign, page } = await recipientFixture(channel);
    assert.equal(await validRecipientPage(page, campaign, 0, 20), true);
    for (const reason of ["declaration_absent", "future_declaration", "permission_unknown", "permission_refused", "destination_absent", "future_registration", "future_campaign"] as const) {
      const p = structuredClone(page), item = p.items[0];
      item.reason = reason; item.eligible_by_current_declaration = false;
      const communication = item.original!.declaration.communications.find(c => c.channel === channel)!;
      if (reason === "declaration_absent") item.original = null;
      if (reason === "future_declaration") item.original!.created_at = "2026-10-07T00:00:03Z";
      if (reason === "permission_unknown") { communication.permission = "unknown"; communication.permission_evidence = null; }
      if (reason === "permission_refused") communication.permission = "refused";
      if (reason === "destination_absent") communication.destination = null;
      if (reason === "future_registration") item.customer.created_at = "2026-10-07T00:00:03Z";
      if (reason === "future_campaign") p.captured_at = "2026-10-07T00:00:00Z";
      assert.equal(await validRecipientPage(p, campaign, 0, 20), true, reason);
      item.eligible_by_current_declaration = true;
      assert.equal(await validRecipientPage(p, campaign, 0, 20), false, reason);
    }
    for (const patch of [{ total: 2 }, { offset: 1 }, { expected_revision_id: "other" }, { institute_id: "foreign" }, { items: [] },
      { delivery_authorized: true }, { external_message_sent: true }, { complete_campaign_evaluation: true }, { captured_at: "2026-10-07" }])
      assert.equal(await validRecipientPage({ ...page, ...patch }, campaign, 0, 20), false);
    const wrong = structuredClone(page); wrong.items[0].customer.customer_id = "foreign";
    assert.equal(await validRecipientPage(wrong, campaign, 0, 20), false);
    const forged = structuredClone(page); forged.campaign.revision.content.body = "Forged";
    assert.equal(await validRecipientPage(forged, campaign, 0, 20), false);
    assert.equal(await validRecipientPage({ ...page, items: [{ ...page.items[0], eligible_by_current_declaration: 1 }] }, campaign, 0, 20), false);
  }
});

test("SEND observations retain current grants and reject forged withdrawal eligibility", async () => {
  for (const channel of ["email", "sms", "push"] as const) {
    const { campaign, page } = await recipientFixture(channel);
    const approval = campaign.revision.id;
    campaign.request.action = "send"; campaign.request.expected_revision_id = approval;
    campaign.revision.id = "send"; campaign.revision.previous_id = approval; campaign.revision.state = "SEND";
    page.expected_revision_id = "send";
    assert.equal(await validRecipientPage(page, campaign, 0, 20), true);
    const communication = page.items[0].original!.declaration.communications.find(value => value.channel === channel)!;
    communication.permission = "refused";
    assert.equal(await validRecipientPage(page, campaign, 0, 20), false);
    page.items[0].reason = "permission_refused"; page.items[0].eligible_by_current_declaration = false;
    assert.equal(await validRecipientPage(page, campaign, 0, 20), true);
  }
});
