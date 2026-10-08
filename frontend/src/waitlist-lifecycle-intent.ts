import { certificationInstant as instant } from "./certification-utils";
import { validWaitlistEnvelope, validWaitlistOriginalShape, type WaitlistEnvelope } from "./waitlist-original-utils";
import { validWaitlistLifecycleRequest, validWaitlistLifecycleEnvelope, validWaitlistLifecycleState, waitlistLifecycleBindsTarget,
  type WaitlistLifecycleRequest, type WaitlistLifecycleEnvelope, type WaitlistLifecycleState } from "./waitlist-lifecycle-utils";

export type WaitlistLifecycleSelection = { request: WaitlistLifecycleRequest; root: WaitlistEnvelope; target: WaitlistEnvelope; previous_state: WaitlistLifecycleState | null };
type Storage = Pick<globalThis.Storage, "getItem" | "setItem" | "removeItem">;
type Saved = { institute: string; actor: string; terms: WaitlistLifecycleSelection };
export type WaitlistLifecycleIntentState = { status: "empty" } | { status: "invalid" } | { status: "frozen"; value: Saved };
type Result = { status: "stale" | "busy" | "correctable" } | { status: "confirmed"; receipt: WaitlistLifecycleEnvelope; state: WaitlistLifecycleState };
const flights = new WeakMap<Storage, Set<string>>();
const keys = (v: unknown, names: string): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v)
  && Object.keys(v).sort().join(" ") === names.split(" ").sort().join(" ");
const same = (a: { original: { id: string }; fingerprint: string }, b: { original: { id: string }; fingerprint: string }) => a.original.id === b.original.id && a.fingerprint === b.fingerprint;
function selectionShape(v: unknown, institute: string): v is WaitlistLifecycleSelection {
  return keys(v, "request root target previous_state") && validWaitlistLifecycleRequest(v.request)
    && keys(v.root, "original fingerprint") && keys(v.target, "original fingerprint")
    && validWaitlistOriginalShape(v.root.original, institute) && validWaitlistOriginalShape(v.target.original, institute)
    && typeof v.root.fingerprint === "string" && /^[0-9a-f]{64}$/.test(v.root.fingerprint)
    && typeof v.target.fingerprint === "string" && /^[0-9a-f]{64}$/.test(v.target.fingerprint)
    && (v.previous_state === null || keys(v.previous_state, "root current_demand state events"));
}
export async function validWaitlistLifecycleSelection(v: unknown, institute: string): Promise<boolean> {
  if (!selectionShape(v, institute) || !await validWaitlistEnvelope(v.root, institute) || !await validWaitlistEnvelope(v.target, institute)) return false;
  const r = v.request;
  if (r.root_id !== v.root.original.id || r.root_fingerprint !== v.root.fingerprint || r.target_id !== v.target.original.id || r.target_fingerprint !== v.target.fingerprint
    || v.root.original.demand.customer_id !== v.target.original.demand.customer_id) return false;
  if (r.action === "activate") return v.previous_state === null && same(v.root, v.target);
  const state = v.previous_state;
  if (!state || !await validWaitlistLifecycleState(state, institute) || state.state !== "active" || !same(state.root, v.root)) return false;
  const previous = state.events[state.events.length-1];
  return r.previous_id === previous.original.id && r.previous_fingerprint === previous.fingerprint
    && (r.action === "cancel" ? same(v.target, state.current_demand) : v.target.original.id !== state.current_demand.original.id);
}
export function waitlistLifecycleIntentKey(institute: string, actor: string) { return `flowpilot.waitlist-lifecycle.v1:${JSON.stringify([institute, actor])}`; }
export function createWaitlistLifecycleIntent(options: { institute: string; actor: string; storage: Storage; current: () => boolean;
  get: (path: string) => Promise<unknown>; post: (path: string, request: WaitlistLifecycleRequest) => Promise<unknown> }) {
  const { institute, actor, storage, current, get, post } = options;
  if (!institute || institute !== institute.trim() || !actor || actor !== actor.trim() || Array.from(actor).length > 160 || /[\x00-\x1f]/.test(actor)) throw new Error("Invalid intent scope");
  const key = waitlistLifecycleIntentKey(institute, actor), base = `/waitlist/institutes/${encodeURIComponent(institute)}/lifecycle`;
  let canCorrect = false;
  function state(): WaitlistLifecycleIntentState {
    try { const raw = storage.getItem(key); if (raw === null) return { status: "empty" }; const saved = JSON.parse(raw);
      return keys(saved, "institute actor terms") && saved.institute === institute && saved.actor === actor && selectionShape(saved.terms, institute)
        ? { status: "frozen", value: saved as Saved } : { status: "invalid" };
    } catch { return { status: "invalid" }; }
  }
  function unchanged(terms: WaitlistLifecycleSelection) { const saved = state();
    if (saved.status !== "frozen" || JSON.stringify(saved.value.terms) !== JSON.stringify(terms)) throw new Error("Frozen lifecycle intent changed"); }
  const byKey = (terms: WaitlistLifecycleSelection) => `${base}/original-by-key?${new URLSearchParams({ key: terms.request.idempotency_key })}`;
  async function verify(value: unknown, terms: WaitlistLifecycleSelection): Promise<WaitlistLifecycleEnvelope> {
    if (!await validWaitlistLifecycleEnvelope(value, institute)) throw new Error("Lifecycle receipt requires verification");
    const envelope = value as WaitlistLifecycleEnvelope, event = envelope.original;
    if (event.actor_id !== actor || Object.entries(terms.request).some(([key, value]) => event[key as keyof typeof event] !== value)
      || !waitlistLifecycleBindsTarget(event, terms.target) || instant(event.created_at)! < instant(terms.root.original.created_at)!
      || terms.previous_state && instant(event.created_at)! < instant(terms.previous_state.events[terms.previous_state.events.length-1].original.created_at)!) throw new Error("Lifecycle receipt differs from frozen decision");
    return envelope;
  }
  async function confirm(value: unknown, terms: WaitlistLifecycleSelection): Promise<Result> {
    const receipt = await verify(value, terms); if (!current()) return { status: "stale" };
    const recovered = await verify(await get(byKey(terms)), terms); if (!current()) return { status: "stale" };
    if (!same(receipt, recovered)) throw new Error("Lifecycle recovery receipt changed");
    const independent = await verify(await get(`${base}/originals/${encodeURIComponent(receipt.original.id)}`), terms); if (!current()) return { status: "stale" };
    if (!same(receipt, independent)) throw new Error("Independent lifecycle receipt changed");
    const valueState = await get(`${base}/states/${encodeURIComponent(terms.request.root_id)}`);
    if (!current()) return { status: "stale" };
    if (!await validWaitlistLifecycleState(valueState, institute)) throw new Error("Retained lifecycle chain requires verification");
    const finalState = valueState as WaitlistLifecycleState, prefix = terms.previous_state?.events || [];
    if (!same(finalState.root, terms.root) || finalState.events.length <= prefix.length || !same(finalState.events[prefix.length], receipt)
      || prefix.some((event, n) => !same(event, finalState.events[n]))) throw new Error("Receipt missing from retained causal chain");
    // Later authorized transitions may already exist. Confirm the retained action
    // at its causal position without pretending it is still the latest state.
    if (!current()) return { status: "stale" };
    unchanged(terms); storage.removeItem(key); if (storage.getItem(key) !== null) throw new Error("Lifecycle intent cleanup requires verification");
    canCorrect = false; return { status: "confirmed", receipt: independent, state: finalState };
  }
  async function run(operation: () => Promise<Result>): Promise<Result> {
    if (!current()) return { status: "stale" };
    let pending = flights.get(storage); if (!pending) { pending = new Set(); flights.set(storage, pending); }
    if (pending.has(key)) return { status: "busy" }; pending.add(key);
    try { return await operation(); } finally { pending.delete(key); }
  }
  async function submit(newTerms?: WaitlistLifecycleSelection): Promise<Result> {
    return run(async () => {
      canCorrect = false; let saved = state();
      if (saved.status === "invalid") throw new Error("Unreadable lifecycle intent blocks writes");
      if (saved.status === "empty") {
        const terms = structuredClone(newTerms);
        if (!await validWaitlistLifecycleSelection(terms, institute)) throw new Error("Explicit verified lifecycle selection required");
        if (!current()) return { status: "stale" };
        if (state().status !== "empty") throw new Error("Lifecycle intent already retained");
        storage.setItem(key, JSON.stringify({ institute, actor, terms })); saved = state();
        if (saved.status !== "frozen") throw new Error("Lifecycle decision could not be retained"); unchanged(terms!);
      }
      const terms = saved.value.terms;
      if (!await validWaitlistLifecycleSelection(terms, institute)) throw new Error("Saved lifecycle proofs require verification");
      if (!current()) return { status: "stale" }; unchanged(terms);
      const recovered = await get(byKey(terms)); if (!current()) return { status: "stale" }; unchanged(terms);
      if (recovered !== null) return confirm(recovered, terms);
      let created: unknown;
      try { created = await post(`${base}/originals`, structuredClone(terms.request)); }
      catch (error) { if (error && typeof error === "object" && "status" in error && [400, 404, 422].includes(Number(error.status))) canCorrect = true; throw error; }
      if (!current()) return { status: "stale" }; return confirm(created, terms);
    });
  }
  async function correct(): Promise<Result> {
    return run(async () => {
      const saved = state(); if (!canCorrect || saved.status !== "frozen" || !await validWaitlistLifecycleSelection(saved.value.terms, institute)) throw new Error("Correction requires verified rejected decision");
      if (!current()) return { status: "stale" }; const terms = saved.value.terms, recovered = await get(byKey(terms));
      if (!current()) return { status: "stale" }; if (recovered !== null) return confirm(recovered, terms);
      unchanged(terms); storage.removeItem(key); if (storage.getItem(key) !== null) throw new Error("Lifecycle cleanup requires verification");
      canCorrect = false; return { status: "correctable" };
    });
  }
  return { state, submit, correct, canCorrect: () => canCorrect };
}
