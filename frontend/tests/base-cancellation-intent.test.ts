import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createBaseOperationIntent, createBaseDecisionIntent, createBaseExecutionIntent, baseCancellationIntentKey } from "../src/base-cancellation-intent";
import { revenueOriginalFingerprint as hash } from "../src/revenue-scenario-utils";
const fixture = JSON.parse(readFileSync(new URL("./fixtures/base-cancellation-17i.json", import.meta.url), "utf8"));
class MemoryStorage {
  values = new Map<string, string>();
  getItem(k: string) { return this.values.get(k) ?? null; }
  setItem(k: string, v: string) { this.values.set(k, v); }
  removeItem(k: string) { this.values.delete(k); }
}
const specs = [
  { mode: "operation", create: createBaseOperationIntent, receipt: fixture.pending.operation,
    fields: "capability selection expected_state_fingerprint valid_until reason idempotency_key", write: "sensitive-operations", keyPath: "sensitive-operation-by-key" },
  { mode: "decision", create: createBaseDecisionIntent, receipt: fixture.approved.decisions[0],
    fields: "operation_id operation_fingerprint previous_id previous_fingerprint decision reason idempotency_key", write: "approvals", keyPath: "approval-by-key" },
  { mode: "execution", create: createBaseExecutionIntent, receipt: fixture.execution,
    fields: "operation_id operation_fingerprint approval_id approval_fingerprint reason idempotency_key", write: "executions", keyPath: "execution-by-key" },
] as const;
for (const spec of specs) {
  const receipt = spec.receipt, actor = receipt.original.actor_id;
  const terms: any = Object.fromEntries(spec.fields.split(" ").map(k => [k, receipt.original[k]]));
  const key = baseCancellationIntentKey("own", actor, spec.mode);
  function setup() {
    const storage = new MemoryStorage(); let stored: any = null, posts = 0, active = true;
    const reads: string[] = [];
    const options = { institute: "own", actor, storage, current: () => active,
      get: async (path: string): Promise<unknown> => {
        assert.notEqual(storage.getItem(key), null); reads.push(path);
        if (path.endsWith("/approval-state")) return fixture.approved;
        return stored;
      },
      post: async (path: string, request: any): Promise<unknown> => {
        assert.equal(path, `/base/institutes/own/${spec.write}`); assert.deepEqual(request, terms);
        assert.notEqual(storage.getItem(key), null); posts++; stored = receipt; return receipt;
      } };
    return { storage, options, reads, posts: () => posts, setStored: (v: any) => { stored = v; }, deactivate: () => { active = false; },
      create: () => spec.create({ ...options, get: (path: string) => options.get(path),
        post: (path: string, request: any) => options.post(path, request) } as any) };
  }
  test(`${spec.mode}: retain before I/O, verify key and independent proof, then clear`, async () => {
    const h = setup(), intent = h.create();
    assert.equal((await intent.submit(terms)).status, "confirmed"); assert.equal(h.posts(), 1);
    assert.match(h.reads[0], new RegExp(spec.keyPath)); assert.equal(intent.state().status, "empty");
    assert.ok(h.reads.some(path => spec.mode === "decision" ? path.endsWith("/approval-state")
      : spec.mode === "execution" ? path.endsWith("/execution") : path.endsWith("/sensitive-operations/operation")));
  });
  test(`${spec.mode}: lost acknowledgement survives reload without changing terms or repeating POST`, async () => {
    const h = setup(), post = h.options.post;
    h.options.post = async (path, value) => { await post(path, value); throw new Error("connection lost"); };
    const intent = h.create(); await assert.rejects(intent.submit(terms), /connection lost/);
    assert.equal(intent.state().status, "frozen"); assert.equal(intent.canCorrect(), false);
    // A recovered approval can be historical after revocation; an execution can be historical after expiry.
    h.options.get = async path => path.endsWith("/approval-state")
      ? spec.mode === "decision" ? fixture.revoked : fixture.expired : receipt;
    const reload = h.create();
    assert.equal((await reload.submit({ ...terms, reason: "Changed form must not replace frozen intent" })).status, "confirmed");
    assert.equal(h.posts(), 1); assert.equal(reload.state().status, "empty");
  });
  test(`${spec.mode}: undefined absence and forged matching outer hash block POST and cleanup`, async () => {
    for (const attack of ["undefined", "actor", "terms", "independent"]) {
      const h = setup(), forged = structuredClone(receipt);
      if (attack === "actor") forged.original.actor_id = "forged-actor";
      if (attack === "terms") forged.original.reason = "Different reason";
      forged.fingerprint = await hash(forged.original);
      let keys = 0;
      h.options.get = async path => {
        if (path.endsWith("/approval-state")) return fixture.approved;
        if (attack === "undefined") return undefined;
        if (attack === "independent") {
          if (path.includes(spec.keyPath)) { keys++; return receipt; }
          return { ...receipt, fingerprint: "0".repeat(64) };
        }
        return forged;
      };
      // For decisions the independent source is the full chain, not an envelope detail endpoint.
      if (attack === "independent" && spec.mode === "decision") h.options.get = async path => {
        if (path.includes(spec.keyPath)) { keys++; return receipt; }
        return keys >= 2 ? fixture.pending : fixture.approved;
      };
      const intent = h.create(); await assert.rejects(intent.submit(terms));
      assert.equal(h.posts(), 0); assert.equal(intent.state().status, "frozen"); assert.equal(intent.canCorrect(), false);
    }
  });
  test(`${spec.mode}: definitive rejection permits correction only after fresh literal null`, async () => {
    const h = setup(); h.options.post = async () => { throw { status: 400 }; };
    const intent = h.create(); await assert.rejects(intent.submit(terms)); assert.equal(intent.canCorrect(), true);
    h.options.get = async () => undefined;
    await assert.rejects(intent.correct()); assert.equal(intent.state().status, "frozen");
    h.options.get = async () => null;
    assert.equal((await intent.correct()).status, "correctable"); assert.equal(intent.state().status, "empty");
    await assert.rejects(h.create().correct(), /definitive rejection/);
  });
  test(`${spec.mode}: stale response and concurrent instances preserve frozen intent`, async () => {
    const h = setup(); let release!: (v: unknown) => void;
    h.options.get = async () => new Promise(resolve => { release = resolve; });
    const first = h.create(), pending = first.submit(terms);
    assert.equal((await h.create().submit(terms)).status, "busy");
    h.deactivate(); release(null); assert.equal((await pending).status, "stale");
    assert.equal(h.posts(), 0); assert.equal(first.state().status, "frozen");
  });
  test(`${spec.mode}: invalid persisted scope and unavailable storage prevent any request`, async () => {
    const h = setup(); h.storage.setItem(key, JSON.stringify({ institute: "foreign", actor, mode: spec.mode, terms }));
    await assert.rejects(h.create().submit(terms), /Unreadable/); assert.equal(h.reads.length, 0);
    h.storage.removeItem(key); h.storage.setItem = () => { throw new Error("storage denied"); };
    await assert.rejects(h.create().submit(terms), /storage denied/); assert.equal(h.posts(), 0); assert.equal(h.reads.length, 0);
  });
  test(`${spec.mode}: ambiguous server failure never authorizes discarding the frozen request`, async () => {
    const h = setup(); h.options.post = async () => { throw { status: 500 }; };
    const intent = h.create(); await assert.rejects(intent.submit(terms));
    assert.equal(intent.canCorrect(), false); await assert.rejects(intent.correct(), /definitive rejection/);
    assert.equal(intent.state().status, "frozen");
  });
  test(`${spec.mode}: committed response after scope change cannot publish or clear retained terms`, async () => {
    const h = setup(), post = h.options.post;
    h.options.post = async (path, request) => { const value = await post(path, request); h.deactivate(); return value; };
    const intent = h.create(); assert.equal((await intent.submit(terms)).status, "stale");
    assert.equal(h.posts(), 1); assert.equal(intent.state().status, "frozen");
  });
  test(`${spec.mode}: correction recovers a now-present proof and cleanup failure retains recovery`, async () => {
    const h = setup(); h.options.post = async () => { throw { status: 422 }; };
    const intent = h.create(); await assert.rejects(intent.submit(terms)); h.setStored(receipt);
    h.storage.removeItem = () => { /* simulate a storage implementation that did not remove the value */ };
    await assert.rejects(intent.correct(), /cleanup requires verification/);
    assert.equal(intent.state().status, "frozen");
    h.storage.removeItem = k => { h.storage.values.delete(k); };
    assert.equal((await h.create().submit()).status, "confirmed"); assert.equal(h.posts(), 0);
  });
}
