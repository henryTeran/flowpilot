import test from "node:test";
import assert from "node:assert/strict";
import { campaignDigest, validCampaignOriginal, validCampaignRequest, matchesCampaignReceipt, sameCampaignOriginal,
  validCampaignCatalog, validCampaignAuditPage, type CampaignContent, type CampaignOriginal } from "../src/marketing-campaign-utils";
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
test("audit pages pin exact bounds/scope/order and check present explicit predecessors", async () => {
  const draft = original(); draft.revision.id = "z-draft";
  const digest = await campaignDigest(draft.revision.content);
  const review: CampaignOriginal = { request: { ...draft.request, action: "review", campaign_id: "campaign-a", expected_revision_id: "z-draft", content: null },
    revision: { ...draft.revision, id: "a-review", previous_id: "z-draft", state: "REVIEW", reviewed_digest: digest } };
  // Equal-clock ID order places this review before its predecessor; this is legitimate.
  const p = { institute_id: "i", campaign_id: "campaign-a", total: 2, offset: 0, limit: 20, originals: [review, draft] };
  assert.equal(await validCampaignAuditPage(p, "i", "campaign-a", 0, 20), true);
  for (const patch of [{ total: 3 }, { offset: 1 }, { limit: 50 }, { campaign_id: "foreign" },
    { originals: [draft, review] }, { originals: [review, review] }]) assert.equal(await validCampaignAuditPage({ ...p, ...patch }, "i", "campaign-a", 0, 20), false);
  assert.equal(await validCampaignAuditPage({ ...p, total: 2, offset: 1, limit: 1, originals: [draft] }, "i", "campaign-a", 1, 1), true);
  assert.equal(await validCampaignAuditPage({ ...p, offset: 2, originals: [] }, "i", "campaign-a", 2, 20), true);
  const changed = structuredClone(draft); changed.request.content!.body = changed.revision.content.body = "Different retained draft";
  assert.equal(await validCampaignAuditPage({ ...p, originals: [review, changed] }, "i", "campaign-a", 0, 20), false);
  const cycle = { ...review, revision: { ...review.revision, id: "b-review", previous_id: review.revision.id },
    request: { ...review.request, expected_revision_id: review.revision.id } };
  assert.equal(await validCampaignAuditPage({ ...p, originals: [review, cycle] }, "i", "campaign-a", 0, 20), false);
  const firstEdit: CampaignOriginal = { request: { ...draft.request, action: "edit", campaign_id: "campaign-a", expected_revision_id: "b-edit" },
    revision: { ...draft.revision, id: "a-edit", previous_id: "b-edit" } };
  const secondEdit: CampaignOriginal = { request: { ...draft.request, action: "edit", campaign_id: "campaign-a", expected_revision_id: "a-edit" },
    revision: { ...draft.revision, id: "b-edit", previous_id: "a-edit" } };
  assert.equal(await validCampaignOriginal(firstEdit, "i"), true);
  assert.equal(await validCampaignOriginal(secondEdit, "i"), true);
  assert.equal(await validCampaignAuditPage({ ...p, originals: [firstEdit, secondEdit] }, "i", "campaign-a", 0, 20), false);
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
