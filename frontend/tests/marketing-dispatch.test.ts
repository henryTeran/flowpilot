import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dispatchFingerprint, validDispatchAccount, validDispatchAccountPage, validDispatchRequest, validDispatchIntent,
  validDispatchIntentPage, validDispatchOutcome, validDispatchOutcomePage, matchesDispatchReceipt, sameDispatchIntent,
  type DispatchIntent, type DispatchOutcome } from "../src/marketing-dispatch-utils";
const vectors = JSON.parse(readFileSync(new URL("./fixtures/marketing-dispatch-13ar.json", import.meta.url), "utf8")) as {
  institute_id: string; account_page: any; intent: DispatchIntent; intent_page: any; outcome: DispatchOutcome; outcome_page: any }[];

for (const vector of vectors) test(`retained backend ${vector.intent.submission.account.channel} sources and SHA-256 match native contracts`, async () => {
  const { institute_id: institute, intent, outcome } = vector, account = intent.submission.account;
  assert.equal(await dispatchFingerprint(intent.submission), intent.request_fingerprint);
  assert.equal(await validDispatchIntent(intent, institute), true);
  assert.equal(validDispatchAccountPage(vector.account_page, institute, account.channel, 0, 20), true);
  assert.equal(await validDispatchIntentPage(vector.intent_page, institute, intent.request.campaign_id, 0, 20), true);
  assert.equal(await validDispatchOutcome(outcome, intent, institute), true);
  assert.equal(await validDispatchOutcomePage(vector.outcome_page, intent, institute, 0, 20), true);
  assert.equal(matchesDispatchReceipt(intent, intent.request, "manager", account), true);
  assert.equal(matchesDispatchReceipt(intent, intent.request, "other", account), false);
  assert.equal(matchesDispatchReceipt(intent, { ...intent.request, reason: "Changed reason" }, "manager", account), false);
  assert.equal(matchesDispatchReceipt(intent, intent.request, "manager", { ...account, mode: "live" }), false);
  const offset = structuredClone(intent);
  function alternate(v: any): void {
    if (v && typeof v === "object") for (const [key, value] of Object.entries(v)) {
      if (key.endsWith("_at") && typeof value === "string") v[key] = value.replace("T12:", "T14:").replace(/Z$/, "+02:00");
      else alternate(value);
    }
  }
  alternate(offset);
  assert.equal(await sameDispatchIntent(intent, offset, institute), true);
  assert.equal(await dispatchFingerprint(offset.submission), intent.request_fingerprint);
  const changedClock = structuredClone(intent); changedClock.created_at = changedClock.submission.eligibility.captured_at = "2026-10-07T12:00:00.000006Z";
  assert.equal(await validDispatchIntent(changedClock, institute), false);
  assert.notEqual(await dispatchFingerprint(changedClock.submission), intent.request_fingerprint);
});

test("account selection refuses foreign channels/scopes/extra credentials and preserves Python ordering", () => {
  const { institute_id: institute, intent, account_page: page } = vectors[0], account = intent.submission.account;
  for (const patch of [{ institute_id: "foreign" }, { channel: "push" }, { mode: "unknown" }, { account_id: " account" },
    { sender_id: "bad\nheader" }, { push_application: "app" }, { secret: "never-inline" }])
    assert.equal(validDispatchAccount({ ...account, ...patch }, institute, "email"), false);
  for (const patch of [{ total: 2 }, { offset: 1 }, { limit: 51 }, { items: [account, account] }, { institute_id: "foreign" }])
    assert.equal(validDispatchAccountPage({ ...page, ...patch }, institute, "email", 0, 20), false);
  const ordered = { ...page, total: 2, items: [{ ...account, account_id: "\ue000" }, { ...account, account_id: "\u{1f642}" }] };
  assert.equal(validDispatchAccountPage(ordered, institute, "email", 0, 20), true);
  assert.equal(validDispatchAccountPage({ ...ordered, items: [...ordered.items].reverse() }, institute, "email", 0, 20), false);
  assert.equal(validDispatchAccountPage({ ...page, total: 0, items: [] }, institute, "email", 0, 20), true);
});

test("intent rejects altered full sources/actor/key/account/fingerprint and malformed values without authority claims", async () => {
  const { intent, institute_id: institute } = vectors[2];
  for (const value of [null, {}, [], { ...intent, request_fingerprint: "0".repeat(64) }, { ...intent, extra: true },
    { ...intent, request: { ...intent.request, account_id: "other" } }, { ...intent, request: { ...intent.request, expected_contact_id: "other" } }])
    assert.equal(await validDispatchIntent(value, institute), false);
  for (const change of ["actor", "key", "permission", "app", "content", "delivery", "future", "member"] as const) {
    const i = structuredClone(intent), s = i.submission, e = s.eligibility;
    if (change === "actor") s.actor_id = "changed";
    if (change === "key") s.idempotency_key = "changed";
    if (change === "permission") e.original.declaration.communications[2].permission = "refused";
    if (change === "app") s.account.push_application = "other";
    if (change === "content") e.campaign.content.body = "Changed literal";
    if (change === "delivery") (e as any).delivery_authorized = true;
    if (change === "future") e.original.created_at = "2026-10-08T12:00:00Z";
    if (change === "member") e.customer.customer_id = "foreign";
    assert.equal(await validDispatchIntent(i, institute), false, change);
  }
  assert.equal(validDispatchRequest({ ...intent.request, idempotency_key: "bad\nkey" }), false);
});

test("bounded intent pages enforce scope exact slices chronology and duplicate refusal", async () => {
  const { intent, institute_id: institute, intent_page: page } = vectors[0];
  const later = { ...structuredClone(intent), id: "z-later" };
  const first = { ...structuredClone(intent), id: "a-first" };
  const expanded = { ...page, total: 2, items: [first, later] };
  assert.equal(await validDispatchIntentPage(expanded, institute, intent.request.campaign_id, 0, 20), true);
  for (const patch of [{ total: 3 }, { items: [later, first] }, { items: [first, first] }, { offset: 1 }])
    assert.equal(await validDispatchIntentPage({ ...expanded, ...patch }, institute, intent.request.campaign_id, 0, 20), false);
  assert.equal(await validDispatchIntentPage({ ...expanded, offset: 2, items: [] }, institute, intent.request.campaign_id, 2, 20), true);
});

test("submission observations never confirm delivery or cross retained intent terms", async () => {
  const { intent, outcome, institute_id: institute } = vectors[0];
  for (const patch of [{ delivery_confirmed: true }, { delivery_confirmed: 0 }, { provider_message_id: null }, { provider_message_id: "bad\nreference" },
    { request_fingerprint: "0".repeat(64) }, { idempotency_key: "other" }, { account: { ...intent.submission.account, mode: "live" } },
    { observed_at: "2026-10-08T12:00:00Z" }])
    assert.equal(await validDispatchOutcome({ ...outcome, request: { ...outcome.request, result: { ...outcome.request.result, ...patch } } }, intent, institute), false);
  assert.equal(await validDispatchOutcome({ ...outcome, request: { ...outcome.request, expected_previous_id: outcome.id } }, intent, institute), false);
});

test("outcome audit refuses present cycles terminal successors changed references and false totals", async () => {
  const { intent, institute_id: institute, outcome_page: page } = vectors[0];
  const unknown = structuredClone(page.items.find((o: DispatchOutcome) => o.request.result.status === "unknown"));
  const accepted = structuredClone(page.items.find((o: DispatchOutcome) => o.request.result.status === "accepted"));
  unknown.id = "a-unknown"; unknown.request.expected_previous_id = null; accepted.id = "b-accepted"; accepted.request.expected_previous_id = unknown.id;
  const ordered = { ...page, items: [unknown, accepted] };
  assert.equal(await validDispatchOutcomePage(ordered, intent, institute, 0, 20), true);
  const terminalPrior = structuredClone(ordered); terminalPrior.items[0].request.result.status = "rejected";
  assert.equal(await validDispatchOutcomePage(terminalPrior, intent, institute, 0, 20), false);
  const reference = structuredClone(ordered); reference.items[0].request.result.provider_message_id = "different";
  assert.equal(await validDispatchOutcomePage(reference, intent, institute, 0, 20), false);
  const cycle = structuredClone(ordered); cycle.items[0].request.expected_previous_id = cycle.items[1].id;
  assert.equal(await validDispatchOutcomePage(cycle, intent, institute, 0, 20), false);
  assert.equal(await validDispatchOutcomePage({ ...ordered, total: 3 }, intent, institute, 0, 20), false);
  assert.equal(await validDispatchOutcomePage({ ...ordered, offset: 1, limit: 1, items: [accepted] }, intent, institute, 1, 1), true);
});

test("fingerprint retains nonselected channel facts and original array order", async () => {
  const { intent, institute_id: institute } = vectors[2];
  const changed = structuredClone(intent);
  changed.submission.eligibility.original.declaration.communications[0].destination!.email = "other@example.com";
  assert.notEqual(await dispatchFingerprint(changed.submission), intent.request_fingerprint);
  assert.equal(await validDispatchIntent(changed, institute), false);
  const ordered = structuredClone(intent); ordered.submission.eligibility.original.declaration.communications.reverse();
  assert.notEqual(await dispatchFingerprint(ordered.submission), intent.request_fingerprint);
  assert.equal(await validDispatchIntent(ordered, institute), false);
  assert.equal(validDispatchAccountPage({ institute_id: institute, total: 0, offset: 0, limit: 20, items: [] }, institute, "unknown" as any, 0, 20), false);
  assert.equal(await validDispatchIntentPage({ institute_id: institute, total: 0, offset: 0, limit: 20, items: [] }, institute, "", 0, 20), false);
});
