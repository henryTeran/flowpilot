import { validOptimizerPolicyRequest, validOptimizerPolicyEnvelope, matchesOptimizerPolicyReceipt, type OptimizerPolicyRequest, type OptimizerPolicyEnvelope } from "./optimizer-policy-utils";

type Storage = Pick<globalThis.Storage, "getItem" | "setItem" | "removeItem">;
type Saved = { institute: string; actor: string; terms: OptimizerPolicyRequest };
export type OptimizerPolicyIntentState = { status: "empty" } | { status: "invalid" } | { status: "frozen"; value: Saved };
export type OptimizerPolicyIntentResult = { status: "stale" | "busy" | "correctable" } | { status: "confirmed"; receipt: OptimizerPolicyEnvelope };
const flights = new WeakMap<Storage, Set<string>>();
export function optimizerPolicyIntentKey(institute: string, actor: string) {
  return `flowpilot.optimizer-policy.v1:${JSON.stringify([institute, actor])}`;
}

export function createOptimizerPolicyIntent(options: { institute: string; actor: string; storage: Storage; current: () => boolean;
  get: (path: string) => Promise<unknown>; post: (path: string, terms: OptimizerPolicyRequest) => Promise<unknown> }) {
  const { institute, actor, storage, current, get, post } = options;
  if (!institute || institute !== institute.trim() || !actor || actor !== actor.trim() || Array.from(actor).length > 160 || /[\x00-\x1f]/.test(actor)) throw new Error("Invalid intent scope");
  const key = optimizerPolicyIntentKey(institute, actor), base = `/optimizer/institutes/${encodeURIComponent(institute)}`;
  let canCorrect = false;
  function state(): OptimizerPolicyIntentState {
    try {
      const raw = storage.getItem(key); if (raw === null) return { status: "empty" };
      const saved = JSON.parse(raw);
      return saved && typeof saved === "object" && Object.keys(saved).sort().join(" ") === "actor institute terms"
        && saved.institute === institute && saved.actor === actor && validOptimizerPolicyRequest(saved.terms)
        ? { status: "frozen", value: saved } : { status: "invalid" };
    } catch { return { status: "invalid" }; }
  }
  function unchanged(terms: OptimizerPolicyRequest) {
    const saved = state();
    if (saved.status !== "frozen" || JSON.stringify(saved.value.terms) !== JSON.stringify(terms)) throw new Error("Frozen intent changed");
  }
  async function verify(value: unknown, terms: OptimizerPolicyRequest): Promise<OptimizerPolicyEnvelope> {
    if (!await validOptimizerPolicyEnvelope(value, institute) || !matchesOptimizerPolicyReceipt(value as OptimizerPolicyEnvelope, terms, actor)) throw new Error("Receipt requires verification");
    return value as OptimizerPolicyEnvelope;
  }
  async function confirm(value: unknown, terms: OptimizerPolicyRequest): Promise<OptimizerPolicyIntentResult> {
    const receipt = await verify(value, terms);
    if (!current()) return { status: "stale" };
    const byKey = await verify(await get(`${base}/policy-original-by-key?${new URLSearchParams({ key: terms.idempotency_key })}`), terms);
    if (!current()) return { status: "stale" };
    if (byKey.original.id !== receipt.original.id || byKey.fingerprint !== receipt.fingerprint) throw new Error("Recovery receipt changed");
    const byId = await verify(await get(`${base}/policy-originals/${encodeURIComponent(receipt.original.id)}`), terms);
    if (!current()) return { status: "stale" };
    if (byId.original.id !== receipt.original.id || byId.fingerprint !== receipt.fingerprint) throw new Error("Independent receipt changed");
    unchanged(terms); storage.removeItem(key);
    if (storage.getItem(key) !== null) throw new Error("Intent cleanup requires verification");
    canCorrect = false;
    return { status: "confirmed", receipt: byId };
  }
  async function run(operation: () => Promise<OptimizerPolicyIntentResult>): Promise<OptimizerPolicyIntentResult> {
    if (!current()) return { status: "stale" };
    let pending = flights.get(storage); if (!pending) { pending = new Set(); flights.set(storage, pending); }
    if (pending.has(key)) return { status: "busy" };
    pending.add(key);
    try { return await operation(); } finally { pending.delete(key); }
  }
  async function submit(newTerms?: OptimizerPolicyRequest): Promise<OptimizerPolicyIntentResult> {
    return run(async () => {
      let saved = state();
      if (saved.status === "invalid") throw new Error("Unreadable saved intent blocks new writes");
      if (saved.status === "empty") {
        if (!validOptimizerPolicyRequest(newTerms)) throw new Error("An explicit valid declaration is required");
        const value: Saved = { institute, actor, terms: structuredClone(newTerms) };
        storage.setItem(key, JSON.stringify(value)); saved = state();
        if (saved.status !== "frozen") throw new Error("Intent could not be retained before sending");
        unchanged(value.terms);
      }
      const terms = saved.value.terms;
      canCorrect = false;
      if (!current()) return { status: "stale" };
      const recovered = await get(`${base}/policy-original-by-key?${new URLSearchParams({ key: terms.idempotency_key })}`);
      if (!current()) return { status: "stale" };
      unchanged(terms);
      if (recovered !== null) return confirm(recovered, terms);
      let created: unknown;
      try {
        created = await post(`${base}/policy-originals`, structuredClone(terms));
      } catch (error) {
        // Only definitive POST rejection can offer correction. Read/verification
        // failures and unknown acknowledgement keep the original frozen intent.
        if (error && typeof error === "object" && "status" in error && [400, 404, 422].includes(Number(error.status))) canCorrect = true;
        throw error;
      }
      if (!current()) return { status: "stale" };
      return confirm(created, terms);
    });
  }
  async function correct(): Promise<OptimizerPolicyIntentResult> {
    return run(async () => {
      const saved = state();
      if (!canCorrect || saved.status !== "frozen") throw new Error("Correction requires a definitive rejection");
      const terms = saved.value.terms, recovered = await get(`${base}/policy-original-by-key?${new URLSearchParams({ key: terms.idempotency_key })}`);
      if (!current()) return { status: "stale" };
      if (recovered !== null) return confirm(recovered, terms);
      unchanged(terms); storage.removeItem(key);
      if (storage.getItem(key) !== null) throw new Error("Intent cleanup requires verification");
      canCorrect = false; return { status: "correctable" };
    });
  }
  return { state, submit, correct, canCorrect: () => canCorrect };
}
