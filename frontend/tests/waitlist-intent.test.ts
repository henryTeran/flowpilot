import test from "node:test";
import assert from "node:assert/strict";
import fixture from "./fixtures/waitlist-originals-15g.json";
import { createWaitlistIntent, waitlistIntentKey } from "../src/waitlist-intent";
import { validWaitlistRequest, matchesWaitlistReceipt, type WaitlistEnvelope, type WaitlistRequest } from "../src/waitlist-original-utils";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";

const receipt = fixture.originals[0] as WaitlistEnvelope;
const { institute_id, declared_at, ...demand } = receipt.original.demand;
const terms: WaitlistRequest = { ...demand, reason: receipt.original.reason, idempotency_key: receipt.original.idempotency_key };
const actor = receipt.original.actor_id, key = waitlistIntentKey("own", actor);
class MemoryStorage {
  values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
  removeItem(key: string) { this.values.delete(key); }
}
function setup(overrides: Partial<Parameters<typeof createWaitlistIntent>[0]> = {}) {
  const storage = new MemoryStorage(); const reads: string[] = []; let posts = 0, stored: unknown = null;
  const options = { institute: "own", actor, storage, current: () => true,
    get: async (path: string) => { assert.notEqual(storage.getItem(key), null); reads.push(path); return stored; },
    post: async (_path: string, value: WaitlistRequest) => { posts++; assert.deepEqual(value, terms); stored = receipt; return receipt; }, ...overrides };
  return { options, storage: options.storage, reads, posts: () => posts, intent: createWaitlistIntent(options) };
}
test("retains before I/O and independently confirms key and ID before cleanup", async () => {
  const h = setup(); assert.equal(h.intent.state().status, "empty");
  assert.equal((await h.intent.submit(terms)).status, "confirmed");
  assert.equal(h.posts(), 1); assert.equal(h.reads.length, 3);
  assert.match(h.reads[0], /original-by-key/); assert.match(h.reads[1], /original-by-key/);
  assert.match(h.reads[2], /originals\/waitlist_demand_000$/);
  assert.equal(h.intent.state().status, "empty");
});
test("lost acknowledgement survives reload and recovers frozen terms without another POST", async () => {
  let committed: unknown = null, posts = 0;
  const h = setup({ get: async () => committed, post: async () => { posts++; committed = receipt; throw new Error("connection lost"); } });
  await assert.rejects(h.intent.submit(terms), /connection lost/);
  assert.equal(h.intent.state().status, "frozen"); assert.equal(h.intent.canCorrect(), false);
  const reloaded = createWaitlistIntent(h.options);
  assert.equal((await reloaded.submit({ ...terms, reason: "Changed form" })).status, "confirmed");
  assert.equal(posts, 1); assert.equal(reloaded.state().status, "empty");
});
test("valid but mismatching receipts and independent read changes preserve frozen intent", async () => {
  for (const change of ["actor", "reason", "id"]) {
    const altered = structuredClone(receipt);
    if (change === "actor") altered.original.actor_id = "other";
    if (change === "reason") altered.original.reason = "Changed reason";
    if (change === "id") altered.original.id = "different";
    altered.fingerprint = await revenueOriginalFingerprint(altered.original);
    let reads = 0;
    const h = setup({ get: async () => ++reads === 1 ? null : altered, post: async () => receipt });
    await assert.rejects(h.intent.submit(terms));
    assert.equal(h.intent.state().status, "frozen"); assert.equal(h.intent.canCorrect(), false);
  }
});
test("only definitive POST rejection enables fresh-null-key correction", async () => {
  for (const status of [400, 404, 422, 500]) {
    let reads = 0;
    const h = setup({ get: async () => { reads++; return null; }, post: async () => { throw { status }; } });
    await assert.rejects(h.intent.submit(terms));
    assert.equal(h.intent.canCorrect(), status !== 500);
    if (status !== 500) { assert.equal((await h.intent.correct()).status, "correctable"); assert.equal(reads, 2); assert.equal(h.intent.state().status, "empty"); }
    else { await assert.rejects(h.intent.correct()); assert.equal(h.intent.state().status, "frozen"); }
  }
});
test("recovery and confirmation read errors never enable correction", async () => {
  for (const failingRead of [1, 2, 3]) {
    let reads = 0;
    const h = setup({ get: async () => { if (++reads === failingRead) throw { status: 422 }; return reads === 1 ? null : receipt; }, post: async () => receipt });
    await assert.rejects(h.intent.submit(terms)); assert.equal(h.intent.canCorrect(), false);
    await assert.rejects(h.intent.correct()); assert.equal(h.intent.state().status, "frozen");
  }
});
test("correction recovers an intervening retained receipt instead of dropping the intent", async () => {
  let reads = 0;
  const h = setup({ get: async () => ++reads === 1 ? null : receipt, post: async () => { throw { status: 400 }; } });
  await assert.rejects(h.intent.submit(terms));
  assert.equal((await h.intent.correct()).status, "confirmed"); assert.equal(reads, 4);
});
test("invalid storage or failed persistence prevents network writes", async () => {
  for (const value of ["broken", JSON.stringify({ institute: "other", actor, terms }), JSON.stringify({ institute: "own", actor, terms: { ...terms, duration_minutes: 0 } })]) {
    const h = setup(); h.storage.setItem(key, value);
    assert.equal(h.intent.state().status, "invalid"); await assert.rejects(h.intent.submit(terms));
    assert.equal(h.reads.length, 0); assert.equal(h.posts(), 0);
  }
  const storage = new MemoryStorage(); storage.setItem = () => { throw new Error("quota"); };
  const h = setup({ storage }); await assert.rejects(h.intent.submit(terms), /quota/);
  assert.equal(h.reads.length, 0); assert.equal(h.posts(), 0);
});
test("undefined recovery is not absence and changed storage prevents cleanup", async () => {
  const missing = setup({ get: async () => undefined }); await assert.rejects(missing.intent.submit(terms));
  assert.equal(missing.posts(), 0); assert.equal(missing.intent.state().status, "frozen");
  const storage = new MemoryStorage(); let reads = 0;
  const h = setup({ storage, get: async () => { if (++reads === 3) storage.setItem(key, "changed"); return reads === 1 ? null : receipt; }, post: async () => receipt });
  await assert.rejects(h.intent.submit(terms), /Frozen intent changed/); assert.equal(storage.getItem(key), "changed");
});
test("same-scope concurrent instances are busy and stale session suppresses late POST", async () => {
  let release!: (value: unknown) => void, current = true;
  const h = setup({ current: () => current, get: () => new Promise(resolve => { release = resolve; }) });
  const pending = h.intent.submit(terms);
  assert.equal((await createWaitlistIntent(h.options).submit(terms)).status, "busy");
  current = false; release(null); assert.equal((await pending).status, "stale");
  assert.equal(h.posts(), 0); assert.equal(h.intent.state().status, "frozen");
  assert.equal((await h.intent.submit()).status, "stale");
});
test("session change after POST or independent read preserves recovery intent", async () => {
  for (const boundary of ["post", "key", "id"]) {
    let current = true, reads = 0;
    const h = setup({ current: () => current,
      get: async () => { reads++; if (reads === (boundary === "key" ? 2 : boundary === "id" ? 3 : -1)) current = false; return reads === 1 ? null : receipt; },
      post: async () => { if (boundary === "post") current = false; return receipt; } });
    assert.equal((await h.intent.submit(terms)).status, "stale"); assert.equal(h.intent.state().status, "frozen");
    assert.equal(reads, boundary === "post" ? 1 : boundary === "key" ? 2 : 3);
  }
});
test("request matching uses exact instants and keeps expired frozen requests recoverable", () => {
  const offset = structuredClone(terms); offset.availability = [{ start: "2026-10-08T13:00:00+02:00", end: "2026-10-08T14:00:00+02:00" }];
  assert.equal(validWaitlistRequest(offset), true); assert.equal(matchesWaitlistReceipt(receipt, offset, actor), true);
  offset.availability[0].start = "2026-10-08T11:00:00.000001Z";
  assert.equal(matchesWaitlistReceipt(receipt, offset, actor), false);
  for (const invalid of [{ ...terms, duration_minutes: 1.5 }, { ...terms, allowed_employee_ids: ["employee", "employee"] }, { ...terms, constraints_review: "unknown" }, { ...terms, extra: true }]) assert.equal(validWaitlistRequest(invalid), false);
});
