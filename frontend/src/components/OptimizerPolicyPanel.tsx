import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { createOptimizerPolicyIntent } from "../optimizer-policy-intent";
import { optimizerFactors, optimizerBases, validOptimizerPolicyRequest, validOptimizerPolicyAudit, validOptimizerPolicyEnvelope,
  type OptimizerFactor, type OptimizerPolicyRequest, type OptimizerPolicyEnvelope, type OptimizerPolicyAudit } from "../optimizer-policy-utils";

export const optimizerLabels: Record<OptimizerFactor, string> = { revenue_score: "Valeur de référence du catalogue", utilization_score: "Durée proposée / fenêtre libre",
  continuity_score: "Continuité enregistrée", client_preference_score: "Préférence cliente", employee_preference_score: "Préférence collaboratrice",
  idle_gap_penalty: "Délai avant début", overtime_penalty: "Dépassement d’horaires déclarés", resource_conflict_penalty: "Conflit de ressources capturé" };
type Draft = { mode: string; numerator: string; denominator: string; ceiling: string; currency: string; priceMode: string; reason: string };
const drafts = (): Draft[] => optimizerFactors.map(() => ({ mode: "", numerator: "", denominator: "", ceiling: "", currency: "", priceMode: "", reason: "" }));
const storage = { getItem: (k: string) => sessionStorage.getItem(k), setItem: (k: string, v: string) => sessionStorage.setItem(k, v), removeItem: (k: string) => sessionStorage.removeItem(k) };
type Props = { institute: string; timezone?: string; onSelect?: (policy: OptimizerPolicyEnvelope | undefined) => void };
export function OptimizerPolicyPanel(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut" || !getOperatorSubject()) return null;
  return <Panel key={JSON.stringify([props.institute, props.timezone, getAccessToken()])} {...props} />;
}
function Rules({ request }: { request: OptimizerPolicyRequest }) {
  return <><ul>{request.terms.rules.map(r => <li key={r.factor}><strong>{optimizerLabels[r.factor]}</strong> : {r.basis === "disabled" ? "désactivé explicitement" : `poids ${r.weight.numerator}/${r.weight.denominator}`}
    {r.ceiling && ` · plafond ${r.ceiling} ${r.factor === "revenue_score" ? `unités monétaires mineures ${r.currency} · tarif ${r.price_mode === "member" ? "abonnée" : "passage"}` : "microsecondes"}`} · {r.reason}</li>)}</ul><p>Motif : {request.reason}</p></>;
}
function Panel({ institute, timezone, onSelect }: Props) {
  const actor = getOperatorSubject()!, token = getAccessToken(), mounted = useRef(false), writeFlight = useRef(false), readSequence = useRef(0);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; readSequence.current++; }; }, []);
  const current = () => mounted.current && token === getAccessToken() && actor === getOperatorSubject() && getOperatorRole() === "responsable_institut";
  const [driver] = useState(() => createOptimizerPolicyIntent({ institute, actor, storage, current,
    get: path => apiGet(path), post: (path, terms) => apiPost(path, terms) }));
  const [saved, setSaved] = useState(() => driver.state()), [draft, setDraft] = useState(drafts), [reason, setReason] = useState("");
  const [receipt, setReceipt] = useState<OptimizerPolicyEnvelope>(), [selected, setSelected] = useState<OptimizerPolicyEnvelope>();
  const [report, setReport] = useState<OptimizerPolicyAudit>(), [writing, setWriting] = useState(false), [reading, setReading] = useState(false);
  const [error, setError] = useState<string>(), [readError, setReadError] = useState<string>();
  const base = `/optimizer/institutes/${encodeURIComponent(institute)}`;
  function date(value: string) { try { return new Intl.DateTimeFormat("fr-CH", { timeZone: timezone || "UTC", dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); } catch { return value; } }
  function change(index: number, update: Partial<Draft>) { setDraft(old => old.map((r, i) => i === index ? { ...r, ...update } : r)); setError(undefined); }
  function request(): OptimizerPolicyRequest {
    if (draft.some(d => !["enabled", "disabled"].includes(d.mode))) throw new Error("Explicit choices required");
    const terms: unknown = { rules: optimizerFactors.map((factor, i) => { const d = draft[i], enabled = d.mode === "enabled";
      return { factor, weight: { numerator: enabled ? d.numerator : "0", denominator: enabled ? d.denominator : "1" },
        basis: enabled ? optimizerBases[factor] : "disabled", ceiling: enabled && ["revenue_score", "idle_gap_penalty", "overtime_penalty"].includes(factor) ? d.ceiling : null,
        currency: enabled && factor === "revenue_score" ? d.currency : null, price_mode: enabled && factor === "revenue_score" ? d.priceMode : null, reason: d.reason.trim() };
    }), normalization: "exact_unit_interval_explicit_ceiling_saturation" };
    const value = { terms, reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validOptimizerPolicyRequest(value)) throw new Error("Invalid explicit policy");
    return value;
  }
  async function act(correct = false) {
    if (!current() || writeFlight.current || receipt) return;
    writeFlight.current = true; setWriting(true); setError(undefined);
    try {
      const state = driver.state(), result = correct ? await driver.correct() : await driver.submit(state.status === "empty" ? request() : undefined);
      if (!current()) return;
      if (result.status === "confirmed") { setReceipt(result.receipt); readSequence.current++; setReport(undefined); setReading(false); setReadError(undefined); setSelected(undefined); onSelect?.(undefined); }
      else if (result.status === "busy") setError("Une reprise est déjà en cours. Réessayez avec la même clé.");
    } catch { if (current()) setError(driver.state().status === "empty"
      ? "Politique non envoyée. Choisissez les huit statuts, au moins un facteur pondéré, les poids entiers exacts, les plafonds requis et des motifs d’au moins trois caractères."
      : "Conservation à vérifier. Les termes figés restent conservés ; reprenez avec la même clé."); }
    finally { writeFlight.current = false; if (current()) { setSaved(driver.state()); setWriting(false); } }
  }
  async function load(offset = 0) {
    if (!current() || writing) return;
    const sequence = ++readSequence.current, live = () => current() && sequence === readSequence.current;
    setReport(undefined); setReading(true); setReadError(undefined); setSelected(undefined); onSelect?.(undefined);
    try {
      const value = await apiGet<OptimizerPolicyAudit>(`${base}/policy-originals?offset=${offset}&limit=20`);
      if (!await validOptimizerPolicyAudit(value, institute, offset)) throw new Error("Invalid policy audit");
      if (live()) setReport(value);
    } catch { if (live()) setReadError("Politiques conservées à vérifier. Relancez la lecture."); }
    finally { if (live()) setReading(false); }
  }
  async function select(value: OptimizerPolicyEnvelope) {
    const sequence = readSequence.current;
    if (!current() || writing || reading) return;
    if (!await validOptimizerPolicyEnvelope(value, institute)) return;
    if (current() && sequence === readSequence.current && !writeFlight.current) { setSelected(value); onSelect?.(value); }
  }
  const locked = writing || saved.status !== "empty" || !!receipt;
  return <section className="revenue-guardian-panel optimizer-policy-panel" aria-label="Politique de scoring des créneaux"><h2>Politique de scoring des créneaux</h2>
    <p>Choisissez les hypothèses à utiliser lors d’une revue. Aucune politique ne devient un réglage automatique ; aucune réservation ni aucun contact n’est effectué.</p>
    <p>Une valeur inconnue reste inconnue. La devise du catalogue, la continuité liée à une collaboratrice, les préférences et les horaires déclarés ne sont pas actuellement prouvés : leur pondération empêchera un classement complet.</p>
    <p>Les poids sont des fractions entières non négatives. Les trois derniers facteurs sont soustraits ; un conflit constaté bloque l’option même avec un poids nul.</p>
    <details><summary>Créer une politique explicite</summary><fieldset disabled={locked}><legend>Huit facteurs et leurs motifs</legend>
      {optimizerFactors.map((factor, i) => { const d = draft[i]; return <fieldset key={factor}><legend>{optimizerLabels[factor]}</legend>
        <label>Statut — {optimizerLabels[factor]}<select value={d.mode} onChange={e => change(i, { mode: e.target.value, numerator: "", denominator: "", ceiling: "", currency: "", priceMode: "" })}>
          <option value="">Choisir</option><option value="disabled">Désactiver explicitement</option><option value="enabled">Pondérer explicitement</option></select></label>
        {d.mode === "enabled" && <div className="revenue-guardian-period"><label>Numérateur du poids — {optimizerLabels[factor]}<input inputMode="numeric" value={d.numerator} onChange={e => change(i, { numerator: e.target.value })} /></label>
          <label>Dénominateur du poids — {optimizerLabels[factor]}<input inputMode="numeric" value={d.denominator} onChange={e => change(i, { denominator: e.target.value })} /></label>
          {["revenue_score", "idle_gap_penalty", "overtime_penalty"].includes(factor) && <label>Plafond — {optimizerLabels[factor]} ({factor === "revenue_score" ? "unités monétaires mineures" : "microsecondes"})<input inputMode="numeric" value={d.ceiling} onChange={e => change(i, { ceiling: e.target.value })} /></label>}
          {factor === "revenue_score" && <><label>Devise de référence<select value={d.currency} onChange={e => change(i, { currency: e.target.value })}><option value="">Choisir</option><option value="CHF">CHF</option><option value="EUR">EUR</option></select></label>
            <label>Tarif de référence<select value={d.priceMode} onChange={e => change(i, { priceMode: e.target.value })}><option value="">Choisir</option><option value="member">Abonnée</option><option value="passage">Passage</option></select></label></>}
        </div>}
        <label>Motif — {optimizerLabels[factor]}<input value={d.reason} onChange={e => change(i, { reason: e.target.value })} /></label>
      </fieldset>; })}<label>Motif de la politique<textarea value={reason} onChange={e => setReason(e.target.value)} /></label></fieldset>
      <div className="revenue-guardian-period"><button disabled={locked} onClick={() => void act()}>Conserver la politique et relire l’original</button></div>
    </details>
    {saved.status === "frozen" && <article><h3>Politique figée à reprendre</h3><Rules request={saved.value.terms} /><details><summary>Voir les termes figés et la clé</summary><pre>{JSON.stringify(saved.value.terms, null, 2)}</pre></details>
      <div className="revenue-guardian-period"><button disabled={writing} onClick={() => void act()}>Reprendre la politique par clé</button>{driver.canCorrect() && <button disabled={writing} onClick={() => void act(true)}>Vérifier la clé avant correction de politique</button>}</div></article>}
    {saved.status === "invalid" && <p role="alert">La politique locale est illisible. Toute nouvelle conservation est bloquée dans ce contexte.</p>}
    {writing && <p role="status">Vérification de la conservation de politique…</p>}{error && <p role="alert">{error}</p>}
    {receipt && <article><h3>Politique conservée et relue</h3><Rules request={receipt.original} /><p>Auteur {receipt.original.actor_id} · {date(receipt.original.created_at)}.</p>
      <details><summary>Voir l’original de politique</summary><p>Empreinte {receipt.fingerprint}</p><pre>{JSON.stringify(receipt.original, null, 2)}</pre></details>
      <div className="revenue-guardian-period"><button onClick={() => void select(receipt)} disabled={writing || reading}>Choisir cette politique pour la revue</button>
        <button onClick={() => { if (current()) { setReceipt(undefined); setDraft(drafts()); setReason(""); setError(undefined); } }}>Préparer une autre politique</button></div></article>}
    <div className="revenue-guardian-period"><button disabled={reading || writing} onClick={() => void load()}>Lire les politiques conservées</button></div>
    {reading && <p role="status">Lecture des politiques…</p>}{readError && <p role="alert">{readError}</p>}
    {report && <><p>{report.originals.length ? `${report.offset+1}–${report.offset+report.originals.length}` : "0"} sur {report.total} politiques · lecture au {date(report.captured_at)}.</p>
      {report.originals.map(e => <article key={e.original.id}><h3>{e.original.reason}</h3><p>Auteur {e.original.actor_id} · {date(e.original.created_at)}.</p>
        <details><summary>Voir les règles et l’original de cette politique</summary><Rules request={e.original} /><p>Empreinte {e.fingerprint}</p><pre>{JSON.stringify(e.original, null, 2)}</pre></details>
        <div className="revenue-guardian-period"><button disabled={writing || reading} onClick={() => void select(e)}>Choisir cette politique pour la revue</button></div></article>)}
      <div className="revenue-guardian-period"><button disabled={reading || writing || report.offset === 0} onClick={() => void load(Math.max(0, report.offset-20))}>Politiques précédentes</button>
        <button disabled={reading || writing || report.offset+report.originals.length >= report.total} onClick={() => void load(report.offset+20)}>Politiques suivantes</button></div></>}
    {selected && <p role="status">Politique choisie pour la prochaine revue : {selected.original.reason}. Aucun score n’est calculé par cette sélection.</p>}
  </section>;
}
