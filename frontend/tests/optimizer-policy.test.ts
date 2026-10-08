import test from "node:test";
import assert from "node:assert/strict";
import fixture from "./fixtures/optimizer-policy-16e.json";
import { validOptimizerPolicyEnvelope, validOptimizerPolicyRequest, validOptimizerPolicyAudit, matchesOptimizerPolicyReceipt,
  type OptimizerPolicyEnvelope, type OptimizerPolicyRequest } from "../src/optimizer-policy-utils";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
const receipt = fixture["0"].originals[0] as OptimizerPolicyEnvelope;
const original = receipt.original;
const request: OptimizerPolicyRequest = { terms: original.terms, reason: original.reason, idempotency_key: original.idempotency_key };

test("typed backend policy originals and 20/5/empty audit pages verify full SHA and exact scope", async () => {
  assert.equal(validOptimizerPolicyRequest(request), true);
  for (const offset of [0, 20, 40]) assert.equal(await validOptimizerPolicyAudit(fixture[String(offset) as keyof typeof fixture], "own", offset), true);
  assert.equal(await validOptimizerPolicyEnvelope(receipt, "foreign"), false);
  assert.equal(matchesOptimizerPolicyReceipt(receipt, request, original.actor_id), true);
  assert.equal(matchesOptimizerPolicyReceipt(receipt, request, "foreign"), false);
});
test("rehashing never makes malformed normalization, actor, action or canonical snapshot valid", async () => {
  const changes = [
    (o: any) => { o.actor_id = "signed-manager\n"; }, (o: any) => { o.reason = " trailing "; },
    (o: any) => { o.action = "book_now"; }, (o: any) => { o.created_at = "2026-10-08T13:00:00+02:00"; },
    (o: any) => { o.terms.rules[0].ceiling = "100"; }, (o: any) => { o.terms.rules[1].basis = "catalog_reference"; },
    (o: any) => { o.terms.rules[1].weight.denominator = "0"; }, (o: any) => { o.terms.rules[1].weight.numerator = "01"; },
    (o: any) => { o.terms.rules[1].weight.numerator = "1".repeat(41); }, (o: any) => { o.terms.rules[0] = o.terms.rules[1]; },
    (o: any) => { o.terms.rules[1].weight.numerator = "0"; o.terms.rules[1].basis = "disabled"; },
    (o: any) => { o.extra = true; }, (o: any) => { o.terms.normalization = "automatic"; },
  ];
  for (const change of changes) {
    const e = structuredClone(receipt); change(e.original); e.fingerprint = await revenueOriginalFingerprint(e.original);
    assert.equal(await validOptimizerPolicyEnvelope(e, "own"), false);
  }
  const e = structuredClone(receipt); e.original.reason = "Changed but not rehashed";
  assert.equal(await validOptimizerPolicyEnvelope(e, "own"), false);
});
test("enabled monetary and elapsed rules require their actual dimensions; zero weights require explicit disable", () => {
  const values = structuredClone(request);
  const revenue = values.terms.rules[0]; revenue.weight.numerator = "2"; revenue.basis = "catalog_reference";
  revenue.ceiling = "10000"; revenue.currency = "EUR"; revenue.price_mode = "passage";
  assert.equal(validOptimizerPolicyRequest(values), true);
  for (const change of [(r: any) => r.currency = null, (r: any) => r.price_mode = null, (r: any) => r.ceiling = "0",
    (r: any) => r.ceiling = "1.5", (r: any) => r.weight.numerator = "0"]) {
    const altered = structuredClone(values); change(altered.terms.rules[0]); assert.equal(validOptimizerPolicyRequest(altered), false);
  }
  const delay = values.terms.rules[5]; delay.weight.numerator = "1"; delay.basis = "elapsed_start_delay"; delay.ceiling = "60000000";
  assert.equal(validOptimizerPolicyRequest(values), true); delay.ceiling = null; assert.equal(validOptimizerPolicyRequest(values), false);
  assert.equal(validOptimizerPolicyRequest({ ...request, score: 1 }), false);
  assert.equal(validOptimizerPolicyRequest({ ...request, idempotency_key: "bad\nkey" }), false);
});
test("audit refuses future rows, disorder, duplicate identity/key, tamper and wrong paging", async () => {
  for (const change of [(p: any) => p.captured_at = "2026-10-08T10:00:00Z", (p: any) => p.originals.reverse(),
    (p: any) => p.originals[1] = p.originals[0], (p: any) => p.total = 1, (p: any) => p.limit = 50,
    (p: any) => p.originals[19].fingerprint = "0".repeat(64), (p: any) => p.offset = 20]) {
    const page = structuredClone(fixture["0"]); change(page); assert.equal(await validOptimizerPolicyAudit(page, "own", 0), false);
  }
  const page = structuredClone(fixture["0"]); page.originals[1].original.idempotency_key = page.originals[0].original.idempotency_key;
  page.originals[1].fingerprint = await revenueOriginalFingerprint(page.originals[1].original);
  assert.equal(await validOptimizerPolicyAudit(page, "own", 0), false);
});
test("receipt comparison preserves exact ordered rules and rational terms", () => {
  for (const change of [(r: any) => r.reason = "Other reason", (r: any) => r.terms.rules.reverse(),
    (r: any) => { r.terms.rules[1].weight.numerator = "2"; r.terms.rules[1].weight.denominator = "2"; }]) {
    const altered = structuredClone(request); change(altered); assert.equal(matchesOptimizerPolicyReceipt(receipt, altered, original.actor_id), false);
  }
});
