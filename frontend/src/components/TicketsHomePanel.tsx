import type { Employee, QueueTicket, Service } from "../types";

type TicketStats = {
  waitingCount: number;
  waitingAmount: number;
  checkoutCount: number;
  checkoutAmount: number;
  salesCount: number;
  salesAmount: number;
};

interface TicketsHomePanelProps {
  tickets: QueueTicket[];
  services: Service[];
  employees: Employee[];
  ticketStats: TicketStats;
  onCreateTicket: () => void;
  onManageTicket: (ticket: QueueTicket) => void;
  onRefresh: () => void | Promise<void>;
}

export function TicketsHomePanel({
  tickets,
  services,
  employees,
  ticketStats,
  onCreateTicket,
  onManageTicket,
  onRefresh,
}: TicketsHomePanelProps) {
  const visibleTickets = tickets.filter((ticket) => !["cancelled", "paid", "completed"].includes(ticket.status));

  return (
    <section className="bm-tickets-page" aria-label="Module Tickets">
      <header className="bm-tickets-header-clone">
        <h2>TICKETS</h2>
        <button type="button" className="bm-tickets-refresh" onClick={() => void onRefresh()}>
          Actualiser
        </button>
      </header>

      <div className="bm-ticket-counter-row" aria-label="Compteurs tickets">
        <TicketCounterCard title="En attente" count={ticketStats.waitingCount} amount={ticketStats.waitingAmount} active />
        <TicketCounterCard title="En caisse" count={ticketStats.checkoutCount} amount={ticketStats.checkoutAmount} />
        <TicketCounterCard title="Ventes" count={ticketStats.salesCount} amount={ticketStats.salesAmount} />
      </div>

      <div className="bm-ticket-create-row">
        <button type="button" className="bm-ticket-create-clone" onClick={onCreateTicket}>
          + Créer un nouveau ticket
        </button>
      </div>

      <div className="bm-ticket-list-clone">
        {visibleTickets.length === 0 ? (
          <div className="bm-ticket-empty-clone">
            Aucun ticket actif pour le moment.
          </div>
        ) : (
          visibleTickets.map((ticket) => (
            <TicketRow
              key={ticket.id}
              ticket={ticket}
              services={services}
              employees={employees}
              onManage={() => onManageTicket(ticket)}
            />
          ))
        )}
      </div>
    </section>
  );
}

function TicketCounterCard({ title, count, amount, active = false }: { title: string; count: number; amount: number; active?: boolean }) {
  return (
    <article className={`bm-ticket-counter-card ${active ? "active" : ""}`}>
      <div className="bm-ticket-counter-badge">{count}</div>
      <div>
        <strong>{title}</strong>
        <span>{formatPrice(amount)}</span>
      </div>
    </article>
  );
}

function TicketRow({
  ticket,
  services,
  employees,
  onManage,
}: {
  ticket: QueueTicket;
  services: Service[];
  employees: Employee[];
  onManage: () => void;
}) {
  const employee = employees.find((item) => item.id === ticket.assigned_employee_id);
  const lines = ticket.lines || [];
  const total = ticket.total_amount ?? lines.reduce((sum, line) => sum + (line.total ?? 0), 0);
  const servicesLabel = lines.length > 0
    ? lines.map((line) => services.find((service) => service.id === line.service_id)?.name || "Prestation").join(" + ")
    : "Passage";

  return (
    <article className="bm-ticket-row-clone">
      <div className="bm-ticket-avatar-clone" aria-hidden="true">
        {getAvatarInitial(ticket)}
      </div>

      <div className="bm-ticket-client-clone">
        <span>{formatTicketKind(ticket)}</span>
        <strong>{formatCustomer(ticket)}</strong>
        <small>0 Points</small>
      </div>

      <div className="bm-ticket-meta-clone">
        <span>Ticket N°</span>
        <strong>{ticket.ticket_number}</strong>
      </div>

      <div className="bm-ticket-meta-clone wide">
        <span>Prestations</span>
        <strong>{servicesLabel}</strong>
      </div>

      <div className="bm-ticket-amount-grid">
        <Metric label="Soins" value={total} />
        <Metric label="Ventes" value={0} />
        <Metric label="NC" value={0} />
        <Metric label="Total" value={total} strong />
      </div>

      <div className="bm-ticket-action-zone">
        <button type="button" className="bm-ticket-manage-button" onClick={onManage}>
          Encaisser / Modifier
        </button>
        <small>{formatTicketTime(ticket)} / {employee?.first_name || "—"}</small>
      </div>
    </article>
  );
}

function Metric({ label, value, strong = false }: { label: string; value: number; strong?: boolean }) {
  return (
    <div className={strong ? "strong" : ""}>
      <span>{label}</span>
      <b>{formatPrice(value)}</b>
    </div>
  );
}

function formatPrice(value: number) {
  return `${value.toFixed(2)} CHF`;
}

function formatTicketTime(ticket: QueueTicket) {
  try {
    return new Intl.DateTimeFormat("fr-CH", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(ticket.arrival_time));
  } catch {
    return "--:--";
  }
}

function formatCustomer(ticket: QueueTicket) {
  if (ticket.customer_id) return `Cliente ${ticket.customer_id.slice(0, 5)}`;
  return "PASSAGE";
}

function formatTicketKind(ticket: QueueTicket) {
  if (["ready_for_checkout", "in_checkout", "checkout"].includes(ticket.status)) return "En caisse";
  if (["in_service", "in_progress"].includes(ticket.status)) return "En cabine";
  if (ticket.status === "assigned") return "Affecté";
  return "Passage";
}

function getAvatarInitial(ticket: QueueTicket) {
  const label = formatCustomer(ticket);
  return label.slice(0, 1).toUpperCase();
}
