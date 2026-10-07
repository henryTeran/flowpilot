import test from "node:test";
import assert from "node:assert/strict";
import { validLifetimeRead, validLifetimeTerms, validLifetimeOriginal, matchesLifetimeReceipt, sameLifetimeOriginal, type LifetimeRead } from "../src/crm-lifetime-utils";
import { crmLifetime as sample } from "./crm-lifetime-fixture";
const start = "2026-10-06T00:00:00Z", end = "2026-10-07T00:00:00Z";
const valid = (r: unknown) => validLifetimeRead(r,"i","customer_a",start);
test("remaining lifetime guard recalculates reduced signed ratios and exact source chronology", () => {
  assert.equal(valid(sample()),true);
  const corrupt: ((r: LifetimeRead) => void)[] = [r => { r.scenario!.remaining_clv_minor!.numerator="199"; },
    r => { r.scenario!.projected_gross_minor!.numerator="102"; },r => { r.scenario!.projected_contribution_minor!.denominator="2"; },
    r => { r.scenario!.projected_gross_minor={ numerator:"202",denominator:"2" }; },r => { r.scenario!.assumed_active_until=end; },
    r => { r.window.customer_id="foreign"; },r => { r.customer.customer_id="foreign"; },r => { r.scenario!.assumptions.future_relationship_cost_minor="0"; },
    r => { r.window.captured_at="2026-10-07T00:00:00.000001Z"; },r => { r.scenario!.billing.window.start="2026-10-05T00:00:00Z"; }];
  for (const mutate of corrupt) { const r=sample(); mutate(r); assert.equal(valid(r),false); }
  assert.equal(valid(null),false);
  const alias=sample(); alias.window.end="2026-10-07T02:00:00+02:00"; assert.equal(valid(alias),true);
  const zero=sample(); zero.original!.assumptions.activity_fraction.numerator=zero.scenario!.assumptions.activity_fraction.numerator="0";
  zero.scenario!.projected_gross_minor=zero.scenario!.projected_contribution_minor={ numerator:"0",denominator:"1" };
  zero.scenario!.remaining_clv_minor={ numerator:"-100",denominator:"1" }; assert.equal(valid(zero),true);
  const large=sample(); large.original!.assumptions.future_relationship_cost_minor=large.scenario!.assumptions.future_relationship_cost_minor="9007199254740993";
  large.scenario!.remaining_clv_minor={ numerator:String(101n-9007199254740993n*3n),denominator:"3" }; assert.equal(valid(large),true);
});
test("original receipt pins every declaration, actor, predecessor and semantic microsecond clock", () => {
  const a=sample().original!;
  assert.equal(validLifetimeOriginal(a,"i","customer_a"),true); assert.equal(matchesLifetimeReceipt(a,a,"manager"),true);
  assert.equal(matchesLifetimeReceipt(a,a,"other"),false);
  const alias=structuredClone(a); alias.created_at="2026-10-06T02:00:00+02:00"; assert.equal(sameLifetimeOriginal(a,alias),true);
  alias.created_at="2026-10-06T00:00:00.000001Z"; assert.equal(sameLifetimeOriginal(a,alias),false);
  const changed=structuredClone(a); changed.assumptions.activity_fraction={ numerator:"2",denominator:"4" };
  assert.equal(matchesLifetimeReceipt(a,changed,"manager"),false);
  for (const mutate of [(r: typeof a) => { r.previous_id=r.id; }, (r: typeof a) => { r.assumptions.activity_fraction.numerator="3"; },
    (r: typeof a) => { r.assumptions.expected_active_us="01"; }, (r: typeof a) => { r.assumptions.gross_contribution_margin.denominator="0"; },
    (r: typeof a) => { r.customer_id="other"; }]) { const r=structuredClone(a); mutate(r); assert.equal(validLifetimeOriginal(r,"i","customer_a"),false); }
  const missing=structuredClone(a) as any; delete missing.previous_id; assert.equal(validLifetimeTerms(missing,"i","customer_a"),false);
  assert.equal(sameLifetimeOriginal({} as any,{} as any),false);
});
test("outer unavailable reasons obey original and registered-date precedence", () => {
  const absent=sample(); absent.original=null; absent.scenario=null; absent.unavailable_reason="assumptions_absent"; assert.equal(valid(absent),true);
  absent.unavailable_reason=null; assert.equal(valid(absent),false);
  const future=sample(); future.original!.created_at="2026-10-07T00:00:00.000001Z"; future.scenario=null; future.unavailable_reason="future_assumptions"; assert.equal(valid(future),true);
  future.customer.created_at="2026-10-07T00:00:00.000001Z"; assert.equal(valid(future),true);
  future.original!.created_at=start; future.unavailable_reason="future_registration"; assert.equal(valid(future),true);
});
test("source uncertainty suppresses all projections without favorable-subset averaging", () => {
  for (const reason of ["undated_closings","future_closings","unrepresentable_lifetime","unknown_currency","no_observed_currency","uncertain_amounts"] as const) {
    const r=sample(), s=r.scenario!;
    if (reason==="undated_closings") { s.undated_paid_tickets=1; s.assumed_active_until=null; }
    if (reason==="future_closings") { s.future_paid_tickets=1; s.assumed_active_until=null; }
    if (reason==="unrepresentable_lifetime") { r.original!.assumptions.expected_active_us=s.assumptions.expected_active_us="9".repeat(30); s.assumed_active_until=null; }
    if (reason==="unknown_currency") { s.billing.unknown_currency_tickets=1; s.billing.complete_currency_classification=false;
      s.billing.closed_tickets=2; s.billing.frequency_per_microsecond.numerator="2"; }
    if (reason==="no_observed_currency") { r.original!.assumptions.currency=s.assumptions.currency="EUR"; }
    if (reason==="uncertain_amounts") { const g=s.billing.currencies[0]; g.known_amount_tickets=0; g.known_gross_minor="0"; g.missing_amount_tickets=1; g.recorded_average_basket_minor=null; }
    s.unavailable_reason=reason; s.projected_gross_minor=s.projected_contribution_minor=s.remaining_clv_minor=null;
    assert.equal(valid(r),true,reason); s.remaining_clv_minor={ numerator:"0",denominator:"1" }; assert.equal(valid(r),false,reason);
  }
});
