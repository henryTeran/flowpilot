import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";

const amounts = ["captured", "applied", "unapplied", "refunded", "refund_reserved", "net_confirmed"] as const;
type Account = { provider: string; account_id: string; currency: string } & Record<typeof amounts[number], string>;
type Snapshot = { institute_id: string; accounts: Account[] };
const labels: Record<typeof amounts[number], string> = {
  captured: "Encaissements confirmés", applied: "Appliqués en caisse", unapplied: "À appliquer en caisse",
  refunded: "Remboursements confirmés", refund_reserved: "Remboursements réservés", net_confirmed: "Net confirmé",
};
function valid(value: Snapshot, institute: string) {
  if (!value || value.institute_id !== institute || !Array.isArray(value.accounts)) return false;
  const seen = new Set<string>();
  return value.accounts.every(row => {
    if (!row || typeof row.provider !== "string" || !row.provider.trim() || typeof row.account_id !== "string" || !row.account_id.trim() ||
        !["CHF", "EUR"].includes(row.currency) || amounts.some(key => typeof row[key] !== "string" || !/^\d+\.\d{2}$/.test(row[key]))) return false;
    // Validate the recorded ledger relationships in exact cents, without deriving
    // a replacement amount or publishing a partially inconsistent account.
    const cents = (key: typeof amounts[number]) => BigInt(row[key].replace(".", ""));
    if (cents("captured") !== cents("applied") + cents("unapplied") ||
        cents("captured") !== cents("refunded") + cents("net_confirmed") ||
        cents("refunded") + cents("refund_reserved") > cents("applied")) return false;
    const key = JSON.stringify([row.provider, row.account_id, row.currency]);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
const display = (value: string) => value.replace(".", ",");

export function PaymentCashflows({ instituteId }: { instituteId: string }) {
  const token = getAccessToken();
  if (!instituteId || getOperatorRole() !== "responsable_institut") return null;
  return <ScopedCashflows key={JSON.stringify([instituteId, token])} instituteId={instituteId} token={token} />;
}
function ScopedCashflows({ instituteId, token }: { instituteId: string; token: string | null }) {
  const [snapshot, setSnapshot] = useState<Snapshot>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0);
  async function load() {
    const request = ++sequence.current;
    const current = () => mounted.current && request === sequence.current && token === getAccessToken();
    setSnapshot(undefined); setError(undefined); setLoading(true);
    try {
      const result = await apiGet<Snapshot>(`/payments/institutes/${encodeURIComponent(instituteId)}/cashflows`);
      if (!valid(result, instituteId)) throw new Error("Lecture des flux de paiement incomplète");
      if (current()) setSnapshot(result);
    } catch (reason) {
      if (current()) setError(reason instanceof Error ? reason.message : "Flux de paiement indisponibles");
    } finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, []);
  return <section className="bm-payment-history" aria-label="Flux des paiements prestataire">
    <h3>Flux des paiements prestataire</h3>
    <p>Cumul des opérations enregistrées, par compte et devise. Ces montants ne représentent pas les versements bancaires, frais ou taxes.</p>
    <button type="button" disabled={loading} onClick={() => void load()}>Actualiser les flux</button>
    {loading && <p>Lecture des flux…</p>}
    {error && <p role="alert">{error}</p>}
    {snapshot && !snapshot.accounts.length && <p>Aucun flux prestataire enregistré.</p>}
    {snapshot?.accounts.map(row => <div key={JSON.stringify([row.provider, row.account_id, row.currency])}>
      <h4>{row.provider} · {row.account_id} · {row.currency}</h4>
      <dl>{amounts.map(key => <div key={key}><dt>{labels[key]}</dt><dd>{display(row[key])} {row.currency}</dd></div>)}</dl>
    </div>)}
  </section>;
}
