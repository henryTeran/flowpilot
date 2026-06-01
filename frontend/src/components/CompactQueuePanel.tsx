import type { Employee, QueueTicket, Service } from "../types";

interface CompactQueuePanelProps {
  tickets: QueueTicket[];
  services: Service[];
  employees: Employee[];
  selectedTicketId: string;
  ticketServiceMap: Record<string, string[]>;
  onTicketSelect: (ticketId: string) => void;
  onOpenTickets: () => void;
  onFinishActiveEmployeeSession: (employeeId: string) => void;
}

export function CompactQueuePanel({
  tickets,
  services,
  employees,
  selectedTicketId,
  ticketServiceMap,
  onTicketSelect,
  onOpenTickets,
  onFinishActiveEmployeeSession,
}: CompactQueuePanelProps) {
  const waitingTickets = tickets.filter((ticket) => ticket.status === "waiting");
  const assignedTickets = tickets.filter((ticket) => ticket.status === "assigned");
  const inProgressTickets = tickets.filter((ticket) => ticket.status === "in_progress");
  const activeTickets = [...waitingTickets, ...assignedTickets, ...inProgressTickets];
  const visibleTickets = activeTickets.slice(0, 6);

  return (
    <aside className="compact-queue-card">
      <div className="compact-queue-header">
        <div>
          <p className="eyebrow">File d’attente</p>
          <h2>{activeTickets.length} ticket(s) actif(s)</h2>
        </div>
        <button type="button" onClick={onOpenTickets}>Gérer</button>
      </div>

      <div className="compact-queue-counters">
        <span><strong>{waitingTickets.length}</strong> à prendre</span>
        <span><strong>{assignedTickets.length}</strong> affecté(s)</span>
        <span><strong>{inProgressTickets.length}</strong> en cours</span>
      </div>

      {visibleTickets.length === 0 ? (
        <div className="compact-empty-state">Aucune cliente en attente.</div>
      ) : (
        <div className="compact-ticket-list">
          {visibleTickets.map((ticket) => {
            const ticketServices = getTicketServiceIds(ticket, ticketServiceMap)
              .map((serviceId) => services.find((item) => item.id === serviceId))
              .filter(Boolean) as Service[];
            const serviceLabel = formatTicketServices(ticketServices);
            const employee = employees.find((item) => item.id === ticket.assigned_employee_id);

            return (
              <div
                key={ticket.id}
                className={`compact-ticket ${selectedTicketId === ticket.id ? "selected" : ""}`}
                onClick={() => onTicketSelect(ticket.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") onTicketSelect(ticket.id);
                }}
              >
                <div className="compact-ticket-topline">
                  <strong>{ticket.ticket_number}</strong>
                  <span className={`status-badge status-badge-${ticket.status}`}>{translateStatus(ticket.status)}</span>
                </div>
                <span className="compact-ticket-service">{serviceLabel || "Prestation"}</span>
                {ticketServices.length > 1 && <small>{ticketServices.length} prestations</small>}
                <small>{employee ? employee.first_name : formatTicketWait(ticket)}</small>

                {ticket.status === "in_progress" && ticket.assigned_employee_id && (
                  <button
                    type="button"
                    className="compact-close-session"
                    onClick={(event) => {
                      event.stopPropagation();
                      onFinishActiveEmployeeSession(ticket.assigned_employee_id!);
                    }}
                  >
                    Clôturer
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {activeTickets.length > visibleTickets.length && (
        <button type="button" className="compact-show-more" onClick={onOpenTickets}>
          Voir {activeTickets.length - visibleTickets.length} ticket(s) de plus
        </button>
      )}
    </aside>
  );
}


function getTicketServiceIds(ticket: QueueTicket | undefined, fallbackMap: Record<string, string[]>) {
  if (!ticket) return [];

  if (ticket.lines && ticket.lines.length > 0) {
    return ticket.lines.map((line) => line.service_id);
  }

  return fallbackMap[ticket.id] || [];
}

function formatTicketServices(ticketServices: Service[]) {
  if (ticketServices.length === 0) return "";
  if (ticketServices.length === 1) return ticketServices[0].name;
  return ticketServices.map((service) => service.name).join(" + ");
}

function formatTicketWait(ticket: QueueTicket) {
  if (ticket.status === "in_progress") return "En cours";
  if (!ticket.estimated_start_time) return "Attente à calculer";
  const diffMs = new Date(ticket.estimated_start_time).getTime() - Date.now();
  const minutes = Math.max(0, Math.ceil(diffMs / 60000));
  if (minutes <= 0) return "Maintenant";
  return `~ ${minutes} min`;
}

function translateStatus(status: string) {
  const labels: Record<string, string> = {
    waiting: "À prendre",
    assigned: "Affecté",
    in_progress: "En cours",
    completed: "Terminé",
    cancelled: "Annulé",
  };
  return labels[status] || status;
}
