import { useState } from "react";
import type { ChiffresSummary } from "../types";

interface ChiffresPanelProps {
  instituteId?: string;
  chiffres?: ChiffresSummary;
  loading?: boolean;
  onRefresh: () => void | Promise<void>;
}

export function ChiffresPanel(props: ChiffresPanelProps) {
  const instituteId = props.instituteId ?? props.chiffres?.institute_id ?? "";
  const chiffres = !props.loading && props.chiffres?.institute_id === instituteId ? props.chiffres : undefined;
  return <ScopedChiffresPanel key={instituteId} {...props} chiffres={chiffres} />;
}

function ScopedChiffresPanel({ chiffres, loading, onRefresh }: ChiffresPanelProps) {
  const [selectedCurrency, setSelectedCurrency] = useState("");
  const groups = chiffres?.currency_groups || [];
  const group = groups.find(value => value.currency === selectedCurrency) || groups[0];
  const currency = group?.currency || chiffres?.currency;
  const rows = group?.rows || chiffres?.rows || [];
  const totals = group?.totals || chiffres?.totals;
  const display = (value: string | null | undefined) => formatAmount(currency ? value : null);

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
            {loading ? "Lecture des chiffres…" : !chiffres ? "Chiffres non disponibles. Actualisez le rapport." : "Aucun chiffre encaissé aujourd’hui. Les montants apparaîtront après paiement d’un ticket."}
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

function formatAmount(value: string | null | undefined) {
  if (typeof value !== "string") return "\u2014";
  const parts = /^(-?)(\d+)\.(\d{2})$/.exec(value);
  if (!parts) return "\u2014";
  return `${parts[1]}${parts[2].replace(/\B(?=(\d{3})+(?!\d))/g, "\u202f")},${parts[3]}`;
}

function formatPeriod(value?: string) {
  if (!value) return "Journée en cours";
  return new Intl.DateTimeFormat("fr-CH", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  }).format(new Date(value));
}
