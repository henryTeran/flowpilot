import test from "node:test";
import assert from "node:assert/strict";
import fixture from "./fixtures/waitlist-lifecycle-15j.json";
import { createWaitlistLifecycleIntent, validWaitlistLifecycleSelection, waitlistLifecycleIntentKey, type WaitlistLifecycleSelection } from "../src/waitlist-lifecycle-intent";
import type { WaitlistLifecycleState } from "../src/waitlist-lifecycle-utils";
import { revenueOriginalFingerprint } from "../src/revenue-scenario-utils";
const actor = "manager-É", key = waitlistLifecycleIntentKey("own", actor);
function selection(state: typeof fixture.activated, previous: WaitlistLifecycleState | null): WaitlistLifecycleSelection {
  const { id, institute_id, actor_id, created_at, activation_source, effect, ...request } = state.events[state.events.length-1].original;
  return structuredClone({ request, root: state.root, target: state.current_demand, previous_state: previous }) as WaitlistLifecycleSelection;
}
const activate = selection(fixture.activated, null), revise = selection(fixture.revised, fixture.activated as WaitlistLifecycleState), cancel = selection(fixture.cancelled, fixture.revised as WaitlistLifecycleState);
class MemoryStorage { values = new Map<string, string>(); getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); } removeItem(key: string) { this.values.delete(key); } }
function setup(terms = activate, finalState: WaitlistLifecycleState = fixture.activated as WaitlistLifecycleState,
  overrides: Partial<Parameters<typeof createWaitlistLifecycleIntent>[0]> = {}) {
  const storage = new MemoryStorage(), receipt = finalState.events[terms.previous_state?.events.length || 0]; let committed: unknown = null, posts = 0;
  const reads: string[] = [];
  const options = { institute: "own", actor, storage, current: () => true,
    get: async (path: string) => { reads.push(path); assert.notEqual(storage.getItem(key), null); return path.includes("/states/") ? finalState : committed; },
    post: async (_path: string, request: unknown) => { posts++; assert.deepEqual(JSON.parse(storage.getItem(key)!).terms, terms); assert.deepEqual(request, terms.request); committed = receipt; return receipt; }, ...overrides };
  return { options, storage: options.storage, reads, posts: () => posts, intent: createWaitlistLifecycleIntent(options), receipt };
}
test("verified selection pins initial activation, revision target and exact active predecessor", async () => {
  for (const terms of [activate, revise, cancel]) assert.equal(await validWaitlistLifecycleSelection(terms, "own"), true);
  for (const terms of [{ ...activate, previous_state: fixture.activated }, { ...revise, target: fixture.activated.root }, { ...cancel, target: fixture.activated.root },
    { ...revise, previous_state: fixture.cancelled }, { ...revise, request: { ...revise.request, previous_fingerprint: "a".repeat(64) } }]) assert.equal(await validWaitlistLifecycleSelection(terms, "own"), false);
});
test("each action persists its complete decision before POST and verifies key, ID and causal chain", async () => {
  for (const [terms, state] of [[activate, fixture.activated], [revise, fixture.revised], [cancel, fixture.cancelled]] as const) {
    const h = setup(terms, state as WaitlistLifecycleState); const result = await h.intent.submit(terms);
    assert.equal(result.status, "confirmed"); assert.equal(h.posts(), 1); assert.equal(h.reads.length, 4);
    assert.match(h.reads[0], /original-by-key/); assert.match(h.reads[1], /original-by-key/); assert.match(h.reads[2], /originals\/event_/); assert.match(h.reads[3], /states\/waitlist_demand_000$/);
    assert.equal(h.intent.state().status, "empty");
  }
});
test("lost acknowledgement recovers frozen revision after reload and a later cancellation without another POST", async () => {
  let committed = false, posts = 0;
  const h = setup(revise, fixture.cancelled as WaitlistLifecycleState, { get: async path => path.includes("/states/") ? fixture.cancelled : committed ? fixture.revised.events[1] : null,
    post: async () => { committed = true; posts++; throw new Error("lost acknowledgement"); } });
  await assert.rejects(h.intent.submit(revise)); assert.equal(h.intent.canCorrect(), false);
  const reloaded = createWaitlistLifecycleIntent(h.options); const result = await reloaded.submit(cancel);
  assert.equal(result.status, "confirmed"); if (result.status === "confirmed") { assert.equal(result.receipt.original.action, "revise"); assert.equal(result.state.state, "cancelled"); }
  assert.equal(posts, 1); assert.equal(reloaded.state().status, "empty");
});
test("valid rehashed receipt substitutions and missing causal proof preserve frozen decision", async () => {
  for (const change of ["actor", "reason", "source", "id", "chain"]) {
    const altered = structuredClone(fixture.revised.events[1]);
    if (change === "actor") altered.original.actor_id = "other";
    if (change === "reason") altered.original.reason = "Another reason";
    if (change === "source") altered.original.activation_source!.duration_minutes = 31;
    if (change === "id") altered.original.id = "different";
    altered.fingerprint = await revenueOriginalFingerprint(altered.original); let reads = 0;
    const h = setup(revise, fixture.revised as WaitlistLifecycleState, { get: async path => {
      if (path.includes("/states/")) return fixture.activated;
      return ++reads === 1 ? null : change === "chain" ? fixture.revised.events[1] : altered;
    }, post: async () => fixture.revised.events[1] });
    await assert.rejects(h.intent.submit(revise)); assert.equal(h.intent.state().status, "frozen"); assert.equal(h.intent.canCorrect(), false);
  }
});
test("only definitive POST rejection permits correction after a fresh null key read", async () => {
  for (const status of [400, 404, 422, 500]) {
    let reads = 0; const h = setup(activate, fixture.activated as WaitlistLifecycleState,
      { get: async () => { reads++; return null; }, post: async () => { throw { status }; } });
    await assert.rejects(h.intent.submit(activate)); assert.equal(h.intent.canCorrect(), status !== 500);
    if (status !== 500) { assert.equal((await h.intent.correct()).status, "correctable"); assert.equal(reads, 2); assert.equal(h.intent.state().status, "empty"); }
    else { await assert.rejects(h.intent.correct()); assert.equal(h.intent.state().status, "frozen"); }
  }
});
test("key, independent ID and state read failures never offer correction", async () => {
  for (const failure of [1, 2, 3, 4]) {
    let reads = 0; const h = setup(activate, fixture.activated as WaitlistLifecycleState,
      { get: async () => { if (++reads === failure) throw { status: 422 }; return reads === 1 ? null : fixture.activated.events[0]; }, post: async () => fixture.activated.events[0] });
    await assert.rejects(h.intent.submit(activate)); assert.equal(h.intent.canCorrect(), false); await assert.rejects(h.intent.correct()); assert.equal(h.intent.state().status, "frozen");
  }
});
test("correction recovers an intervening committed action instead of releasing its key", async () => {
  let reads = 0; const h = setup(activate, fixture.activated as WaitlistLifecycleState,
    { get: async path => path.includes("/states/") ? fixture.activated : ++reads === 1 ? null : fixture.activated.events[0], post: async () => { throw { status: 400 }; } });
  await assert.rejects(h.intent.submit(activate)); assert.equal((await h.intent.correct()).status, "confirmed"); assert.equal(h.intent.state().status, "empty");
});
test("invalid shapes, corrupted saved proofs and persistence failure prevent all network I/O", async () => {
  for (const raw of ["broken", JSON.stringify({ institute: "other", actor, terms: activate }), JSON.stringify({ institute: "own", actor, terms: { ...activate, target: { original: null, fingerprint: "a".repeat(64) } } })]) {
    const h = setup(); h.storage.setItem(key, raw); assert.equal(h.intent.state().status, "invalid"); await assert.rejects(h.intent.submit(activate)); assert.equal(h.posts(), 0); assert.equal(h.reads.length, 0);
  }
  const h = setup(), altered = structuredClone(activate); altered.root.original.reason = "Changed valid reason";
  h.storage.setItem(key, JSON.stringify({ institute: "own", actor, terms: altered })); await assert.rejects(h.intent.submit()); assert.equal(h.reads.length, 0);
  const storage = new MemoryStorage(); storage.setItem = () => { throw new Error("quota"); }; const failed = setup(activate, fixture.activated as WaitlistLifecycleState, { storage });
  await assert.rejects(failed.intent.submit(activate), /quota/); assert.equal(failed.reads.length, 0); assert.equal(failed.posts(), 0);
});
test("undefined recovery cannot POST; changed frozen storage cannot be cleared", async () => {
  const absent = setup(activate, fixture.activated as WaitlistLifecycleState, { get: async () => undefined }); await assert.rejects(absent.intent.submit(activate)); assert.equal(absent.posts(), 0);
  const storage = new MemoryStorage(); let reads = 0;
  const h = setup(activate, fixture.activated as WaitlistLifecycleState, { storage, get: async path => {
    if (path.includes("/states/")) { storage.setItem(key, "changed"); return fixture.activated; } return ++reads === 1 ? null : fixture.activated.events[0]; }, post: async () => fixture.activated.events[0] });
  await assert.rejects(h.intent.submit(activate), /Frozen lifecycle intent changed/); assert.equal(storage.getItem(key), "changed");
});
test("shared flights and session invalidation at each I/O boundary preserve recovery without late writes", async () => {
  let release!: (value: unknown) => void, current = true;
  const h = setup(activate, fixture.activated as WaitlistLifecycleState, { current: () => current, get: () => new Promise(r => { release = r; }) });
  const pending = h.intent.submit(activate);
  assert.equal((await createWaitlistLifecycleIntent(h.options).submit(activate)).status, "busy");
  while (!release) await new Promise(r => setTimeout(r, 1)); current = false; release(null);
  assert.equal((await pending).status, "stale"); assert.equal(h.posts(), 0); assert.equal(h.intent.state().status, "frozen");
  for (const boundary of ["post", "key", "id", "state"]) {
    let current = true, reads = 0;
    const h = setup(activate, fixture.activated as WaitlistLifecycleState, { current: () => current,
      get: async path => { reads++; if (reads === ({ key: 2, id: 3, state: 4 } as Record<string, number>)[boundary]) current = false; return path.includes("/states/") ? fixture.activated : reads === 1 ? null : fixture.activated.events[0]; },
      post: async () => { if (boundary === "post") current = false; return fixture.activated.events[0]; } });
    assert.equal((await h.intent.submit(activate)).status, "stale"); assert.equal(h.intent.state().status, "frozen");
    assert.equal(reads, ({ post: 1, key: 2, id: 3, state: 4 } as Record<string, number>)[boundary]);
  }
});
