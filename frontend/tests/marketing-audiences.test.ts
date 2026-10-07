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
test("capture manifests pin full request, actor, clock and coherent summary", () => {
  const a = original(); assert.equal(validAudienceOriginal(a, "i"), true);
  assert.equal(matchesAudienceReceipt(a, a.request, "manager"), true);
  assert.equal(matchesAudienceReceipt(a, a.request, "other"), false);
  assert.equal(matchesAudienceReceipt(a, { ...a.request, segments: ["ACTIVE"] }, "manager"), false);
  assert.equal(sameAudienceOriginal(a, { ...a, captured_at: "2026-10-07T02:00:00+02:00" }), true);
  assert.equal(sameAudienceOriginal(a, { ...a, summary: { ...a.summary, eligible_count: 1 } }), false);
  for (const patch of [{ institute_id: "other" }, { delivery_authorized: true }, { captured_at: "2026-10-07" },
    { summary: { ...a.summary, page_count: 2 } }, { summary: { ...a.summary, eligible_count: 2 } },
    { request: { ...a.request, segments: ["VIP", "VIP"] } }, { request: { ...a.request, segments: [] } }]) {
    assert.equal(validAudienceOriginal({ ...a, ...patch }, "i"), false);
  }
});
test("observation recomputes segment and exact channel/purpose permission", () => {
  const p = observation(); assert.equal(validAudienceObservation(p, "i"), true);
  for (const patch of [{ selected_segment: false }, { eligible_by_recorded_permission: true }, { marketing_permission: "granted" },
    { customer_id: "foreign" }, { delivery_authorized: true }, { declaration: { ...p.items[0].declaration, institute_id: "foreign" } }]) {
    assert.equal(validAudienceObservation({ ...p, items: [{ ...p.items[0], ...patch }] }, "i"), false);
  }
  const granted = structuredClone(p); granted.items[0].declaration!.declaration.communications.find(c => c.channel === "email" && c.purpose === "marketing")!.permission = "granted";
  granted.items[0].marketing_permission = "granted"; granted.items[0].eligible_by_recorded_permission = true;
  assert.equal(validAudienceObservation(granted, "i"), true);
  const future = structuredClone(granted); future.items[0].declaration!.created_at = "2026-10-07T00:00:00.000001Z";
  future.items[0].marketing_permission = "future_declaration"; future.items[0].eligible_by_recorded_permission = false;
  assert.equal(validAudienceObservation(future, "i"), true);
  const push = structuredClone(granted); push.selection.channel = "push"; push.items[0].marketing_permission = "unsupported_channel";
  push.items[0].eligible_by_recorded_permission = false; assert.equal(validAudienceObservation(push, "i"), true);
  assert.equal(validAudienceObservation({ ...p, items: [p.items[0], p.items[0]] }, "i"), false);
  assert.equal(validAudienceObservation({ ...p, next_after: "customer_a" }, "i"), false);
  assert.equal(validAudienceObservation({ ...p, captured_at: "2026-10-07T00:00:00.000001Z" }, "i"), false);
});
test("retained page binds capture/filter/clock/count and predecessor cursor", () => {
  const o = original(), p = observation(); o.request.segments = p.selection.segments;
  const retained = { capture_id: o.id, page_index: 0, observation: p };
  assert.equal(validRetainedAudiencePage(retained, o, 0, null), true);
  assert.equal(validRetainedAudiencePage(retained, o, 0, "customer_before"), false);
  assert.equal(validRetainedAudiencePage({ ...retained, capture_id: "foreign" }, o, 0, null), false);
  assert.equal(validRetainedAudiencePage(retained, { ...o, request: { ...o.request, channel: "sms" } }, 0, null), false);
  assert.equal(validRetainedAudiencePage(retained, { ...o, summary: { ...o.summary, customer_count: 2 } }, 0, null), false);
  const empty = { ...o, summary: { page_count: 1, customer_count: 0, selected_count: 0, eligible_count: 0 } };
  assert.equal(validRetainedAudiencePage({ ...retained, observation: { ...p, items: [] } }, empty, 0, null), true);
});
test("capture catalog requires exact pagination and descending clock/ascending ID ties", () => {
  const a = original(), b = { ...original(), id: "capture-b" };
  const p = { institute_id: "i", total: 2, offset: 0, limit: 20, items: [a, b] };
  assert.equal(validAudienceCatalog(p, "i", 0, 20), true);
  for (const patch of [{ total: 3 }, { offset: 1 }, { limit: 50 }, { items: [b, a] }, { items: [a, a] },
    { items: [a, { ...b, institute_id: "foreign" }] }]) assert.equal(validAudienceCatalog({ ...p, ...patch }, "i", 0, 20), false);
  assert.equal(validAudienceCatalog({ ...p, items: [a, { ...b, captured_at: "2026-10-06T00:00:00Z" }] }, "i", 0, 20), true);
  assert.equal(validAudienceCatalog({ ...p, offset: 2, items: [] }, "i", 2, 20), true);
});
