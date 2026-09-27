import type { ChiffresSummary } from "../types";

interface ChiffresPanelProps {
  chiffres?: ChiffresSummary;
  loading?: boolean;
  onRefresh: () => void | Promise<void>;
}

export function ChiffresPanel({ chiffres, loading, onRefresh }: ChiffresPanelProps) {
  const rows = chiffres?.rows || [];
  const totals = chiffres?.totals;

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
            <span>{formatAmount(row.soins)}</span>
            <span>{formatAmount(row.ventes)}</span>
            <span>{formatAmount(row.contrats)}</span>
            <span>{formatAmount(row.pourboires)}</span>
            <span>{formatAmount(row.moyenne)}</span>
            <span className="bm-chiffres-total">{formatAmount(row.total)}</span>
          </div>
        ))}

        {totals && (
          <div className="bm-chiffres-row bm-chiffres-row-total" role="row">
            <strong>Total journée</strong>
            <span>{formatAmount(totals.soins)}</span>
            <span>{formatAmount(totals.ventes)}</span>
            <span>{formatAmount(totals.contrats)}</span>
            <span>{formatAmount(totals.pourboires)}</span>
            <span>{formatAmount(totals.moyenne)}</span>
            <span className="bm-chiffres-total">{formatAmount(totals.total)}</span>
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
  const amount = Number(value || 0);
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
