import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { instituteMidnight } from "../outlook-utils";
import { validRevenueScenarioDeclaration, validRevenueScenarioEnvelope, matchesRevenueScenarioReceipt,
  type RevenueScenarioDeclaration, type RevenueScenarioEnvelope } from "../revenue-scenario-utils";
type Saved = { institute: string; actor: string; terms: RevenueScenarioDeclaration };
export function RevenueScenarioWriter(props: { institute: string; timezone?: string; onRetained?: () => void }) {
  if (!props.institute || !getOperatorSubject() || getOperatorRole() !== "responsable_institut") return null;
  return <Writer key={JSON.stringify([props.institute, getAccessToken()])} {...props} />;
}
function Writer({ institute, timezone, onRetained }: { institute: string; timezone?: string; onRetained?: () => void }) {
  const actor = getOperatorSubject()!, token = getAccessToken(), storage = `flowpilot.revenue-scenario.v1:${JSON.stringify([institute, actor])}`;
  const base = `/revenue/institutes/${encodeURIComponent(institute)}/scenarios`;
  function validSaved(v: unknown): v is Saved {
    const s = v as Saved; return !!s && typeof s === "object" && Object.keys(s).sort().join(" ") === "actor institute terms"
      && s.institute === institute && s.actor === actor && validRevenueScenarioDeclaration(s.terms);
  }
  const [saved, setSaved] = useState<{ value?: Saved; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const s = JSON.parse(raw); return validSaved(s) ? { value: s } : { invalid: true }; }
    catch { return { invalid: true }; }
  });
  const [dates, setDates] = useState(["", "", "", ""]), [currency, setCurrency] = useState(""), [numerator, setNumerator] = useState(""), [denominator, setDenominator] = useState(""), [reason, setReason] = useState("");
  const [receipt, setReceipt] = useState<RevenueScenarioEnvelope>(), [error, setError] = useState<string>(), [busy, setBusy] = useState(false), [rejected, setRejected] = useState(false);
  const mounted = useRef(false), pending = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const current = () => mounted.current && token === getAccessToken() && actor === getOperatorSubject() && getOperatorRole() === "responsable_institut";
  async function accept(e: RevenueScenarioEnvelope, terms: RevenueScenarioDeclaration) {
    if (!await validRevenueScenarioEnvelope(e, institute) || !matchesRevenueScenarioReceipt(e, terms, actor)) throw new Error();
    if (!current()) return;
    const byKey = await apiGet<RevenueScenarioEnvelope | null>(`${base}/original-by-key?${new URLSearchParams({ key: terms.idempotency_key })}`);
    if (!byKey || !await validRevenueScenarioEnvelope(byKey, institute) || !matchesRevenueScenarioReceipt(byKey, terms, actor)
      || byKey.fingerprint !== e.fingerprint || byKey.original.id !== e.original.id) throw new Error();
    if (!current()) return;
    const byId = await apiGet<RevenueScenarioEnvelope>(`${base}/originals/${encodeURIComponent(e.original.id)}`);
    if (!await validRevenueScenarioEnvelope(byId, institute) || byId.original.id !== e.original.id || byId.fingerprint !== e.fingerprint || !matchesRevenueScenarioReceipt(byId, terms, actor)) throw new Error();
    if (!current()) return;
    const raw = sessionStorage.getItem(storage);
    if (!raw || !validSaved(JSON.parse(raw)) || JSON.stringify(JSON.parse(raw).terms) !== JSON.stringify(terms)) throw new Error();
    sessionStorage.removeItem(storage); setSaved({}); setReceipt(byId); onRetained?.();
  }
  async function retain() {
    if (!current() || pending.current || saved.invalid || receipt) return;
    pending.current = true; setBusy(true); setError(undefined); setRejected(false);
    let frozen = !!saved.value;
    try {
      let terms = saved.value?.terms;
      if (!terms) {
        if (!timezone) throw new Error();
        const instants = dates.map(d => instituteMidnight(d, timezone)); if (instants.some(d => !d)) throw new Error();
        terms = { assumptions: { model: "constant_recorded_gross_rate_v1", observed_start: instants[0]!, observed_end: instants[1]!,
          projected_start: instants[2]!, projected_end: instants[3]!, currency: currency as "CHF" | "EUR", activity_fraction: { numerator, denominator } },
          reason: reason.trim(), idempotency_key: crypto.randomUUID() };
        if (!validRevenueScenarioDeclaration(terms) || !current() || sessionStorage.getItem(storage) !== null) throw new Error();
        const value = { institute, actor, terms }; sessionStorage.setItem(storage, JSON.stringify(value)); setSaved({ value });
        frozen = true;
      }
      const original = await apiGet<RevenueScenarioEnvelope | null>(`${base}/original-by-key?${new URLSearchParams({ key: terms.idempotency_key })}`);
      if (!current()) return;
      if (original) { await accept(original, terms); return; }
      await accept(await apiPost<RevenueScenarioEnvelope>(`${base}/originals`, terms), terms);
    } catch (e) {
      if (current()) { if (e instanceof ApiError && [400, 422].includes(e.status)) setRejected(true);
        setError(frozen ? "Conservation à vérifier. Reprenez la demande figée avec la même clé."
          : "Demande non envoyée. Vérifiez les quatre dates, la devise, la fraction entre 0 et 1 et le motif d’au moins trois caractères, puis réessayez."); }
    } finally { pending.current = false; if (current()) setBusy(false); }
  }
  async function correct() {
    if (!current() || pending.current || !saved.value || !rejected) return;
    pending.current = true; setBusy(true); setError(undefined);
    try {
      const terms = saved.value.terms, original = await apiGet<RevenueScenarioEnvelope | null>(`${base}/original-by-key?${new URLSearchParams({ key: terms.idempotency_key })}`);
      if (!current()) return;
      if (original) { await accept(original, terms); return; }
      const raw = sessionStorage.getItem(storage);
      if (!raw || !validSaved(JSON.parse(raw)) || JSON.stringify(JSON.parse(raw).terms) !== JSON.stringify(terms)) throw new Error();
      sessionStorage.removeItem(storage); setSaved({}); setRejected(false);
    } catch { if (current()) setError("Clé à vérifier. La demande figée reste conservée."); }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  const locked = busy || !!saved.value || !!saved.invalid || !!receipt;
  return <section className="revenue-guardian-panel" aria-label="Conserver un scénario">
    <h2>Conserver un scénario conditionnel</h2>
    <p>Rythme brut enregistré constant, appliqué à une période future avec votre fraction d’activité déclarée. Les sources seront capturées au moment de la conservation. Une projection indisponible peut aussi être conservée avec ses preuves ; aucune action ni prévision validée n’en découle.</p>
    <p>Journées de l’institut · {timezone || "Fuseau indisponible"}. Début inclus, fin exclue.</p>
    <div className="revenue-guardian-period">{["Début observé", "Fin observée exclue", "Début projeté", "Fin projetée exclue"].map((label, i) => <label key={label}>{label}<input disabled={locked} type="date" value={dates[i]} onChange={e => setDates(old => old.map((v, n) => n === i ? e.target.value : v))} /></label>)}</div>
    <div className="revenue-guardian-period"><label>Devise du scénario <select disabled={locked} value={currency} onChange={e => setCurrency(e.target.value)}><option value="">Choisir</option><option>CHF</option><option>EUR</option></select></label>
      <label>Numérateur d’activité <input disabled={locked} inputMode="numeric" value={numerator} onChange={e => setNumerator(e.target.value)} /></label>
      <label>Dénominateur d’activité <input disabled={locked} inputMode="numeric" value={denominator} onChange={e => setDenominator(e.target.value)} /></label></div>
    <label>Motif du scénario <textarea disabled={locked} value={reason} onChange={e => setReason(e.target.value)} /></label>
    {saved.value && <article><h3>Demande figée à reprendre</h3><p>Clé : {saved.value.terms.idempotency_key}</p><p>{saved.value.terms.reason}</p>
      <p>{saved.value.terms.assumptions.currency} · Fraction {saved.value.terms.assumptions.activity_fraction.numerator} / {saved.value.terms.assumptions.activity_fraction.denominator}</p>
      <p>Observé : {saved.value.terms.assumptions.observed_start} → {saved.value.terms.assumptions.observed_end}</p><p>Projeté : {saved.value.terms.assumptions.projected_start} → {saved.value.terms.assumptions.projected_end}</p></article>}
    {saved.invalid && <p role="alert">La demande locale est illisible. Aucune nouvelle conservation n’est autorisée dans ce contexte.</p>}
    <div className="revenue-guardian-period"><button disabled={busy || !!saved.invalid || !!receipt} onClick={() => void retain()}>{saved.value ? "Reprendre la conservation par clé" : "Conserver ces hypothèses et capturer les sources"}</button>
      {rejected && saved.value && <button disabled={busy} onClick={() => void correct()}>Vérifier la clé avant correction</button>}</div>
    {busy && <p role="status">Vérification de la conservation…</p>}{error && <p role="alert">{error}</p>}
    {receipt && <article><h3>Scénario conservé et relu</h3><p>Original {receipt.original.id} · Auteur {receipt.original.actor_id} · {receipt.original.created_at}</p><p>Clé : {receipt.original.idempotency_key}</p><p>Empreinte : {receipt.fingerprint}</p>
      <p>{receipt.original.reason}</p><p>Fraction déclarée : {receipt.original.assumptions.activity_fraction.numerator} / {receipt.original.assumptions.activity_fraction.denominator} · {receipt.original.assumptions.currency}</p>
      <p>Observé : {receipt.original.assumptions.observed_start} → {receipt.original.assumptions.observed_end}</p><p>Projeté : {receipt.original.assumptions.projected_start} → {receipt.original.assumptions.projected_end}</p>
      <p>Projection conditionnelle : {receipt.original.projected_gross_minor ? `${receipt.original.projected_gross_minor.numerator} / ${receipt.original.projected_gross_minor.denominator} centimes ${receipt.original.assumptions.currency}` : "indisponible"}. Consultez l’historique pour ses preuves.</p></article>}
    {receipt && <div className="revenue-guardian-period"><button onClick={() => { setReceipt(undefined); setError(undefined); setDates(["", "", "", ""]); setCurrency(""); setNumerator(""); setDenominator(""); setReason(""); }}>Déclarer un autre scénario</button></div>}
  </section>;
}
