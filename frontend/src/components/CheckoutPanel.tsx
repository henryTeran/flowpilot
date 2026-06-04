import type { Employee, PaymentMethod, QueueTicket, Service } from "../types";

interface CheckoutPanelProps {
  ticket?: QueueTicket;
  services: Service[];
  employees: Employee[];
  cashierEmployee?: Employee;
  selectedPaymentMethod: PaymentMethod;
  onPaymentMethodChange: (method: PaymentMethod) => void;
  onPay: () => void;
  onClose: () => void;
}

const PAYMENT_METHODS: Array<{ value: PaymentMethod; label: string }> = [
  { value: "cb", label: "CB" },
  { value: "especes", label: "Espèces" },
  { value: "cheque", label: "Chèque" },
  { value: "carte_cadeau", label: "Carte cadeau" },
  { value: "mixte", label: "Mixte" },
];

export function CheckoutPanel({
  ticket,
  services,
  employees,
  cashierEmployee,
  selectedPaymentMethod,
  onPaymentMethodChange,
  onPay,
  onClose,
}: CheckoutPanelProps) {
  if (!ticket) {
    return (
      <div className="bm-checkout-empty">
        <strong>Aucun ticket sélectionné</strong>
        <p>Sélectionne un ticket prêt pour la caisse.</p>
      </div>
    );
  }

  const ticketLines = ticket.lines || [];
  const total = ticket.total_amount ?? ticketLines.reduce((sum, line) => sum + Number(line.total || 0), 0);
  const creator = employees.find((employee) => employee.id === ticket.created_by_id);
  const assigned = employees.find((employee) => employee.id === ticket.assigned_employee_id);

  return (
    <section className="bm-checkout-panel">
      <header className="bm-checkout-header">
        <div>
          <p>Encaissement</p>
          <h2>{ticket.ticket_number}</h2>
          <span>
            Créé par {creator?.first_name || "non renseigné"} · Prestation {assigned ? `par ${assigned.first_name}` : "à confirmer"}
          </span>
        </div>
        <button type="button" onClick={onClose}>Fermer</button>
      </header>

      <div className="bm-checkout-identity">
        <span>Collaboratrice caisse</span>
        <strong>{cashierEmployee?.first_name || "Identification obligatoire"}</strong>
        <small>Cette identité sera utilisée pour les chiffres / ventes.</small>
      </div>

      <div className="bm-checkout-lines">
        <div className="bm-checkout-line bm-checkout-line-head">
          <span>Prestation</span>
          <span>Exécutante</span>
          <span>Total</span>
        </div>

        {ticketLines.map((line) => {
          const service = services.find((item) => item.id === line.service_id);
          const performer = employees.find((employee) => employee.id === line.performed_by_employee_id);
          return (
            <div key={line.id} className="bm-checkout-line">
              <span>{service?.name || "Prestation"}</span>
              <span>{performer?.first_name || assigned?.first_name || cashierEmployee?.first_name || "À confirmer"}</span>
              <strong>{formatCurrency(Number(line.total || 0))}</strong>
            </div>
          );
        })}
      </div>

      <div className="bm-payment-methods">
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

      <footer className="bm-checkout-footer">
        <div>
          <span>Total à encaisser</span>
          <strong>{formatCurrency(total)}</strong>
        </div>
        <button type="button" className="bm-checkout-pay-button" onClick={onPay} disabled={!cashierEmployee}>
          Valider paiement
        </button>
      </footer>
    </section>
  );
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("fr-CH", {
    style: "currency",
    currency: "CHF",
  }).format(value);
}
