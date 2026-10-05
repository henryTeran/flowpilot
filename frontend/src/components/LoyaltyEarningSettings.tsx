import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";

type Intent = { currency: "CHF" | "EUR"; points_per_unit: string; enabled: boolean; reason: string; idempotency_key: string };
type Policy = Intent & { revision: number };
function validRate(value: string) { return /^\d{1,5}(\.\d{1,4})?$/.test(value) && Number(value) > 0 && Number(value) <= 10000; }
function recover(key: string): Intent | undefined {
  try {
    const row = JSON.parse(sessionStorage.getItem(key) || "null");
    if (!row || !["CHF", "EUR"].includes(row.currency) || typeof row.points_per_unit !== "string" || !validRate(row.points_per_unit) ||
        typeof row.enabled !== "boolean" || typeof row.reason !== "string" || row.reason.trim().length < 3 || row.reason.length > 240 ||
        typeof row.idempotency_key !== "string" || !row.idempotency_key || row.idempotency_key.length > 120) return;
    return { currency: row.currency, points_per_unit: row.points_per_unit, enabled: row.enabled, reason: row.reason, idempotency_key: row.idempotency_key };
  } catch { return; }
}
export function LoyaltyEarningSettings({ instituteId }: { instituteId: string }) {
  return <EarningForm key={JSON.stringify([instituteId, getAccessToken()])} instituteId={instituteId} />;
}
function EarningForm({ instituteId }: { instituteId: string }) {
  const token = getAccessToken(), subject = getOperatorSubject();
  const manager = getOperatorRole() === "responsable_institut" && !!subject;
  const prefix = `/loyalty/institutes/${encodeURIComponent(instituteId)}`;
  const storageKey = `flowpilot.loyalty-policy:${encodeURIComponent(instituteId)}:${encodeURIComponent(subject || "")}`;
  const [policy, setPolicy] = useState<Policy | null>(), [currency, setCurrency] = useState<string>();
  const [rate, setRate] = useState(""), [reason, setReason] = useState(""), [enabled, setEnabled] = useState(true);
  const [intent, setIntent] = useState<Intent>(), [loaded, setLoaded] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [message, setMessage] = useState<string>();
  const epoch = useRef(0), reads = useRef(0), pending = useRef(false);
  function capture() { const generation = epoch.current; return () => generation === epoch.current && token === getAccessToken(); }
  async function reload() {
    const current = capture(), request = ++reads.current;
    const [latest, settings] = await Promise.all([apiGet<Policy | null>(`${prefix}/earning-policy`),
      apiGet<{currency: string} | null>(`/gift-cards/institutes/${encodeURIComponent(instituteId)}/settings`).catch(reason => {
        if (reason instanceof ApiError && reason.status === 400) return null;
        throw reason;
      })]);
    if (!current() || request !== reads.current) return false;
    setPolicy(latest); setCurrency(settings?.currency); setLoaded(true); return true;
  }
  useEffect(() => {
    epoch.current++; const current = capture(); setIntent(manager ? recover(storageKey) : undefined);
    void reload().catch(reason => { if (current()) setError(reason instanceof Error ? reason.message : "Programme indisponible"); });
    return () => { epoch.current++; };
  }, []);
  async function refresh() {
    const current = capture(); setError(undefined);
    try { await reload(); } catch (reason) { if (current()) setError(String(reason)); }
  }
  async function save() {
    if (!manager || pending.current || !loaded || !["CHF", "EUR"].includes(currency || "")) return;
    const normalized = rate.trim().replace(",", ".");
    const row = intent || { currency: currency as "CHF" | "EUR", points_per_unit: normalized, enabled, reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validRate(row.points_per_unit) || row.reason.length < 3) return;
    const current = capture(); pending.current = true; reads.current++; setBusy(true); setIntent(row); setError(undefined); setMessage(undefined);
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(row));
      await apiPost(`${prefix}/earning-policies`, row);
      if (!current() || !await reload()) return;
      sessionStorage.removeItem(storageKey); setIntent(undefined); setRate(""); setReason(""); setMessage("Programme enregistre");
    } catch (reason) {
      if (current()) {
        const rejected = reason instanceof ApiError && reason.status >= 400 && reason.status < 500;
        if (rejected) { sessionStorage.removeItem(storageKey); setIntent(undefined); setRate(row.points_per_unit); setReason(row.reason); setEnabled(row.enabled); }
        setError(`${reason instanceof Error ? reason.message : "Operation indisponible"}${rejected ? "" : ". Reessayez le programme conserve."}`);
      }
    } finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  return <section aria-label="Acquisition de points"><h3>Acquisition de points</h3>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <button type="button" disabled={busy} onClick={() => void refresh()}>Actualiser le programme</button>
    {loaded && (policy ? <p>Version {policy.revision} ? {policy.enabled ? "Active" : "Suspendue"} ? {policy.points_per_unit} points par {policy.currency}</p> : <p>Aucun programme configure</p>)}
    {loaded && !currency && <p>Configurez la devise dans Cartes cadeaux avant le programme de points.</p>}
    {manager && currency && <><p>Devise configuree : {currency}. Les points entiers sont acquis sur le montant effectif a la cloture.</p>
      {intent ? <p>Programme conserve : {intent.points_per_unit} points par {intent.currency} ? {intent.enabled ? "Actif" : "Suspendu"} ? {intent.reason}</p> : <fieldset disabled={busy}>
        <label>Points par unite monetaire<input inputMode="decimal" value={rate} onChange={event => setRate(event.target.value)} /></label>
        <label>Motif du programme<input maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label>
        <label><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} />Acquisition active</label>
      </fieldset>}
      <button type="button" disabled={busy || !loaded || (!intent && (!validRate(rate.trim().replace(",", ".")) || reason.trim().length < 3))} onClick={() => void save()}>{intent ? "Reessayer le programme conserve" : "Enregistrer le programme"}</button>
    </>}
  </section>;
}
