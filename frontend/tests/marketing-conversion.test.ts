import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { attributionFingerprint, validAttribution, validConversionOriginal, validConversionRequest, validConversionPreview,
  validConversionSelection, matchesConversionReceipt, sameConversionOriginal, validCurrentConversionPage, validConversionAuditPage,
  validConversionReport, type ConversionOriginal, type ConversionReport } from "../src/marketing-conversion-utils";
const vector = JSON.parse(readFileSync(new URL("./fixtures/marketing-conversions-13bb.json", import.meta.url), "utf8"));
const { institute_id: institute, campaign_id: campaign, window: period, linked, retracted } = vector;
const clone = <T,>(v: T): T => structuredClone(v);
function changed(v: any, path: string[], value: unknown): any {
  const result = clone(v); let cursor = result;
  for (const key of path.slice(0, -1)) cursor = cursor[key];
  cursor[path[path.length - 1]] = value; return result;
}

test("actual retained link/retraction/backend fingerprint and summary/page contracts agree", async () => {
  assert.equal(await attributionFingerprint(linked.attribution), linked.attribution_fingerprint);
  assert.equal(await validConversionOriginal(linked, institute, linked.request.ticket_id), true);
  assert.equal(await validConversionOriginal(retracted, institute, linked.request.ticket_id), true);
  assert.equal(await validCurrentConversionPage(vector.page, institute, campaign, period, 0, 20), true);
  assert.equal(await validConversionAuditPage(vector.audit, institute, linked.request.ticket_id, 0, 20), true);
  assert.equal(validConversionReport(vector.report, institute, campaign, period), true);
  assert.equal(validConversionReport(vector.empty_report, institute, campaign, period), true);
  assert.equal(matchesConversionReceipt(linked, linked.request, "manager"), true);
  assert.equal(matchesConversionReceipt(linked, linked.request, "other-manager"), false);
  assert.equal(matchesConversionReceipt(linked, { ...linked.request, reason: "Other reason" }, "manager"), false);
  assert.equal(await sameConversionOriginal(linked, retracted, institute), false);
});

test("aware alternate offsets preserve full UTC microsecond fingerprint and receipt terms", async () => {
  const alternate = clone(linked);
  function offsets(v: any): void {
    if (!v || typeof v !== "object") return;
    for (const [key, value] of Object.entries(v)) {
      if ((key.endsWith("_at") || ["start", "end"].includes(key)) && typeof value === "string")
        v[key] = value.replace("T12:", "T14:").replace(/Z$|\+00:00$/, "+02:00");
      else offsets(value);
    }
  }
  offsets(alternate);
  assert.equal(await validConversionOriginal(alternate, institute), true);
  assert.equal(await attributionFingerprint(alternate.attribution), linked.attribution_fingerprint);
  assert.equal(await sameConversionOriginal(alternate, linked, institute), true);
  assert.equal(matchesConversionReceipt(alternate, linked.request, "manager"), true);
  assert.equal(await validAttribution(changed(linked.attribution, ["ticket", "closed_at"], linked.attribution.window.end), institute), false);
  assert.equal(await validAttribution(changed(linked.attribution, ["window", "start"], "2026-10-07T12:00:00Z"), institute), false);
});

test("source substitutions, unsafe claims and amount inconsistencies refuse attribution", async () => {
  const a = linked.attribution;
  for (const [path, value] of [
    [["intent", "request_fingerprint"], "0".repeat(64)], [["authorization", "revision", "previous_id"], "other"],
    [["authorization", "request", "reason"], "Different reason"], [["authorization", "revision", "state"], "APPROVE"],
    [["accepted", "request", "intent_id"], "other"], [["accepted", "request", "result", "status"], "unknown"],
    [["accepted", "request", "result", "provider_message_id"], null], [["accepted", "request", "result", "delivery_confirmed"], true],
    [["ticket", "customer_id"], "foreign"], [["ticket", "institute_id"], "foreign"], [["ticket", "currency"], "USD"],
    [["ticket", "amount_minor"], "01"], [["ticket", "amount_minor"], 12345], [["ticket", "amount_minor"], "10000000000"],
    [["ticket", "amount_quality"], "missing"], [["window", "captured_at"], "2026-10-11T12:00:00Z"],
    [["actor_id"], "bad\nactor"], [["causal_effect_proven"], 0], [["delivery_confirmed"], "false"], [["extra"], "untrusted"],
  ] as [string[], unknown][]) assert.equal(await validAttribution(changed(a, path, value), institute), false, path.join("."));
  assert.equal(await validAttribution(a, "foreign"), false);
  const missing = clone(a); missing.ticket.amount_minor = null; missing.ticket.amount_quality = "missing";
  assert.equal(await validAttribution(missing, institute), true);
  missing.ticket.currency = null; missing.ticket.amount_quality = "invalid";
  assert.equal(await validAttribution(missing, institute), true);
});

test("complete retained fingerprint preserves literal date-looking messages, reasons and Unicode", async () => {
  const a = clone(linked.attribution);
  a.reason = "2026-10-07T12:00:00+02:00";
  const f = await attributionFingerprint(a);
  a.reason = "2026-10-07T10:00:00Z";
  assert.notEqual(await attributionFingerprint(a), f);
  a.reason = "Literal \u00e9 \ud83d\ude42 {customer_name}";
  const u = await attributionFingerprint(a);
  a.reason += "!";
  assert.notEqual(await attributionFingerprint(a), u);
});

test("request and preview require exact selected sources, actor, operation and non-retention", async () => {
  const s = linked.request.selection;
  assert.equal(validConversionSelection(s), true);
  assert.equal(validConversionRequest(linked.request), true);
  assert.equal(validConversionRequest(retracted.request), true);
  for (const patch of [{ selection: null }, { ticket_id: "other" }, { actor_id: "injected" }, { expected_previous_id: 0 }, { action: "delete" }])
    assert.equal(validConversionRequest({ ...linked.request, ...patch }), false);
  assert.equal(validConversionRequest({ ...retracted.request, expected_previous_id: null }), false);
  const preview = { request: s, attribution: linked.attribution, retained: false };
  assert.equal(await validConversionPreview(preview, institute, s, "manager"), true);
  assert.equal(await validConversionPreview(preview, institute, s, "other"), false);
  assert.equal(await validConversionPreview({ ...preview, retained: 0 }, institute, s, "manager"), false);
  assert.equal(await validConversionPreview(preview, institute, { ...s, authorization_id: "other" }, "manager"), false);
});

test("original refuses actor/clock/request/ticket changes; retraction retains historical actor", async () => {
  for (const [path, value] of [
    [["actor_id"], "other-manager"], [["created_at"], "2026-10-11T12:00:00Z"],
    [["request", "selection", "authorization_id"], "other"], [["request", "ticket_id"], "other"],
    [["attribution_fingerprint"], "0".repeat(64)], [["request", "expected_previous_id"], linked.id],
  ] as [string[], unknown][]) assert.equal(await validConversionOriginal(changed(linked, path, value), institute), false, path.join("."));
  assert.equal(await validConversionOriginal(linked, institute, "other-ticket"), false);
  assert.equal(retracted.actor_id, "other-manager");
  assert.equal(retracted.attribution.actor_id, "manager");
  assert.equal(await validConversionOriginal(retracted, institute), true);
});

test("current pages reject retractions, different campaign/window, duplicates and incoherent bounds", async () => {
  for (const page of [{ ...vector.page, items: [retracted] }, { ...vector.page, total: 2 },
    { ...vector.page, total: 2, items: [linked, linked] }, { ...vector.page, offset: 1 }, { ...vector.page, institute_id: "foreign" }])
    assert.equal(await validCurrentConversionPage(page, institute, campaign, period, 0, 20), false);
  assert.equal(await validCurrentConversionPage(vector.page, institute, "other", period, 0, 20), false);
  assert.equal(await validCurrentConversionPage(vector.page, institute, campaign, { start: linked.attribution.window.end, end: "2026-10-11T12:00:00Z" }, 0, 20), false);
  assert.equal(await validCurrentConversionPage({ ...vector.page, offset: 1, items: [] }, institute, campaign, period, 1, 20), true);
  assert.equal(await validCurrentConversionPage(vector.page, institute, campaign, period, 0, 51), false);
  const first = clone(linked), second = clone(linked);
  for (const [o, ticket] of [[first, "a-ticket"], [second, "b-ticket"]] as [ConversionOriginal, string][]) {
    o.id = ticket; o.request.ticket_id = o.request.selection!.ticket_id = o.attribution.ticket.ticket_id = ticket;
    o.attribution_fingerprint = await attributionFingerprint(o.attribution);
    assert.equal(await validConversionOriginal(o, institute), true);
  }
  assert.equal(await validCurrentConversionPage({ ...vector.page, total: 2, items: [first, second] }, institute, campaign, period, 0, 20), false);
});

test("audit detects present predecessor cycles and altered retraction snapshots, leaves outside ancestors unproven", async () => {
  const page = clone(vector.audit);
  assert.equal(await validConversionAuditPage({ ...page, offset: 1, items: page.items.slice(1) }, institute, linked.request.ticket_id, 1, 20), true);
  const cycle = clone(page);
  cycle.items.find((o: ConversionOriginal) => o.id === linked.id).request.expected_previous_id = retracted.id;
  assert.equal(await validConversionAuditPage(cycle, institute, linked.request.ticket_id, 0, 20), false);
  const altered = clone(page), retract = altered.items.find((o: ConversionOriginal) => o.id === retracted.id);
  retract.attribution.reason = "Altered historical snapshot";
  retract.attribution_fingerprint = await attributionFingerprint(retract.attribution);
  assert.equal(await validConversionOriginal(retract, institute), true);
  assert.equal(await validConversionAuditPage(altered, institute, linked.request.ticket_id, 0, 20), false);
  const duplicateKey = clone(page);
  duplicateKey.items.find((o: ConversionOriginal) => o.id === retracted.id).request.idempotency_key = linked.request.idempotency_key;
  assert.equal(await validConversionAuditPage(duplicateKey, institute, linked.request.ticket_id, 0, 20), false);
});

test("report binds selected observed period and exact counts, modes, currencies and no-claims", () => {
  for (const [path, value] of [
    [["full_retained_current_cohort"], 1], [["selected_current_links"], 2], [["summary", "linked_tickets"], 1.5],
    [["summary", "test_linked_tickets"], 0], [["summary", "unknown_currency_test_tickets"], 1],
    [["summary", "window", "captured_at"], period.start], [["summary", "complete_campaign_history"], true],
    [["summary", "causal_effect_proven"], 0], [["summary", "conversion_rate"], 0], [["summary", "return_on_ad_spend"], "1"],
  ] as [string[], unknown][]) assert.equal(validConversionReport(changed(vector.report, path, value), institute, campaign, period), false, path.join("."));
  assert.equal(validConversionReport(vector.report, institute, "other", period), false);
  assert.equal(validConversionReport(vector.report, "foreign", campaign, period), false);
  assert.equal(validConversionReport(vector.report, institute, campaign, { ...period, start: "2026-10-08T12:00:00Z" }), false);
  for (const patch of [{ known_gross_minor: 12345 }, { known_gross_minor: "012345" }, { known_amount_tickets: 0 },
    { currency: "USD" }, { mode: "LIVE" }, { linked_tickets: -1 }, { missing_amount_tickets: 1 }, { known_gross_minor: "10000000000" }]) {
    const report = clone(vector.report); Object.assign(report.summary.currencies[0], patch);
    assert.equal(validConversionReport(report, institute, campaign, period), false);
  }
});

test("report preserves arbitrary precision minor strings and separates unknown currency diagnostics", () => {
  const report: ConversionReport = clone(vector.report);
  report.selected_current_links = report.summary.linked_tickets = report.summary.test_linked_tickets = 1000000;
  const c = report.summary.currencies[0]; c.linked_tickets = c.known_amount_tickets = 1000000; c.known_gross_minor = "9007199254740993";
  assert.equal(validConversionReport(report, institute, campaign, period), true);
  assert.equal(report.summary.currencies[0].known_gross_minor, "9007199254740993");
  report.summary.unknown_currency_test_tickets = 1;
  c.linked_tickets = c.known_amount_tickets = 999999;
  assert.equal(validConversionReport(report, institute, campaign, period), true);
  report.summary.currencies.push(clone(c));
  assert.equal(validConversionReport(report, institute, campaign, period), false);
});
