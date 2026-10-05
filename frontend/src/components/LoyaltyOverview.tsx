import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken } from "../api/session";
import { readUtcDate } from "../api/dates";
import type { Customer } from "../types";

type Tier = { id: string; name: string; minimum_points: number; benefit_description: string };
type Balance = { customer_id: string; points: number; tier: Tier | null };
type Entry = { id: string; points: number; reason: string; actor_id: string; occurred_at: string };
type Redemption = { id: string; points_cost: number; quantity: number; occurred_at: string; reversed_at: string | null; reversal_reason: string | null };
type Facts = { scope: string; balance: Balance; entries: Entry[]; redemptions: Redemption[] };

export function LoyaltyOverview({ instituteId, customer }: { instituteId: string; customer?: Customer }) {
  const [storedFacts, setFacts] = useState<Facts>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const epoch = useRef(0);
  const sequence = useRef(0);
  const token = getAccessToken();
  const scope = JSON.stringify([instituteId, customer?.id, token]);
  const facts = storedFacts?.scope === scope ? storedFacts : undefined;
  async function load() {
    if (!customer) return;
    const generation = epoch.current, request = ++sequence.current;
    const current = () => generation === epoch.current && request === sequence.current && token === getAccessToken();
    setBusy(true); setFacts(undefined); setError(undefined);
    const path = `/loyalty/institutes/${encodeURIComponent(instituteId)}/customers/${encodeURIComponent(customer.id)}`;
    try {
      const [balance, entries, redemptions] = await Promise.all([
        apiGet<Balance>(path), apiGet<Entry[]>(`${path}/history`), apiGet<Redemption[]>(`${path}/redemptions`),
      ]);
      if (current()) setFacts({ scope, balance, entries, redemptions });
    } catch (reason) {
      if (current()) setError(reason instanceof Error ? reason.message : "Fidelite indisponible");
    } finally { if (current()) setBusy(false); }
  }
  useEffect(() => {
    epoch.current++; setFacts(undefined); setError(undefined); setBusy(false);
    void load();
    return () => { epoch.current++; };
  }, [instituteId, customer?.id, token]);
  return <section className="commerce-management" aria-label="Fidelite cliente">
    <h3>Fidelite{customer ? ` de ${customer.display_name}` : ""}</h3>
    {!customer ? <p>Selectionnez une cliente pour consulter sa fidelite.</p> : <>
      <button type="button" disabled={busy} onClick={() => void load()}>Actualiser la fidelite</button>
      {busy && <p role="status">Chargement de la fidelite</p>}
      {error && <p role="alert">{error}</p>}
      {facts && <>
        <p><strong>{facts.balance.points} points</strong></p>
        {facts.balance.tier ? <p>Niveau : {facts.balance.tier.name} ? {facts.balance.tier.benefit_description}</p> : <p>Aucun niveau atteint</p>}
        <details><summary>Historique des points ({facts.entries.length})</summary>
          {!facts.entries.length && <p>Aucun mouvement de points</p>}
          {facts.entries.map(row => <p key={row.id}>{readUtcDate(row.occurred_at).toLocaleString("fr")} ? {row.points > 0 ? "+" : ""}{row.points} points ? {row.reason}</p>)}
        </details>
        <details><summary>Recompenses utilisees ({facts.redemptions.length})</summary>
          {!facts.redemptions.length && <p>Aucune recompense utilisee</p>}
          {facts.redemptions.map(row => <p key={row.id}>{readUtcDate(row.occurred_at).toLocaleString("fr")} ? {row.points_cost} points ? {row.quantity} seance(s) ? {row.reversed_at ? `Annulee : ${row.reversal_reason}` : "Appliquee"}</p>)}
        </details>
      </>}
    </>}
  </section>;
}
