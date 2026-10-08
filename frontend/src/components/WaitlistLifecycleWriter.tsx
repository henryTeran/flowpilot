import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validWaitlistEnvelope, type WaitlistEnvelope } from "../waitlist-original-utils";
import { validWaitlistLifecycleState, type WaitlistLifecycleState, type WaitlistLifecycleEnvelope, type WaitlistLifecycleRequest } from "../waitlist-lifecycle-utils";
import { createWaitlistLifecycleIntent, type WaitlistLifecycleSelection } from "../waitlist-lifecycle-intent";

export type WaitlistLifecycleChoice = { kind: "root" | "target"; envelope: WaitlistEnvelope };
type Props = { institute: string; timezone?: string; choice?: WaitlistLifecycleChoice;
  onContext?: (state?: WaitlistLifecycleState) => void; onRetained?: () => void };
type Review = { root: WaitlistEnvelope; state: WaitlistLifecycleState | null; target?: WaitlistEnvelope };
const storage = { getItem: (key: string) => sessionStorage.getItem(key), setItem: (key: string, value: string) => sessionStorage.setItem(key, value), removeItem: (key: string) => sessionStorage.removeItem(key) };
const same = (a: WaitlistEnvelope, b: WaitlistEnvelope) => a.original.id === b.original.id && a.fingerprint === b.fingerprint;
export function WaitlistLifecycleWriter(props: Props) {
  if (!props.institute || !getOperatorSubject() || getOperatorRole() !== "responsable_institut") return null;
  return <Writer key={JSON.stringify([props.institute, props.timezone, getAccessToken()])} {...props} />;
}
function Writer({ institute, timezone, choice, onContext, onRetained }: Props) {
  const actor = getOperatorSubject()!, token = getAccessToken(), mounted = useRef(false), pending = useRef(false), sequence = useRef(0), panel = useRef<HTMLElement | null>(null);
  const base = `/waitlist/institutes/${encodeURIComponent(institute)}`;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current++; }; }, []);
  const current = () => mounted.current && token === getAccessToken() && actor === getOperatorSubject() && getOperatorRole() === "responsable_institut";
  const [driver] = useState(() => createWaitlistLifecycleIntent({ institute, actor, storage, current, get: path => apiGet(path), post: (path, request) => apiPost(path, request) }));
  const [saved, setSaved] = useState(() => driver.state()), [review, setReview] = useState<Review>(), reviewRef = useRef<Review | undefined>(undefined);
  const [reason, setReason] = useState(""), [receipt, setReceipt] = useState<WaitlistLifecycleEnvelope>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  function publish(value?: Review) { reviewRef.current = value; setReview(value); onContext?.(value?.state || undefined); }
  async function original(envelope: WaitlistEnvelope, fresh: () => boolean) {
    if (!await validWaitlistEnvelope(envelope, institute) || !fresh()) throw new Error("Invalid selected declaration");
    const value = await apiGet<WaitlistEnvelope>(`${base}/originals/${encodeURIComponent(envelope.original.id)}`);
    if (!await validWaitlistEnvelope(value, institute) || !same(value, envelope)) throw new Error("Selected original changed");
    return value;
  }
  async function state(root: WaitlistEnvelope, fresh: () => boolean, allowAbsent = false) {
    if (!fresh()) throw new Error("Obsolete selection");
    try {
      const value = await apiGet<WaitlistLifecycleState>(`${base}/lifecycle/states/${encodeURIComponent(root.original.id)}`);
      if (!await validWaitlistLifecycleState(value, institute) || !same(value.root, root)) throw new Error("Selected chain changed");
      return value;
    } catch (e) { if (allowAbsent && e instanceof ApiError && e.status === 404) return null; throw e; }
  }
  useEffect(() => {
    if (!choice || !current()) return;
    panel.current?.focus({ preventScroll: true }); panel.current?.scrollIntoView?.({ block: "start" });
    if (pending.current || driver.state().status !== "empty") return;
    const selected = structuredClone(choice), previous = reviewRef.current, request = ++sequence.current;
    const fresh = () => current() && request === sequence.current && driver.state().status === "empty";
    setBusy(true); setError(undefined); setReceipt(undefined); setReason(""); publish(undefined);
    void (async () => {
      try {
        if (selected.kind === "root") {
          const root = await original(selected.envelope, fresh); if (!fresh()) return;
          const value = await state(root, fresh, true); if (fresh()) publish({ root, state: value });
        } else {
          if (!previous?.state || previous.state.state !== "active") throw new Error("Select an active root first");
          const target = await original(selected.envelope, fresh); if (!fresh()) return;
          const value = await state(previous.root, fresh);
          if (!value || value.state !== "active" || target.original.id === value.current_demand.original.id || target.original.demand.customer_id !== value.root.original.demand.customer_id) throw new Error("Revision requires another declaration of the same customer");
          if (fresh()) publish({ root: value.root, state: value, target });
        }
      } catch { if (fresh()) setError("Sélection à vérifier. Relisez la déclaration ou la liste avant de choisir une action."); }
      finally { if (current() && request === sequence.current) setBusy(false); }
    })();
  }, [choice]);
  function selection(action: WaitlistLifecycleRequest["action"]): WaitlistLifecycleSelection {
    const r = reviewRef.current; if (!r) throw new Error("Verified selection required");
    const target = action === "activate" ? r.root : action === "cancel" ? r.state?.current_demand : r.target;
    if (!target) throw new Error("Explicit target required"); const previous = r.state?.events[r.state.events.length-1];
    return { root: r.root, target, previous_state: r.state,
      request: { root_id: r.root.original.id, root_fingerprint: r.root.fingerprint, previous_id: previous?.original.id || null,
        previous_fingerprint: previous?.fingerprint || null, target_id: target.original.id, target_fingerprint: target.fingerprint,
        action, reason: reason.trim(), idempotency_key: crypto.randomUUID() } };
  }
  async function act(action?: WaitlistLifecycleRequest["action"], correct = false) {
    if (!current() || busy || pending.current) return;
    pending.current = true; sequence.current++; setBusy(true); setError(undefined); setReceipt(undefined);
    try {
      const frozen = driver.state(); const result = correct ? await driver.correct() : await driver.submit(frozen.status === "empty" && action ? selection(action) : undefined);
      if (!current()) return;
      if (result.status === "confirmed") { setReceipt(result.receipt); setReason(""); publish({ root: result.state.root, state: result.state }); onRetained?.(); }
      else if (result.status === "correctable") { publish(undefined); setReason(""); setReceipt(undefined); }
      else if (result.status === "busy") setError("Une vérification est déjà en cours. Reprenez ensuite avec la même clé.");
    } catch { if (current()) setError(driver.state().status === "empty" ? "Action non envoyée. Choisissez une déclaration relue et un motif d’au moins trois caractères."
      : "Conservation à vérifier. La décision figée reste conservée : reprenez avec la même clé."); }
    finally { pending.current = false; if (current()) { setSaved(driver.state()); setBusy(false); } }
  }
  function date(value: string) { try { return new Intl.DateTimeFormat("fr-CH", { timeZone: timezone || "UTC", dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); } catch { return value; } }
  function declaration(envelope: WaitlistEnvelope) { const o = envelope.original;
    return <><h3>{o.reason}</h3><p>Cliente {o.demand.customer_id} · prestation {o.demand.service_id} · durée {o.demand.duration_minutes} min.</p>
      <p>Contraintes {o.demand.constraints_review === "confirmed" ? "relues selon déclaration" : "inconnues : matching à vérifier"}.</p>
      <ul>{o.demand.availability.map((w, i) => <li key={i}>Du {date(w.start)} au {date(w.end)}.</li>)}</ul></>; }
  const locked = busy || saved.status !== "empty";
  return <section ref={panel} tabIndex={-1} className="revenue-guardian-panel waitlist-lifecycle-writer" aria-label="Gérer une liste d’attente">
    <h2>Gérer une liste d’attente</h2><p>Choisissez une déclaration ou une liste dans les historiques, puis relisez ses souhaits et choisissez explicitement l’action. L’activation et la révision recontrôlent les sources enregistrées. L’annulation ferme la chaîne. Aucune réservation ni aucun contact n’est effectué.</p>
    <p>Horaires : {timezone || "UTC — fuseau institut indisponible"}.</p>
    {review && saved.status === "empty" && <article>{declaration(review.target || review.state?.current_demand || review.root)}
      <p>{review.state ? review.state.state === "active" ? "Liste relue : active administrativement. La version sera contrôlée lors de l’action." : "Liste relue : annulée, aucune nouvelle transition possible." : "Déclaration relue : pas de liste activée pour cette racine."}</p>
      {review.state?.state === "active" && !review.target && <p>Pour réviser, choisissez une autre déclaration de cette cliente dans les demandes conservées. Vous pouvez d’abord déclarer ses nouveaux souhaits.</p>}
      {review.target && <p>Déclaration de remplacement relue pour cette liste.</p>}
      <details><summary>Voir la racine et la version relues</summary><p>Racine {review.root.original.id} · empreinte {review.root.fingerprint}.</p>
        {review.state && <p>Version {review.state.events[review.state.events.length-1].original.id} · empreinte {review.state.events[review.state.events.length-1].fingerprint}.</p>}</details>
    </article>}
    {saved.status === "frozen" && <article><h3>Décision figée à reprendre</h3><p>Action : {({ activate: "activation", revise: "révision", cancel: "annulation" })[saved.value.terms.request.action]} · motif : {saved.value.terms.request.reason}.</p>
      {declaration(saved.value.terms.target)}<details><summary>Voir la clé et les preuves figées</summary><p>Clé : {saved.value.terms.request.idempotency_key}</p><pre>{JSON.stringify(saved.value.terms, null, 2)}</pre></details></article>}
    {saved.status === "invalid" && <p role="alert">La décision locale est illisible. Aucune nouvelle action ne peut être envoyée dans ce contexte.</p>}
    {review && saved.status === "empty" && review.state?.state !== "cancelled" && <><label>Motif de l’action de liste d’attente<textarea disabled={locked} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <div className="revenue-guardian-period">{review.state === null ? <button disabled={locked} onClick={() => void act("activate")}>Activer cette demande</button> : <>
        {review.target && <button disabled={locked} onClick={() => void act("revise")}>Réviser avec la déclaration sélectionnée</button>}
        <button disabled={locked} onClick={() => void act("cancel")}>Annuler cette liste d’attente</button></>}</div></>}
    {saved.status === "frozen" && <div className="revenue-guardian-period"><button disabled={busy} onClick={() => void act()}>Reprendre l’action par clé</button>
      {driver.canCorrect() && <button disabled={busy} onClick={() => void act(undefined, true)}>Vérifier la clé avant de relire la décision</button>}</div>}
    {busy && <p role="status">Vérification de la liste d’attente…</p>}{error && <p role="alert">{error}</p>}
    {receipt && <article><h3>Action conservée et relue</h3><p>{({ activate: "Activation", revise: "Révision", cancel: "Annulation" })[receipt.original.action]} · {receipt.original.reason} · {date(receipt.original.created_at)} · auteur {receipt.original.actor_id}.</p>
      <p>État relu après l’action : {review?.state?.state === "cancelled" ? "annulé" : "actif administrativement"}. Des actions ultérieures peuvent déjà avoir été conservées.</p>
      <details><summary>Voir l’original de l’action relue</summary><p>Action {receipt.original.id} · clé {receipt.original.idempotency_key} · empreinte {receipt.fingerprint}.</p><pre>{JSON.stringify(receipt.original, null, 2)}</pre></details>
    </article>}
  </section>;
}
