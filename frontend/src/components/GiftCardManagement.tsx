import { useEffect, useRef, useState } from "react";
import { ApiError, apiGet, apiPost, apiPut } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { readUtcDate } from "../api/dates";

type Currency = "CHF" | "EUR";
type Settings = { currency: Currency };
type IssuedCard = { id: string; code: string; initial_amount: string; currency: Currency; expires_at: string };
type IssueIntent = { amount: string; valid_days: number; reason: string; idempotency_key: string };

export function GiftCardManagement({ instituteId }: { instituteId: string }) {
  const [settings, setSettings] = useState<Settings>();
  const [choice, setChoice] = useState<Currency | "">("");
  const [loaded, setLoaded] = useState(false);
  const [amount, setAmount] = useState("");
  const [days, setDays] = useState("365");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [issued, setIssued] = useState<IssuedCard>();
  const [error, setError] = useState<string>();
  const epoch = useRef(0), reads = useRef(0), pending = useRef(false);
  const intent = useRef<IssueIntent | undefined>(undefined);
  const token = getAccessToken();
  const manager = getOperatorRole() === "responsable_institut";
  const subject = getOperatorSubject();
  const recoveryKey = subject ? `flowpilot.gift-issue:${encodeURIComponent(instituteId)}:${encodeURIComponent(subject)}` : undefined;
  const prefix = `/gift-cards/institutes/${encodeURIComponent(instituteId)}`;
  function capture() { const stamp = epoch.current; return () => stamp === epoch.current && token === getAccessToken(); }
  async function reload() {
    const current = capture(), request = ++reads.current;
    setLoaded(false);
    try {
      const value = await apiGet<Settings>(`${prefix}/settings`);
      if (!current() || request !== reads.current) return false;
      setSettings(value); setChoice(value.currency); setLoaded(true); return true;
    } catch (failure) {
      if (!current() || request !== reads.current) return false;
      if (failure instanceof ApiError && failure.status === 404) {
        setSettings(undefined); setChoice(""); setLoaded(true); return true;
      }
      // Missing configuration is a business 400; network errors must not enable issuance.
      if (failure instanceof ApiError && failure.status === 400 && /Configurer la devise/.test(failure.message)) {
        setSettings(undefined); setChoice(""); setLoaded(true); return true;
      }
      throw failure;
    }
  }
  useEffect(() => {
    epoch.current++; pending.current = false; intent.current = undefined;
    setLoaded(false); setSettings(undefined); setChoice(""); setIssued(undefined);
    setAmount(""); setDays("365"); setReason(""); setBusy(false); setUncertain(false); setError(undefined);
    if (manager && recoveryKey) {
      try {
        const saved = sessionStorage.getItem(recoveryKey);
        if (saved) {
          const value = JSON.parse(saved) as IssueIntent;
          if (typeof value.amount !== "string" || typeof value.reason !== "string" || typeof value.idempotency_key !== "string"
              || value.idempotency_key.length < 1 || value.idempotency_key.length > 120 || !Number.isInteger(value.valid_days)) throw new Error("Demande de récupération invalide");
          intent.current = value; setAmount(value.amount); setDays(String(value.valid_days)); setReason(value.reason); setUncertain(true);
        }
      } catch (failure) { setError(failure instanceof Error ? failure.message : "Récupération indisponible"); }
    }
    const current = capture();
    void reload().catch(failure => { if (current()) setError(String(failure.message || failure)); });
    return () => { epoch.current++; reads.current++; };
  }, [instituteId, token]);

  async function configure() {
    if (!manager || !choice || pending.current || uncertain || issued) return;
    const current = capture(); pending.current = true; reads.current++; setBusy(true); setError(undefined);
    try {
      await apiPut(`${prefix}/settings`, { currency: choice });
      if (!current()) return;
      if (!await reload()) return;
    } catch (failure) { if (current()) { setLoaded(false); setError(`${failure instanceof Error ? failure.message : "Configuration indisponible"}. Actualisez la devise avant toute émission.`); } }
    finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  async function issue() {
    if (!manager || !loaded || !settings || pending.current || issued || (!intent.current && !valid)) return;
    const current = capture();
    if (!intent.current) intent.current = { amount: normalizedAmount, valid_days: Number(days), reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    const payload = intent.current;
    pending.current = true; reads.current++; setBusy(true); setError(undefined);
    try {
      // Store only the replay intent, never the bearer code or a second access token.
      if (recoveryKey) sessionStorage.setItem(recoveryKey, JSON.stringify(payload));
      const value = await apiPost<IssuedCard>(prefix, payload);
      if (!current()) return;
      setIssued(value); setUncertain(false);
    } catch (failure) {
      if (!current()) return;
      const rejected = failure instanceof ApiError && failure.status >= 400 && failure.status < 500 && failure.status !== 408;
      if (rejected) { if (recoveryKey) sessionStorage.removeItem(recoveryKey); intent.current = undefined; setUncertain(false); }
      else setUncertain(true);
      setError(`${failure instanceof Error ? failure.message : "Émission indisponible"}${rejected ? "" : ". Réessayez la même émission pour récupérer le code sans créer un second crédit."}`);
    } finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  const normalizedAmount = amount.trim().replace(",", ".");
  const valid = /^\d{1,8}(\.\d{1,2})?$/.test(normalizedAmount) && Number(normalizedAmount) > 0 && Number(normalizedAmount) <= 99999999.99
    && Number.isInteger(Number(days)) && Number(days) >= 1 && Number(days) <= 3650 && reason.trim().length >= 3;
  return <section className="commerce-panel" aria-label="Gestion des cartes cadeaux">
    <h2>Cartes cadeaux</h2>
    {error && <p role="alert">{error}</p>}
    <p>{loaded ? settings ? `Devise configurée : ${settings.currency}` : "Devise à configurer" : "Devise non vérifiée"}</p>
    <button type="button" disabled={busy} onClick={() => { const current = capture(); setError(undefined); void reload().catch(failure => { if (current()) setError(String(failure.message || failure)); }); }}>Actualiser la devise</button>
    {manager ? <>
      <form onSubmit={event => { event.preventDefault(); void configure(); }}><fieldset disabled={busy || uncertain || !!issued}>
        <label>Devise des cartes cadeaux<select value={choice} onChange={event => setChoice(event.target.value as Currency | "")}><option value="">Choisir une devise</option><option value="CHF">CHF</option><option value="EUR">EUR</option></select></label>
        <p>La devise ne peut plus changer après émission d’une carte.</p>
        <button type="submit" disabled={!choice}>Enregistrer la devise</button>
      </fieldset></form>
      <p>Cette émission attribue du crédit. Elle ne constitue pas une vente encaissée. Carte au porteur valable dans cet institut.</p>
      <form onSubmit={event => { event.preventDefault(); void issue(); }}>
        <fieldset disabled={busy || uncertain || !!issued}>
          <label>Montant de la carte<input inputMode="decimal" value={amount} onChange={event => setAmount(event.target.value)} /></label>
          <label>Validité de la carte en jours<input type="number" min="1" max="3650" value={days} onChange={event => setDays(event.target.value)} /></label>
          <label>Motif d’émission<input maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label>
        </fieldset>
        <button type="submit" disabled={busy || !!issued || !loaded || !settings || (!uncertain && !valid)}>{uncertain ? "Récupérer cette émission" : "Émettre la carte cadeau"}</button>
      </form>
      {issued && <div role="status"><p>Carte émise : {issued.initial_amount} {issued.currency} · expiration {readUtcDate(issued.expires_at).toLocaleDateString("fr")}</p>
        <label>Code de la carte cadeau<textarea readOnly value={issued.code} /></label><p>Transmettez ce code à la bénéficiaire avant de créer une autre carte.</p>
        <button type="button" onClick={() => { if (recoveryKey) sessionStorage.removeItem(recoveryKey); intent.current = undefined; setIssued(undefined); setAmount(""); setReason(""); setError(undefined); }}>Nouvelle carte cadeau</button>
      </div>}
    </> : <p>La configuration et l’émission sont réservées à la responsable.</p>}
  </section>;
}
