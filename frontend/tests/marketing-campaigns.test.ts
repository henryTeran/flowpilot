import test from "node:test";
import assert from "node:assert/strict";
import { campaignDigest, validCampaignOriginal, validCampaignRequest, matchesCampaignReceipt, sameCampaignOriginal,
  validCampaignCatalog, type CampaignContent, type CampaignOriginal } from "../src/marketing-campaign-utils";
function content(clock = "2026-10-07T02:00:00.123456+02:00"): CampaignContent {
  return { institute_id: "i", channel: "email", origin: "ai", subject: "Bonjour é", body: "Bonjour {customer_name}\n🙂\x7f",
    template_original_id: null, audience: { id: "audience", institute_id: "i", captured_at: clock, customer_ids: ["customer_b", "customer_a"] } };
}
function original(): CampaignOriginal {
  const c = content(); return { request: { action: "create", campaign_id: null, expected_revision_id: null,
    content: { channel: c.channel, origin: c.origin, subject: c.subject, body: c.body, audience_id: c.audience.id, template_original_id: null },
    reason: "Explicit draft", idempotency_key: "key" }, revision: { id: "revision", campaign_id: "campaign-a", institute_id: "i", previous_id: null,
    state: "DRAFT", content: c, actor_id: "manager", reason: "Explicit draft", created_at: "2026-10-07T00:00:01Z",
    reviewed_digest: null, approved_digest: null, external_message_sent: false, delivery_authorized: false } };
}
test("campaign SHA-256 matches backend Python Unicode/UTC/microsecond vectors", async () => {
  for (const [clock, digest] of [
    ["2026-10-07T02:00:00.123456+02:00", "bed53fbb867e7dece6b846232f7a79c839cbe1ed3ed4e7856552eede921b8eb6"],
    ["1969-12-31T23:59:59.999999Z", "969151d2a2c8940021f537cb4698a55d0625f50af57928d10737376f32c99f28"],
    ["2026-10-07T00:00:00Z", "fae1c49e7a9606519efbaa75ea3efbae5d749e6337368d644c0335fbefecd11b"]]) assert.equal(await campaignDigest(content(clock)), digest);
  const c = content(); assert.notEqual(await campaignDigest(c), await campaignDigest({ ...c, audience: { ...c.audience, customer_ids: [...c.audience.customer_ids].reverse() } }));
});
test("native original enforces action/stage/source and exact review/approval digest", async () => {
  const a = original(); assert.equal(await validCampaignOriginal(a, "i"), true);
  const digest = await campaignDigest(a.revision.content);
  for (const [action, state] of [["review", "REVIEW"], ["approve", "APPROVE"]] as const) {
    const stage: CampaignOriginal = { request: { ...a.request, action, campaign_id: "campaign-a", expected_revision_id: "previous", content: null },
      revision: { ...a.revision, previous_id: "previous", state, reviewed_digest: digest, approved_digest: action === "approve" ? digest : null } };
    assert.equal(await validCampaignOriginal(stage, "i"), true);
    assert.equal(await validCampaignOriginal({ ...stage, revision: { ...stage.revision, content: { ...stage.revision.content, body: "Changed" } } }, "i"), false);
    assert.equal(await validCampaignOriginal({ ...stage, revision: { ...stage.revision, approved_digest: "forged" } }, "i"), false);
  }
  for (const patch of [{ institute_id: "foreign" }, { previous_id: "revision" }, { state: "SEND" }, { delivery_authorized: true },
    { created_at: "2026-10-07T00:00:00Z" }, { reviewed_digest: digest }, { content: { ...a.revision.content, body: "Changed" } }])
    assert.equal(await validCampaignOriginal({ ...a, revision: { ...a.revision, ...patch } }, "i"), false);
  assert.equal(validCampaignRequest({ ...a.request, action: "send" }), false);
  assert.equal(validCampaignRequest({ ...a.request, action: "approve" }), false);
});
test("recovery pins actor/full terms and independent originals normalize only instants", async () => {
  const a = original(); assert.equal(matchesCampaignReceipt(a, a.request, "manager"), true);
  assert.equal(matchesCampaignReceipt(a, a.request, "other"), false);
  assert.equal(matchesCampaignReceipt(a, { ...a.request, reason: "Other terms" }, "manager"), false);
  assert.equal(await sameCampaignOriginal(a, { ...a, revision: { ...a.revision, created_at: "2026-10-07T02:00:01+02:00" } }, "i"), true);
  assert.equal(await sameCampaignOriginal(a, { ...a, revision: { ...a.revision, created_at: "2026-10-07T00:00:01.000001Z" } }, "i"), false);
  const p = { institute_id: "i", total: 1, offset: 0, limit: 20, items: [a] };
  assert.equal(await validCampaignCatalog(p, "i", 0, 20), true);
  assert.equal(await validCampaignCatalog({ ...p, total: 2 }, "i", 0, 20), false);
  assert.equal(await validCampaignCatalog({ ...p, total: 2, items: [a, a] }, "i", 0, 20), false);
});
