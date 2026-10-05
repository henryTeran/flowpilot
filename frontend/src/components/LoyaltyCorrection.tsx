import { useEffect, useRef, useState } from "react";
import { apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";

type Intent = { points: number; reason: string; idempotency_key: string };
function validPoints(points: number) { return Number.isSafeInteger(points) && points !== 0 && Math.abs(points) <= 1e9; }
function recover(key: string): Intent | undefined {
  try {
    const row = JSON.parse(sessionStorage.getItem(key) || "null");
    if (!row || !validPoints(row.points) || typeof row.reason !== "string" || row.reason.trim().length < 3 || row.reason.length > 240 ||
        typeof row.idempotency_key !== "string" || !row.idempotency_key || row.idempotency_key.length > 120) return;
    return { points: row.points, reason: row.reason, idempotency_key: row.idempotency_key };
  } catch { return; }
}
type Props = { instituteId: string; customerId: string; onChanged: () => Promise<boolean> };
export function LoyaltyCorrection(props: Props) {
  return <CorrectionForm key={JSON.stringify([props.instituteId, props.customerId, getAccessToken()])} {...props} />;
}
function CorrectionForm({ instituteId, customerId, onChanged }: Props) {
  const token = getAccessToken(), subject = getOperatorSubject();
  const manager = getOperatorRole() === "responsable_institut" && !!subject;
  const storageKey = `flowpilot.loyalty-correction:${encodeURIComponent(instituteId)}:${encodeURIComponent(customerId)}:${encodeURIComponent(subject || "")}`;
  const [intent, setIntent] = useState<Intent>(), [points, setPoints] = useState(""), [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [message, setMessage] = useState<string>();
  const lifetime = useRef(0), pending = useRef(false);
  const callbacks = useRef(onChanged); callbacks.current = onChanged;
  function capture() { const generation = lifetime.current; return () => generation === lifetime.current && token === getAccessToken(); }
  useEffect(() => {
    lifetime.current++; setIntent(manager ? recover(storageKey) : undefined);
    return () => { lifetime.current++; };
  }, []);
  async function save() {
    if (!manager || pending.current) return;
    const row = intent || { points: Number(points), reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validPoints(row.points) || row.reason.length < 3 || (!intent && !/^[+-]?\d+$/.test(points))) return;
    const current = capture(); pending.current = true; setBusy(true); setIntent(row); setError(undefined); setMessage(undefined);
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(row));
      await apiPost(`/loyalty/institutes/${encodeURIComponent(instituteId)}/customers/${encodeURIComponent(customerId)}/adjustments`, row);
      if (!current()) return;
      if (!await callbacks.current()) throw new Error("Actualiser le solde et son historique avant de poursuivre");
      if (!current()) return;
      sessionStorage.removeItem(storageKey); setIntent(undefined); setPoints(""); setReason(""); setMessage("Correction enregistree");
    } catch (reason) {
      if (current()) {
        const rejected = reason instanceof ApiError && reason.status >= 400 && reason.status < 500;
        if (rejected) { sessionStorage.removeItem(storageKey); setIntent(undefined); setPoints(String(row.points)); setReason(row.reason); }
        setError(`${reason instanceof Error ? reason.message : "Operation indisponible"}${rejected ? "" : ". Reessayez la correction conservee."}`);
      }
    } finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  if (!manager) return null;
  return <section aria-label="Correction des points"><h4>Correction des points</h4>
    <p>Correction manuelle avec motif. Un montant positif ajoute des points, un montant negatif en retire.</p>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {intent ? <p>Correction conservee : {intent.points} points, {intent.reason}</p> : <fieldset disabled={busy}>
      <label>Variation de points<input inputMode="numeric" value={points} onChange={event => setPoints(event.target.value)} /></label>
      <label>Motif de correction<input maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label>
    </fieldset>}
    <button type="button" disabled={busy || (!intent && (!/^[+-]?\d+$/.test(points) || !validPoints(Number(points)) || reason.trim().length < 3))} onClick={() => void save()}>{intent ? "Reessayer la correction conservee" : "Enregistrer la correction"}</button>
  </section>;
}
