import { useMemo, useState } from "react";
import type { Employee, PaymentMethod, QueueTicket, Service } from "../types";

interface CheckoutPanelProps {
  ticket?: QueueTicket;
  services: Service[];
  employees: Employee[];
  cashierEmployee?: Employee;
  selectedPaymentMethod: PaymentMethod;
  onPaymentMethodChange: (method: PaymentMethod) => void;
  onAddService: (serviceId: string) => void;
  onRemoveLine: (lineId: string) => void;
  onPay: () => void;
  onClose: () => void;
  onCancelTicket?: (ticketId: string) => void;
  onReidentify?: () => void;
}

const PAYMENT_METHODS: Array<{ value: PaymentMethod; label: string }> = [
  { value: "cb", label: "CB" },
  { value: "especes", label: "esp." },
  { value: "cheque", label: "chq." },
];

export function CheckoutPanel({
  ticket,
  services,
  employees,
  cashierEmployee,
  selectedPaymentMethod,
  onPaymentMethodChange,
  onAddService,
  onRemoveLine,
  onPay,
  onClose,
  onCancelTicket,
  onReidentify,
}: CheckoutPanelProps) {
  const [serviceToAdd, setServiceToAdd] = useState("");
  const [printCustomerTicket, setPrintCustomerTicket] = useState(false);

  const orderedServices = useMemo(
    () => [...services].sort((a, b) => a.name.localeCompare(b.name, "fr")),
    [services],
  );

  if (!ticket) {
    return (
      <div className="bm-checkout-empty bm-checkout-clone-empty">
        <strong>Aucun ticket sélectionné</strong>
        <p>Sélectionne un ticket prêt pour la caisse.</p>
      </div>
    );
  }

  const ticketLines = ticket.lines || [];
  const total = ticket.total_amount ?? ticketLines.reduce((sum, line) => sum + Number(line.total || 0), 0);
  const creator = employees.find((employee) => employee.id === ticket.created_by_id);
  const assigned = employees.find((employee) => employee.id === ticket.assigned_employee_id);
  const canEditLines = ["ready_for_checkout", "in_checkout"].includes(ticket.status);

  function handleAddService() {
    if (!serviceToAdd) return;
    onAddService(serviceToAdd);
    setServiceToAdd("");
  }

  return (
    <section className="bm-checkout-clone">
      <main className="bm-checkout-main-card">
        <header className="bm-ticket-cash-header">
          <button type="button" className="bm-cash-back" onClick={onClose} aria-label="Retour">
            ‹
          </button>

          <div className="bm-cash-title-block">
            <h1>Ticket n°{formatTicketNumber(ticket.ticket_number)}</h1>
            <span>{formatTicketStatus(ticket.status)}</span>
          </div>

          <div className="bm-cash-top-actions">
            <button type="button" className="bm-cash-top-primary">
              Imprimer un recu provisoire
            </button>
            <button
              type="button"
              className="bm-cash-top-secondary"
              onClick={() => onCancelTicket?.(ticket.id)}
              disabled={!onCancelTicket || ticket.status === "paid"}
            >
              Clore en annulation
            </button>
          </div>
        </header>

        <section className="bm-customer-cash-card">
          <div className="bm-customer-avatar">
            <span>CL</span>
            <small>Dossier</small>
          </div>

          <div className="bm-customer-cash-info">
            <h2>{ticket.customer_id ? `Cliente ${ticket.customer_id}` : "Cliente de passage"}</h2>
            <div className="bm-customer-meta-grid">
              <span><strong>Reference</strong>{ticket.customer_id || "—"}</span>
              <span><strong>Segment</strong>{ticket.customer_id ? "Fidelisee" : "Passage"}</span>
              <span><strong>Arrivee</strong>{formatShortTime(ticket.arrival_time)}</span>
              <span><strong>Origine</strong>File institut</span>
              <span><strong>Dossier</strong>{ticket.ticket_number}</span>
            </div>
          </div>

          <button type="button" className="bm-subscription-link">
            Ouvrir la fiche cliente
          </button>
        </section>

        <section className="bm-cash-action-row">
          <button type="button">▦ Appliquer remise</button>
          <div className="bm-cash-add-service">
            <span>＋ Ajouter prestation</span>
            <select value={serviceToAdd} onChange={(event) => setServiceToAdd(event.target.value)} disabled={!canEditLines}>
              <option value="">Choisir une prestation à ajouter</option>
              {orderedServices.map((service) => (
                <option key={service.id} value={service.id}>
                  {service.name} · {service.duration_min} min · {formatCurrency(Number(service.price_passage || 0))}
                </option>
              ))}
            </select>
            <button type="button" onClick={handleAddService} disabled={!serviceToAdd || !canEditLines}>
              Ajouter
            </button>
          </div>
          <button type="button">▧ Ajouter article</button>
          <button type="button">▥ Bon cadeau</button>
        </section>

        <section className="bm-cash-lines-card">
          {ticketLines.length === 0 ? (
            <div className="bm-cash-empty-line">Aucune prestation sur ce ticket.</div>
          ) : (
            ticketLines.map((line) => {
              const service = services.find((item) => item.id === line.service_id);
              const removable = canEditLines && ticketLines.length > 1;
              return (
                <article key={line.id} className="bm-cash-line-item">
                  <div className="bm-cash-line-name">
                    <strong>{service?.name || "Prestation"}</strong>
                    <small>{line.duration_minutes} min</small>
                  </div>

                  <div className="bm-cash-line-price">
                    <span>Prix</span>
                    <strong>{formatNumber(Number(line.unit_price || line.total || 0))}</strong>
                  </div>

                  <div className="bm-cash-line-qty">
                    <span>Quantité</span>
                    <div>
                      <button type="button" disabled>−</button>
                      <strong>{line.quantity || 1}</strong>
                      <button type="button" disabled>＋</button>
                    </div>
                  </div>

                  <div className="bm-cash-line-total">
                    <span>Total</span>
                    <strong>{formatNumber(Number(line.total || 0))}</strong>
                  </div>

                  <button
                    type="button"
                    className="bm-cash-trash"
                    onClick={() => onRemoveLine(line.id)}
                    disabled={!removable}
                    title={removable ? "Retirer cette prestation" : "Impossible de retirer la dernière prestation"}
                  >
                    🗑
                  </button>
                </article>
              );
            })
          )}
        </section>

        <footer className="bm-cash-footer-note">
          Controle avant paiement: verifier les prestations, la duree et les montants du ticket.
        </footer>
      </main>

      <aside className="bm-checkout-side-card">
        <section className="bm-cash-audit-block">
          <span>Créé par</span>
          <strong>{creator?.first_name || "—"}</strong>
          <em>{formatShortTime(ticket.arrival_time)}</em>
        </section>

        <section className="bm-cash-audit-block">
          <span>Encaissé par</span>
          <strong>{cashierEmployee?.first_name || "—"}</strong>
          <em>{cashierEmployee ? "Identifiée" : "Identification requise"}</em>
        </section>

        <button type="button" className="bm-side-identify" onClick={onReidentify}>
          Je m’identifie ↻
        </button>

        <div className="bm-cash-total-box">
          <span>Total</span>
          <strong>{formatNumber(total)} CHF</strong>
        </div>

        <button type="button" className="bm-gift-sale-button">
          Creer un bon cadeau
        </button>

        <div className="bm-cash-payments-rounds">
          {PAYMENT_METHODS.map((method) => (
            <button
              key={method.value}
              type="button"
              className={selectedPaymentMethod === method.value ? "selected" : ""}
              onClick={() => onPaymentMethodChange(method.value)}
            >
              {method.label}
            </button>
          ))}
        </div>

        <label className="bm-print-toggle">
          <span>Imprimer ticket client</span>
          <input
            type="checkbox"
            checked={printCustomerTicket}
            onChange={(event) => setPrintCustomerTicket(event.target.checked)}
          />
        </label>

        <button type="button" className="bm-final-cash-button" onClick={onPay} disabled={!cashierEmployee}>
          Enregistrer le paiement
        </button>

        <small className="bm-side-helper">
          Prestations réalisées par {assigned?.first_name || "la collaboratrice de cabine"}. La caisse peut ajuster les lignes avant paiement.
        </small>
      </aside>
    </section>
  );
}

function formatTicketNumber(ticketNumber: string) {
  return ticketNumber.replace(/^D-?/i, "").replace(/^T-?/i, "");
}

function formatTicketStatus(status: string) {
  const labels: Record<string, string> = {
    waiting: "en attente",
    assigned: "affecté",
    in_service: "en cabine",
    ready_for_checkout: "en caisse",
    in_checkout: "encaissement",
    paid: "payé",
    cancelled: "annulé",
  };

  return labels[status] || status;
}

function formatShortTime(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit" });
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("fr-CH", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("fr-CH", {
    style: "currency",
    currency: "CHF",
  }).format(value);
}
