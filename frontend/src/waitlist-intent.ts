import { validWaitlistRequest, validWaitlistEnvelope, matchesWaitlistReceipt, type WaitlistRequest, type WaitlistEnvelope } from "./waitlist-original-utils";

type Storage = Pick<globalThis.Storage, "getItem" | "setItem" | "removeItem">;
type Saved = { institute: string; actor: string; terms: WaitlistRequest };
export type WaitlistIntentState = { status: "empty" } | { status: "invalid" } | { status: "frozen"; value: Saved };
export type WaitlistIntentResult = { status: "stale" | "busy" | "correctable" } | { status: "confirmed"; receipt: WaitlistEnvelope };
const flights = new WeakMap<Storage, Set<string>>();
export function waitlistIntentKey(institute: string, actor: string) {
  return `flowpilot.waitlist-demand.v1:${JSON.stringify([institute, actor])}`;
}

export function createWaitlistIntent(options: { institute: string; actor: string; storage: Storage; current: () => boolean;
  get: (path: string) => Promise<unknown>; post: (path: string, terms: WaitlistRequest) => Promise<unknown> }) {
  const { institute, actor, storage, current, get, post } = options;
  if (!institute || institute !== institute.trim() || !actor || actor !== actor.trim() || Array.from(actor).length > 160 || /[\x00-\x1f]/.test(actor)) throw new Error("Invalid intent scope");
  const key = waitlistIntentKey(institute, actor), base = `/waitlist/institutes/${encodeURIComponent(institute)}`;
  let canCorrect = false;
  function state(): WaitlistIntentState {
    try {
      const raw = storage.getItem(key); if (raw === null) return { status: "empty" };
      const saved = JSON.parse(raw);
      return saved && typeof saved === "object" && Object.keys(saved).sort().join(" ") === "actor institute terms"
        && saved.institute === institute && saved.actor === actor && validWaitlistRequest(saved.terms)
        ? { status: "frozen", value: saved } : { status: "invalid" };
    } catch { return { status: "invalid" }; }
  }
  function unchanged(terms: WaitlistRequest) {
    const saved = state();
    if (saved.status !== "frozen" || JSON.stringify(saved.value.terms) !== JSON.stringify(terms)) throw new Error("Frozen intent changed");
  }
  async function verify(value: unknown, terms: WaitlistRequest): Promise<WaitlistEnvelope> {
    if (!await validWaitlistEnvelope(value, institute) || !matchesWaitlistReceipt(value as WaitlistEnvelope, terms, actor)) throw new Error("Receipt requires verification");
    return value as WaitlistEnvelope;
  }
  async function confirm(value: unknown, terms: WaitlistRequest): Promise<WaitlistIntentResult> {
    const receipt = await verify(value, terms);
    if (!current()) return { status: "stale" };
    const byKey = await verify(await get(`${base}/original-by-key?${new URLSearchParams({ key: terms.idempotency_key })}`), terms);
    if (!current()) return { status: "stale" };
    if (byKey.original.id !== receipt.original.id || byKey.fingerprint !== receipt.fingerprint) throw new Error("Recovery receipt changed");
    const byId = await verify(await get(`${base}/originals/${encodeURIComponent(receipt.original.id)}`), terms);
    if (!current()) return { status: "stale" };
    if (byId.original.id !== receipt.original.id || byId.fingerprint !== receipt.fingerprint) throw new Error("Independent receipt changed");
    unchanged(terms); storage.removeItem(key);
    if (storage.getItem(key) !== null) throw new Error("Intent cleanup requires verification");
    canCorrect = false;
    return { status: "confirmed", receipt: byId };
  }
  async function run(operation: () => Promise<WaitlistIntentResult>): Promise<WaitlistIntentResult> {
    if (!current()) return { status: "stale" };
    let pending = flights.get(storage); if (!pending) { pending = new Set(); flights.set(storage, pending); }
    if (pending.has(key)) return { status: "busy" };
    pending.add(key);
    try { return await operation(); } finally { pending.delete(key); }
  }
  async function submit(newTerms?: WaitlistRequest): Promise<WaitlistIntentResult> {
    return run(async () => {
      let saved = state();
      if (saved.status === "invalid") throw new Error("Unreadable saved intent blocks new writes");
      if (saved.status === "empty") {
        if (!validWaitlistRequest(newTerms)) throw new Error("An explicit valid declaration is required");
        const value: Saved = { institute, actor, terms: structuredClone(newTerms) };
        storage.setItem(key, JSON.stringify(value)); saved = state();
        if (saved.status !== "frozen") throw new Error("Intent could not be retained before sending");
        unchanged(value.terms);
      }
      const terms = saved.value.terms;
      canCorrect = false;
      if (!current()) return { status: "stale" };
      const recovered = await get(`${base}/original-by-key?${new URLSearchParams({ key: terms.idempotency_key })}`);
      if (!current()) return { status: "stale" };
      unchanged(terms);
      if (recovered !== null) return confirm(recovered, terms);
      let created: unknown;
      try {
        created = await post(`${base}/originals`, structuredClone(terms));
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
  async function correct(): Promise<WaitlistIntentResult> {
    return run(async () => {
      const saved = state();
      if (!canCorrect || saved.status !== "frozen") throw new Error("Correction requires a definitive rejection");
      const terms = saved.value.terms, recovered = await get(`${base}/original-by-key?${new URLSearchParams({ key: terms.idempotency_key })}`);
      if (!current()) return { status: "stale" };
      if (recovered !== null) return confirm(recovered, terms);
      unchanged(terms); storage.removeItem(key);
      if (storage.getItem(key) !== null) throw new Error("Intent cleanup requires verification");
      canCorrect = false; return { status: "correctable" };
    });
  }
  return { state, submit, correct, canCorrect: () => canCorrect };
}
