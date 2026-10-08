import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validWaitlistOriginalAudit, validWaitlistEnvelope } from "../src/waitlist-original-utils";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
const fixture = JSON.parse(readFileSync(new URL("./fixtures/waitlist-originals-15g.json", import.meta.url), "utf8"));

test("backend original raw fingerprint and logical scope/source/chronology claims are independently checked", async () => {
  assert.equal(await validWaitlistOriginalAudit(fixture, "own", 0), true);
  assert.equal(await validWaitlistOriginalAudit(fixture, "foreign", 0), false);
  for (const attack of [
    (o: any) => { o.source.duration_minutes = 31; }, (o: any) => { o.demand.institute_id = "foreign"; },
    (o: any) => { o.action = "booked"; }, (o: any) => { o.state = "active"; },
    (o: any) => { o.source.registered_at = "2026-10-08T10:00:00.000001Z"; },
    (o: any) => { o.demand.allowed_employee_ids.push("employee"); o.source.allowed_employee_ids.push("employee"); },
    (o: any) => { o.demand.availability.push(o.demand.availability[0]); },
    (o: any) => { o.demand.duration_minutes = o.source.duration_minutes = true; },
    (o: any) => { o.demand.constraints_review = "unknown"; },
  ]) {
    const vector = structuredClone(fixture); attack(vector.originals[0].original);
    vector.originals[0].fingerprint = await revenueOriginalFingerprint(vector.originals[0].original);
    assert.equal(await validWaitlistOriginalAudit(vector, "own", 0), false);
  }
  const changed = structuredClone(fixture); changed.originals[0].original.reason = "Changed original";
  assert.equal(await validWaitlistEnvelope(changed.originals[0], "own"), false);
});

test("original pages preserve exact cardinality, chronology and retained expired availability", async () => {
  const page = structuredClone(fixture); page.total = 25; page.originals = [];
  for (let n = 0; n < 20; n++) {
    const envelope = structuredClone(fixture.originals[0]); envelope.original.id = `waitlist_demand_${String(n).padStart(3,"0")}`;
    envelope.fingerprint = await revenueOriginalFingerprint(envelope.original); page.originals.push(envelope);
  }
  assert.equal(await validWaitlistOriginalAudit(page, "own", 0), true);
  page.originals.reverse(); assert.equal(await validWaitlistOriginalAudit(page, "own", 0), false);
  page.originals.reverse(); page.originals.pop(); assert.equal(await validWaitlistOriginalAudit(page, "own", 0), false);
  const later = structuredClone(fixture); later.captured_at = "2027-01-01T00:00:00Z";
  assert.equal(await validWaitlistOriginalAudit(later, "own", 0), true);
  later.total = Number.MAX_SAFE_INTEGER+1; assert.equal(await validWaitlistOriginalAudit(later, "own", 0), false);
});
