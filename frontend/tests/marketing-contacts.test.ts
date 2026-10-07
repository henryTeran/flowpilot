import test from "node:test";
import assert from "node:assert/strict";
import { validContactOriginal, validContactRequest, matchesContactReceipt, sameContactOriginal, type ContactOriginal } from "../src/marketing-contact-utils";
import { validAudienceOriginal, validAudienceCatalog, validAudienceObservation, validRetainedAudiencePage, matchesAudienceReceipt, type AudienceOriginal, type AudienceObservation } from "../src/marketing-audience-utils";
import { crmProfile } from "./crm-fixture";

export function contactOriginal(): ContactOriginal {
  return { id: "contact", previous_id: null, actor_id: "manager", created_at: crmProfile().captured_at,
    reason: "Explicit contacts", idempotency_key: "contact-key", declaration: { institute_id: "i", customer_id: "customer_a", purpose: "marketing",
      communications: ["email", "sms", "push"].map(c => ({ channel: c as "email" | "sms" | "push", permission: "granted", permission_evidence: "Explicit permission",
        destination: { channel: c as "email" | "sms" | "push", email: c === "email" ? "customer@example.com" : null,
          phone: c === "sms" ? "+41791234567" : null, push_application: c === "push" ? "app" : null, push_token: c === "push" ? "device-token" : null,
          evidence: "Explicit destination" } })) } };
}
test("contact originals bind own complete channels, exact destinations, actor and replay terms", () => {
  const o = contactOriginal(), request = { declaration: o.declaration, previous_id: o.previous_id, reason: o.reason, idempotency_key: o.idempotency_key };
  assert.equal(validContactOriginal(o, "i", "customer_a"), true); assert.equal(validContactRequest(request, "i", "customer_a"), true);
  assert.equal(matchesContactReceipt(o, request, "manager"), true); assert.equal(matchesContactReceipt(o, request, "other"), false);
  assert.equal(sameContactOriginal(o, { ...o, created_at: "2026-10-07T02:00:00+02:00" }), true);
  for (const patch of [{ previous_id: o.id }, { actor_id: " manager " }, { created_at: "2026-10-07" }, { idempotency_key: " key " }])
    assert.equal(validContactOriginal({ ...o, ...patch }, "i", "customer_a"), false);
  assert.equal(validContactOriginal(o, "foreign", "customer_a"), false);
  assert.equal(validContactOriginal(o, "i", "foreign"), false);
  for (const changed of ["reason", "idempotency_key", "previous_id"] as const) assert.equal(matchesContactReceipt(o, { ...request, [changed]: "Changed" }, "manager"), false);
  for (const channel of ["email", "sms", "push"] as const) {
    for (const change of [{ permission_evidence: null }, { permission: "unknown" }, { channel: "foreign" }]) {
      const bad = structuredClone(o); Object.assign(bad.declaration.communications.find(c => c.channel === channel)!, change);
      assert.equal(validContactOriginal(bad, "i", "customer_a"), false);
    }
  }
  for (const phone of ["0791234567", "+012345", "+41791234567\n"]) {
    const bad = structuredClone(o); bad.declaration.communications[1].destination!.phone = phone;
    assert.equal(validContactOriginal(bad, "i", "customer_a"), false);
  }
  for (const token of [" token ", "a\x00b", ""]) {
    const bad = structuredClone(o); bad.declaration.communications[2].destination!.push_token = token;
    assert.equal(validContactOriginal(bad, "i", "customer_a"), false);
  }
  const duplicate = structuredClone(o); duplicate.declaration.communications[2] = duplicate.declaration.communications[0];
  assert.equal(validContactOriginal(duplicate, "i", "customer_a"), false);
});

function contactPage(channel: "email" | "sms" | "push"): { original: AudienceOriginal; page: AudienceObservation } {
  const profile = crmProfile();
  const page: AudienceObservation = { institute_id: "i", captured_at: profile.captured_at,
    selection: { segments: [profile.segment!.state!], channel, after: null, permission_basis: "marketing_contact" }, next_after: null,
    items: [{ customer_id: "customer_a", profile, declaration: contactOriginal(), selected_segment: true, marketing_permission: "granted",
      eligible_by_recorded_permission: true, delivery_authorized: false }], complete_institute_audience: false, delivery_authorized: false };
  return { page, original: { id: "capture", institute_id: "i", actor_id: "manager", captured_at: profile.captured_at,
    request: { segments: page.selection.segments, channel, permission_basis: "marketing_contact", reason: "Explicit contacts", idempotency_key: "capture-key" },
    summary: { page_count: 1, customer_count: 1, selected_count: 1, eligible_count: 1 }, complete_registered_cohort: true, delivery_authorized: false } };
}
test("all three contact audience channels pin source basis and recompute permission", () => {
  for (const channel of ["email", "sms", "push"] as const) {
    const { page, original } = contactPage(channel);
    assert.equal(validAudienceOriginal(original, "i"), true); assert.equal(validAudienceObservation(page, "i"), true);
    assert.equal(validAudienceCatalog({ institute_id: "i", total: 1, offset: 0, limit: 20, items: [original] }, "i", 0, 20), true);
    const retained = { capture_id: "capture", page_index: 0, observation: page };
    assert.equal(validRetainedAudiencePage(retained, original, 0, null), true);
    const legacy = { ...original.request }; delete legacy.permission_basis;
    assert.equal(matchesAudienceReceipt(original, legacy, "manager"), false);
    assert.equal(validRetainedAudiencePage(retained, { ...original, request: legacy }, 0, null), false);
    const absentBasis = structuredClone(page); delete absentBasis.selection.permission_basis;
    assert.equal(validAudienceObservation(absentBasis, "i"), false);
    const withdrawn = structuredClone(page), declared = withdrawn.items[0].declaration as ContactOriginal;
    declared.declaration.communications.find(c => c.channel === channel)!.permission = "refused";
    assert.equal(validAudienceObservation(withdrawn, "i"), false);
    withdrawn.items[0].marketing_permission = "refused"; withdrawn.items[0].eligible_by_recorded_permission = false;
    assert.equal(validAudienceObservation(withdrawn, "i"), true);
    const missing = structuredClone(page); missing.items[0].declaration = null;
    missing.items[0].marketing_permission = "unknown"; missing.items[0].eligible_by_recorded_permission = false;
    assert.equal(validAudienceObservation(missing, "i"), true);
  }
});
