import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";

type Intent = { currency: "CHF" | "EUR"; name: string; service_id: string; points_cost: number; minimum_points: number; discount_amount: string; idempotency_key: string };
type Reward = Intent & { id: string };
import type { Service } from "../types";
function validAmount(value: string) { return /^\d{1,8}(\.\d{1,2})?$/.test(value) && Number(value) > 0; }
function validPoints(value: number, positive = false) { return Number.isSafeInteger(value) && value >= (positive ? 1 : 0) && value <= 1e9; }
function recover(key: string): Intent | undefined {
  try {
    const row = JSON.parse(sessionStorage.getItem(key) || "null");
    if (!row || !["CHF", "EUR"].includes(row.currency) || typeof row.name !== "string" || !row.name.trim() || row.name.length > 120 ||
        typeof row.service_id !== "string" || !row.service_id || row.service_id.length > 80 ||
        !validPoints(row.points_cost, true) || !validPoints(row.minimum_points) || typeof row.discount_amount !== "string" || !validAmount(row.discount_amount) ||
        typeof row.idempotency_key !== "string" || !row.idempotency_key || row.idempotency_key.length > 120) return;
    return { currency: row.currency, name: row.name, service_id: row.service_id, points_cost: row.points_cost,
      minimum_points: row.minimum_points, discount_amount: row.discount_amount, idempotency_key: row.idempotency_key };
  } catch { return; }
}
export function LoyaltyRewards({ instituteId, services }: { instituteId: string; services: Service[] }) {
  return <RewardForm key={JSON.stringify([instituteId, getAccessToken()])} instituteId={instituteId} services={services} />;
}
function RewardForm({ instituteId, services }: { instituteId: string; services: Service[] }) {
  const token = getAccessToken(), subject = getOperatorSubject();
  const manager = getOperatorRole() === "responsable_institut" && !!subject;
  const prefix = `/loyalty/institutes/${encodeURIComponent(instituteId)}`;
  const storageKey = `flowpilot.loyalty-reward:${encodeURIComponent(instituteId)}:${encodeURIComponent(subject || "")}`;
  const [rewards, setRewards] = useState<Reward[]>([]), [currency, setCurrency] = useState<string>();
  const [name, setName] = useState(""), [serviceId, setServiceId] = useState(""), [cost, setCost] = useState(""), [threshold, setThreshold] = useState("0"), [amount, setAmount] = useState("");
  const [intent, setIntent] = useState<Intent>(), [loaded, setLoaded] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [message, setMessage] = useState<string>();
  const epoch = useRef(0), reads = useRef(0), pending = useRef(false);
  function capture() { const generation = epoch.current; return () => generation === epoch.current && token === getAccessToken(); }
  async function reload() {
    const current = capture(), request = ++reads.current;
    const [latest, settings] = await Promise.all([apiGet<Reward[]>(`${prefix}/rewards`),
      apiGet<{currency: string} | null>(`/gift-cards/institutes/${encodeURIComponent(instituteId)}/settings`).catch(reason => {
        if (reason instanceof ApiError && reason.status === 400) return null;
        throw reason;
      })]);
    if (!current() || request !== reads.current) return false;
    setRewards(latest); setCurrency(settings?.currency); setLoaded(true); return true;
  }
  useEffect(() => {
    epoch.current++; const current = capture(); setIntent(manager ? recover(storageKey) : undefined);
    void reload().catch(reason => { if (current()) setError(reason instanceof Error ? reason.message : "Recompenses indisponibles"); });
    return () => { epoch.current++; };
  }, []);
  async function refresh() {
    const current = capture(); setError(undefined);
    try { await reload(); } catch (reason) { if (current()) setError(String(reason)); }
  }
  async function save() {
    if (!manager || pending.current || !loaded || !["CHF", "EUR"].includes(currency || "")) return;
    const normalized = amount.trim().replace(",", ".");
    const row = intent || { currency: currency as "CHF" | "EUR", name: name.trim(), service_id: serviceId, points_cost: Number(cost), minimum_points: Number(threshold), discount_amount: normalized, idempotency_key: crypto.randomUUID() };
    if (!row.name || (!intent && !services.some(service => service.id === row.service_id)) || !validPoints(row.points_cost, true) || !validPoints(row.minimum_points) || !validAmount(row.discount_amount)) return;
    const current = capture(); pending.current = true; reads.current++; setBusy(true); setIntent(row); setError(undefined); setMessage(undefined);
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(row));
      await apiPost(`${prefix}/rewards`, row);
      if (!current() || !await reload()) return;
      sessionStorage.removeItem(storageKey); setIntent(undefined); setName(""); setCost(""); setAmount(""); setMessage("Recompense configuree");
    } catch (reason) {
      if (current()) {
        const rejected = reason instanceof ApiError && reason.status >= 400 && reason.status < 500;
        if (rejected) { sessionStorage.removeItem(storageKey); setIntent(undefined); setName(row.name); setServiceId(row.service_id); setCost(String(row.points_cost)); setThreshold(String(row.minimum_points)); setAmount(row.discount_amount); }
        setError(`${reason instanceof Error ? reason.message : "Operation indisponible"}${rejected ? "" : ". Reessayez la recompense conservee."}`);
      }
    } finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  const valid = !!name.trim() && !!serviceId && /^\d+$/.test(cost) && /^\d+$/.test(threshold) && validPoints(Number(cost), true) && validPoints(Number(threshold)) && validAmount(amount.trim().replace(",", "."));
  return <section aria-label="Recompenses de fidelite"><h3>Recompenses de fidelite</h3>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <button type="button" disabled={busy} onClick={() => void refresh()}>Actualiser les recompenses</button>
    {rewards.map(row => <p key={row.id}>{row.name} : {row.points_cost} points par seance, seuil {row.minimum_points} points, reduction {row.discount_amount} {row.currency} par seance.</p>)}
    {loaded && !rewards.length && <p>Aucune recompense configuree</p>}
    {loaded && !currency && <p>Configurez la devise dans Cartes cadeaux avant les recompenses.</p>}
    {manager && currency && <><p>Devise configuree : {currency}. La reduction est plafonnee au prix de la prestation.</p>
      {intent ? <p>Recompense conservee : {intent.name}, {intent.points_cost} points, reduction {intent.discount_amount} {intent.currency}.</p> : <fieldset disabled={busy}>
        <label>Nom de la recompense<input maxLength={120} value={name} onChange={event => setName(event.target.value)} /></label>
        <label>Prestation de la recompense<select value={serviceId} onChange={event => setServiceId(event.target.value)}><option value="">Choisir</option>{services.map(service => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
        <label>Cout en points par seance<input inputMode="numeric" value={cost} onChange={event => setCost(event.target.value)} /></label>
        <label>Seuil avant utilisation<input inputMode="numeric" value={threshold} onChange={event => setThreshold(event.target.value)} /></label>
        <label>Reduction par seance<input inputMode="decimal" value={amount} onChange={event => setAmount(event.target.value)} /></label>
      </fieldset>}
      <button type="button" disabled={busy || !loaded || (!intent && !valid)} onClick={() => void save()}>{intent ? "Reessayer la recompense conservee" : "Configurer la recompense"}</button>
    </>}
  </section>;
}
