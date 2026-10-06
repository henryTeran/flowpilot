import { useState } from "react";
import type { ChiffresSummary } from "../types";

interface ChiffresPanelProps {
  chiffres?: ChiffresSummary;
  loading?: boolean;
  onRefresh: () => void | Promise<void>;
}

export function ChiffresPanel({ chiffres, loading, onRefresh }: ChiffresPanelProps) {
  const [selectedCurrency, setSelectedCurrency] = useState("");
  const groups = chiffres?.currency_groups || [];
  const group = groups.find(value => value.currency === selectedCurrency) || groups[0];
  const currency = group?.currency || chiffres?.currency;
  const rows = group?.rows || chiffres?.rows || [];
  const totals = group?.totals || chiffres?.totals;
  const display = (value: number | null | undefined) => formatAmount(currency ? value : null);

  return (
    <section className="bm-chiffres-screen">
      <header className="bm-chiffres-header">
        <div>
          <p>Module</p>
          <h2>Chiffres</h2>
          <span>{formatPeriod(chiffres?.period_start)}</span>
        </div>
        <button type="button" onClick={() => void onRefresh()} disabled={loading}>
          {loading ? "Chargement..." : "Rafraîchir"}
        </button>
      </header>

      {groups.length > 0 && <label>Devise du rapport<select value={group?.currency} onChange={event => setSelectedCurrency(event.target.value)}>
        {groups.map(value => <option key={value.currency} value={value.currency}>{value.currency}</option>)}
      </select></label>}
      {chiffres && !currency && <p>Devise non connue : les montants ne sont pas additionnés.</p>}
      {!!chiffres?.unknown_currency_tickets && <p>{chiffres.unknown_currency_tickets} ticket(s) sans devise connue, exclus des totaux monétaires.</p>}

      <div className="bm-chiffres-table" role="table" aria-label="Chiffres par collaboratrice">
        <div className="bm-chiffres-row bm-chiffres-row-head" role="row">
          <span>Collaboratrice</span>
          <span>Soins</span>
          <span>Ventes</span>
          <span>Contrats</span>
          <span>Pourboires</span>
          <span>Moyenne</span>
          <span>Total</span>
        </div>

        {rows.length === 0 && (
          <div className="bm-chiffres-empty">
            Aucun chiffre encaissé aujourd’hui. Les montants apparaîtront après paiement d’un ticket.
          </div>
        )}

        {rows.map((row) => (
          <div className="bm-chiffres-row" role="row" key={row.employee_id}>
            <strong>{row.employee_name}</strong>
            <span>{display(row.soins)}</span>
            <span>{display(row.ventes)}</span>
            <span>{display(row.contrats)}</span>
            <span>{display(row.pourboires)}</span>
            <span>{display(row.moyenne)}</span>
            <span className="bm-chiffres-total">{display(row.total)}</span>
          </div>
        ))}

        {totals && (
          <div className="bm-chiffres-row bm-chiffres-row-total" role="row">
            <strong>Total journée</strong>
            <span>{display(totals.soins)}</span>
            <span>{display(totals.ventes)}</span>
            <span>{display(totals.contrats)}</span>
            <span>{display(totals.pourboires)}</span>
            <span>{display(totals.moyenne)}</span>
            <span className="bm-chiffres-total">{display(totals.total)}</span>
          </div>
        )}
      </div>

      <footer className="bm-chiffres-note">
        Les chiffres sont imputés à la collaboratrice qui a réalisé la prestation ou validé l’encaissement,
        pas à la personne qui a seulement créé le ticket.
      </footer>
    </section>
  );
}

function formatAmount(value: number | null | undefined) {
  if (value === null || value === undefined) return "\u2014";
  const amount = value;
  return new Intl.NumberFormat("fr-CH", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatPeriod(value?: string) {
  if (!value) return "Journée en cours";
  return new Intl.DateTimeFormat("fr-CH", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  }).format(new Date(value));
}
