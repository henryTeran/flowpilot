import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";

type Tier = { id: string; name: string; minimum_points: number; benefit_description: string };
type Intent = { name: string; minimum_points: number; benefit_description: string; idempotency_key: string };
function recover(key: string): Intent | undefined {
  try {
    const row = JSON.parse(sessionStorage.getItem(key) || "null");
    if (!row || typeof row.name !== "string" || !row.name.trim() || row.name.length > 120 ||
      !Number.isSafeInteger(row.minimum_points) || row.minimum_points < 0 || row.minimum_points > 1e9 ||
      typeof row.benefit_description !== "string" || row.benefit_description.trim().length < 3 || row.benefit_description.length > 240 ||
      typeof row.idempotency_key !== "string" || !row.idempotency_key || row.idempotency_key.length > 120) return;
    return { name: row.name, minimum_points: row.minimum_points, benefit_description: row.benefit_description, idempotency_key: row.idempotency_key };
  } catch { return; }
}
export function LoyaltyTiers({ instituteId }: { instituteId: string }) {
  return <LoyaltyTierForm key={JSON.stringify([instituteId, getAccessToken()])} instituteId={instituteId} />;
}
function LoyaltyTierForm({ instituteId }: { instituteId: string }) {
  const token = getAccessToken(), subject = getOperatorSubject();
  const manager = getOperatorRole() === "responsable_institut" && !!subject;
  const path = `/loyalty/institutes/${encodeURIComponent(instituteId)}/tiers`;
  const storageKey = `flowpilot.loyalty-tier:${encodeURIComponent(instituteId)}:${encodeURIComponent(subject || "")}`;
  const [tiers, setTiers] = useState<Tier[]>([]), [loaded, setLoaded] = useState(false);
  const [name, setName] = useState(""), [threshold, setThreshold] = useState(""), [description, setDescription] = useState("");
  const [intent, setIntent] = useState<Intent>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [message, setMessage] = useState<string>();
  const epoch = useRef(0), reads = useRef(0), pending = useRef(false);
  function capture() { const generation = epoch.current; return () => generation === epoch.current && token === getAccessToken(); }
  async function reload() {
    const current = capture(), request = ++reads.current;
    const rows = await apiGet<Tier[]>(path);
    if (!current() || request !== reads.current) return false;
    setTiers(rows); setLoaded(true); return true;
  }
  useEffect(() => {
    epoch.current++; pending.current = false; setBusy(false); setLoaded(false); setTiers([]); setError(undefined); setMessage(undefined);
    setName(""); setThreshold(""); setDescription(""); setIntent(manager ? recover(storageKey) : undefined);
    const current = capture();
    void reload().catch(reason => { if (current()) setError(reason instanceof Error ? reason.message : "Niveaux indisponibles"); });
    return () => { epoch.current++; };
  }, [instituteId, token]);
  async function refresh() {
    const current = capture();
    try { await reload(); } catch (reason) { if (current()) setError(String(reason)); }
  }
  async function save() {
    if (!manager || pending.current || !loaded) return;
    const row = intent || { name: name.trim(), minimum_points: Number(threshold), benefit_description: description.trim(), idempotency_key: crypto.randomUUID() };
    if (!row.name || !/^\d+$/.test(intent ? String(intent.minimum_points) : threshold) || !Number.isSafeInteger(row.minimum_points) || row.minimum_points > 1e9 || row.benefit_description.length < 3) return;
    const current = capture(); pending.current = true; reads.current++; setBusy(true); setError(undefined); setMessage(undefined); setIntent(row);
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(row));
      await apiPost(path, row);
      if (!current()) return;
      if (!await reload()) return;
      sessionStorage.removeItem(storageKey); setIntent(undefined); setName(""); setThreshold(""); setDescription(""); setMessage("Niveau configure");
    } catch (reason) {
      if (current()) {
        const rejected = reason instanceof ApiError && reason.status >= 400 && reason.status < 500;
        if (rejected) {
          sessionStorage.removeItem(storageKey); setIntent(undefined);
          setName(row.name); setThreshold(String(row.minimum_points)); setDescription(row.benefit_description);
        }
        setError(`${reason instanceof Error ? reason.message : "Operation indisponible"}${rejected ? "" : ". Reessayez la configuration conservee."}`);
      }
    } finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  return <section aria-label="Niveaux de fidelite"><h3>Niveaux de fidelite</h3>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {!loaded && <button type="button" onClick={() => void refresh()}>Actualiser les niveaux</button>}
    {tiers.map(tier => <p key={tier.id}><strong>{tier.name}</strong> ? des {tier.minimum_points} points ? {tier.benefit_description}</p>)}
    {loaded && !tiers.length && <p>Aucun niveau configure</p>}
    {manager && <><p>La description du niveau ne modifie pas le prix des prestations.</p>
      {intent ? <p>Configuration conservee : {intent.name} ? {intent.minimum_points} points ? {intent.benefit_description}</p> : <fieldset disabled={busy}>
        <label>Nom du niveau<input maxLength={120} value={name} onChange={event => setName(event.target.value)} /></label>
        <label>Seuil de points<input inputMode="numeric" value={threshold} onChange={event => setThreshold(event.target.value)} /></label>
        <label>Description du niveau<input maxLength={240} value={description} onChange={event => setDescription(event.target.value)} /></label>
      </fieldset>}
      <button type="button" disabled={busy || !loaded || (!intent && (!name.trim() || !/^\d+$/.test(threshold) || description.trim().length < 3))} onClick={() => void save()}>{intent ? "Reessayer le niveau conserve" : "Configurer le niveau"}</button>
    </>}
  </section>;
}
