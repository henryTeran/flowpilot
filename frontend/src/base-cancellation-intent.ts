import { revenueOriginalFingerprint as hash } from "./revenue-scenario-utils";
import { validBaseOperationRequest, validBaseDecisionRequest, validBaseExecutionRequest,
  validBaseOperationEnvelope, validBaseDecisionEnvelope, validBaseApprovalState, validBaseExecutionEnvelope,
  type BaseOperationRequest, type BaseDecisionRequest, type BaseExecutionRequest,
  type BaseOperationEnvelope, type BaseDecisionEnvelope, type BaseExecutionEnvelope, type BaseApprovalState } from "./base-cancellation-utils";

type Storage = Pick<globalThis.Storage, "getItem" | "setItem" | "removeItem">;
type Mode = "operation" | "decision" | "execution";
type Terms = BaseOperationRequest | BaseDecisionRequest | BaseExecutionRequest;
type Receipt = BaseOperationEnvelope | BaseDecisionEnvelope | BaseExecutionEnvelope;
type Saved<T> = { institute: string; actor: string; mode: Mode; terms: T };
export type BaseIntentState<T> = { status: "empty" | "invalid" } | { status: "frozen"; value: Saved<T> };
export type BaseIntentResult<R> = { status: "stale" | "busy" | "correctable" } | { status: "confirmed"; receipt: R };
type Options<T> = { institute: string; actor: string; storage: Storage; current: () => boolean;
  get: (path: string) => Promise<unknown>; post: (path: string, terms: T) => Promise<unknown> };
const flights = new WeakMap<Storage, Set<string>>();
const routes = {
  operation: { key: "sensitive-operation-by-key", write: "sensitive-operations", valid: validBaseOperationRequest },
  decision: { key: "approval-by-key", write: "approvals", valid: validBaseDecisionRequest },
  execution: { key: "execution-by-key", write: "executions", valid: validBaseExecutionRequest },
} as const;
export function baseCancellationIntentKey(institute: string, actor: string, mode: Mode) {
  return `flowpilot.base-cancellation.v1:${JSON.stringify([institute, actor, mode])}`;
}
function createIntent<T extends Terms, R extends Receipt>(mode: Mode, options: Options<T>) {
  const { institute, actor, storage, current, get, post } = options;
  if ([institute, actor].some(v => !v || v !== v.trim() || /[\x00-\x1f]/.test(v))
    || Array.from(institute).length > 80 || Array.from(actor).length > 160) throw new Error("Invalid intent scope");
  const key = baseCancellationIntentKey(institute, actor, mode), route = routes[mode];
  const base = `/base/institutes/${encodeURIComponent(institute)}`;
  let canCorrect = false;
  function state(): BaseIntentState<T> {
    try {
      const raw = storage.getItem(key); if (raw === null) return { status: "empty" };
      const saved = JSON.parse(raw);
      return saved && typeof saved === "object" && Object.keys(saved).sort().join(" ") === "actor institute mode terms"
        && saved.institute === institute && saved.actor === actor && saved.mode === mode && route.valid(saved.terms)
        ? { status: "frozen", value: saved } : { status: "invalid" };
    } catch { return { status: "invalid" }; }
  }
  function unchanged(terms: T) {
    const saved = state();
    if (saved.status !== "frozen" || JSON.stringify(saved.value.terms) !== JSON.stringify(terms)) throw new Error("Frozen intent changed");
  }
  const byKey = (terms: T) => `${base}/${route.key}?${new URLSearchParams({ key: terms.idempotency_key })}`;
  async function approvalState(operation: string) {
    const value = await get(`${base}/sensitive-operations/${encodeURIComponent(operation)}/approval-state`);
    if (!await validBaseApprovalState(value, institute)) throw new Error("Approval state requires verification");
    return value as BaseApprovalState;
  }
  async function verify(value: unknown, terms: T): Promise<R> {
    let valid = false;
    if (mode === "operation") valid = await validBaseOperationEnvelope(value, institute);
    else {
      const operation = (terms as BaseDecisionRequest | BaseExecutionRequest).operation_id;
      const history = await approvalState(operation);
      if (mode === "decision") {
        valid = await validBaseDecisionEnvelope(value, institute, history.operation)
          && history.decisions.some(d => d.original.id === (value as BaseDecisionEnvelope).original.id
            && d.fingerprint === (value as BaseDecisionEnvelope).fingerprint);
      } else valid = await validBaseExecutionEnvelope(value, institute, history);
    }
    if (!valid) throw new Error("Receipt requires verification");
    const receipt = value as R, original = receipt.original;
    const request = Object.fromEntries(Object.keys(terms).map(k => [k, (original as unknown as Record<string, unknown>)[k]]));
    if (original.actor_id !== actor || await hash(request) !== await hash(terms)) throw new Error("Receipt differs from frozen terms");
    return receipt;
  }
  async function confirm(value: unknown, terms: T): Promise<BaseIntentResult<R>> {
    const receipt = await verify(value, terms);
    if (!current()) return { status: "stale" };
    const recovered = await verify(await get(byKey(terms)), terms);
    if (!current()) return { status: "stale" };
    if (recovered.original.id !== receipt.original.id || recovered.fingerprint !== receipt.fingerprint) throw new Error("Recovery receipt changed");
    let independent: R;
    if (mode === "decision") {
      const history = await approvalState((terms as BaseDecisionRequest).operation_id);
      independent = await verify(history.decisions.find(d => d.original.id === receipt.original.id), terms);
    } else {
      const path = mode === "operation" ? `/sensitive-operations/${encodeURIComponent(receipt.original.id)}`
        : `/sensitive-operations/${encodeURIComponent((terms as BaseExecutionRequest).operation_id)}/execution`;
      independent = await verify(await get(`${base}${path}`), terms);
    }
    if (!current()) return { status: "stale" };
    if (independent.original.id !== receipt.original.id || independent.fingerprint !== receipt.fingerprint) throw new Error("Independent receipt changed");
    unchanged(terms); storage.removeItem(key);
    if (storage.getItem(key) !== null) throw new Error("Intent cleanup requires verification");
    canCorrect = false; return { status: "confirmed", receipt: independent };
  }
  async function run(action: () => Promise<BaseIntentResult<R>>): Promise<BaseIntentResult<R>> {
    if (!current()) return { status: "stale" };
    let pending = flights.get(storage); if (!pending) { pending = new Set(); flights.set(storage, pending); }
    if (pending.has(key)) return { status: "busy" };
    pending.add(key); try { return await action(); } finally { pending.delete(key); }
  }
  async function submit(newTerms?: T): Promise<BaseIntentResult<R>> {
    return run(async () => {
      let saved = state();
      if (saved.status === "invalid") throw new Error("Unreadable saved intent blocks new writes");
      if (saved.status === "empty") {
        if (!route.valid(newTerms)) throw new Error("An explicit valid request is required");
        const value = { institute, actor, mode, terms: structuredClone(newTerms!) };
        storage.setItem(key, JSON.stringify(value)); saved = state();
        if (saved.status !== "frozen") throw new Error("Intent could not be retained before sending");
        unchanged(value.terms);
      }
      if (saved.status !== "frozen") throw new Error("Missing frozen intent");
      const terms = saved.value.terms; canCorrect = false;
      if (!current()) return { status: "stale" };
      const recovered = await get(byKey(terms));
      if (!current()) return { status: "stale" };
      unchanged(terms);
      if (recovered !== null) return confirm(recovered, terms);
      let created: unknown;
      try { created = await post(`${base}/${route.write}`, structuredClone(terms)); }
      catch (error) {
        if (error && typeof error === "object" && "status" in error && [400, 404, 422].includes(Number(error.status))) canCorrect = true;
        throw error;
      }
      if (!current()) return { status: "stale" };
      return confirm(created, terms);
    });
  }
  async function correct(): Promise<BaseIntentResult<R>> {
    return run(async () => {
      const saved = state();
      if (!canCorrect || saved.status !== "frozen") throw new Error("Correction requires a definitive rejection");
      const terms = saved.value.terms, recovered = await get(byKey(terms));
      if (!current()) return { status: "stale" };
      if (recovered !== null) return confirm(recovered, terms);
      unchanged(terms); storage.removeItem(key);
      if (storage.getItem(key) !== null) throw new Error("Intent cleanup requires verification");
      canCorrect = false; return { status: "correctable" };
    });
  }
  return { state, submit, correct, canCorrect: () => canCorrect };
}
export const createBaseOperationIntent = (options: Options<BaseOperationRequest>) => createIntent<BaseOperationRequest, BaseOperationEnvelope>("operation", options);
export const createBaseDecisionIntent = (options: Options<BaseDecisionRequest>) => createIntent<BaseDecisionRequest, BaseDecisionEnvelope>("decision", options);
export const createBaseExecutionIntent = (options: Options<BaseExecutionRequest>) => createIntent<BaseExecutionRequest, BaseExecutionEnvelope>("execution", options);
