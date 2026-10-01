import { useMemo, useState } from "react";
import type { Employee, QueueTicket, Service } from "../types";

type CompactQueueFilter = "all" | "waiting" | "assigned" | "in_progress" | "checkout" | "delayed";

interface CompactQueuePanelProps {
  tickets: QueueTicket[];
  services: Service[];
  employees: Employee[];
  selectedTicketId: string;
  ticketServiceMap: Record<string, string[]>;
  onTicketSelect: (ticketId: string) => void;
  onOpenTickets: () => void;
  onFinishActiveEmployeeSession: (employeeId: string) => void;
  onStartCheckout: (ticketId: string) => void;
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
  onStartCheckout,
}: CompactQueuePanelProps) {
  const [filter, setFilter] = useState<CompactQueueFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");

  const waitingTickets = tickets.filter((ticket) => ticket.status === "waiting");
  const assignedTickets = tickets.filter((ticket) => ticket.status === "assigned");
  const inProgressTickets = tickets.filter((ticket) => ticket.status === "in_progress");
  const checkoutTickets = tickets.filter((ticket) => ["ready_for_checkout", "in_checkout"].includes(ticket.status));
  const delayedTickets = tickets.filter((ticket) => {
    if (!ticket.assigned_employee_id) return false;

    const assignedEmployee = employees.find((employee) => employee.id === ticket.assigned_employee_id);
    return assignedEmployee?.status === "delayed" && ["assigned", "in_progress", "ready_for_checkout", "in_checkout"].includes(ticket.status);
  });
  const activeTickets = [...waitingTickets, ...assignedTickets, ...inProgressTickets, ...checkoutTickets];

  const filteredTickets = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    const nextTickets = filter === "all"
      ? activeTickets
      : filter === "checkout"
        ? activeTickets.filter((ticket) => ["ready_for_checkout", "in_checkout"].includes(ticket.status))
        : filter === "delayed"
          ? delayedTickets
          : activeTickets.filter((ticket) => ticket.status === filter);

    const searchedTickets = normalizedSearch
      ? nextTickets.filter((ticket) => matchesTicketSearch(ticket, services, employees, ticketServiceMap, normalizedSearch))
      : nextTickets;

    return [...searchedTickets].sort((left, right) => compareTicketPriority(left, right));
  }, [activeTickets, delayedTickets, employees, filter, searchTerm, services, ticketServiceMap]);

  const visibleTickets = filteredTickets.slice(0, 6);

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
        <span><strong>{checkoutTickets.length}</strong> en caisse</span>
        <span><strong>{delayedTickets.length}</strong> retard(s)</span>
      </div>

      <label className="compact-search-field" aria-label="Rechercher un ticket">
        <input
          className="compact-queue-search"
          type="search"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="Ticket, prestation, collaboratrice…"
        />
      </label>

      <div className="compact-filter-row" aria-label="Filtrer la file d’attente">
        {[
          { id: "all", label: "Tout" },
          { id: "waiting", label: "À prendre" },
          { id: "assigned", label: "Affectés" },
          { id: "in_progress", label: "En cours" },
          { id: "checkout", label: "Caisse" },
          { id: "delayed", label: "Retards" },
        ].map((chip) => (
          <button
            key={chip.id}
            type="button"
            className={`compact-filter-button ${filter === chip.id ? "active" : ""}`}
            onClick={() => setFilter(chip.id as CompactQueueFilter)}
          >
            {chip.label}
          </button>
        ))}
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
                <span className="compact-ticket-service">{serviceLabel || "Séance"}</span>
                {ticketServices.length > 1 && <small>{ticketServices.length} prestations · durée cumulée</small>}
                <small>{employee ? employee.first_name : formatTicketWait(ticket)}</small>

                {["ready_for_checkout", "in_checkout"].includes(ticket.status) ? (
                  <button
                    type="button"
                    className="compact-close-session"
                    onClick={(event) => {
                      event.stopPropagation();
                      onStartCheckout(ticket.id);
                    }}
                  >
                    Encaisser
                  </button>
                ) : ticket.status === "in_progress" && ticket.assigned_employee_id && (
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

      {filteredTickets.length > visibleTickets.length && (
        <button type="button" className="compact-show-more" onClick={onOpenTickets}>
          Voir {filteredTickets.length - visibleTickets.length} ticket(s) de plus
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

function matchesTicketSearch(
  ticket: QueueTicket,
  services: Service[],
  employees: Employee[],
  fallbackMap: Record<string, string[]>,
  searchTerm: string,
) {
  const ticketServices = getTicketServiceIds(ticket, fallbackMap)
    .map((serviceId) => services.find((service) => service.id === serviceId))
    .filter(Boolean) as Service[];
  const employee = employees.find((item) => item.id === ticket.assigned_employee_id);
  const haystack = [
    ticket.ticket_number,
    ticket.status,
    translateStatus(ticket.status),
    ...ticketServices.map((service) => service.name),
    employee?.first_name ?? "",
  ].join(" ").toLowerCase();

  return haystack.includes(searchTerm);
}

function formatTicketServices(ticketServices: Service[]) {
  if (ticketServices.length === 0) return "";
  if (ticketServices.length === 1) return ticketServices[0].name;
  const duration = ticketServices.reduce((sum, service) => sum + service.duration_min, 0);
  return `${ticketServices.length} prestations · ${duration} min`;
}

function formatTicketWait(ticket: QueueTicket) {
  if (ticket.status === "in_progress") return "En cabine";
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
    in_progress: "En cabine",
    completed: "Terminé",
    ready_for_checkout: "En caisse",
    in_checkout: "Caisse ouverte",
    paid: "Payé",
    cancelled: "Annulé",
  };
  return labels[status] || status;
}

function compareTicketPriority(left: QueueTicket, right: QueueTicket) {
  const priority = { waiting: 0, assigned: 1, in_progress: 2, ready_for_checkout: 3, in_checkout: 4 };
  const leftPriority = priority[left.status as keyof typeof priority] ?? 99;
  const rightPriority = priority[right.status as keyof typeof priority] ?? 99;

  if (leftPriority !== rightPriority) return leftPriority - rightPriority;

  const leftTime = left.estimated_start_time ? new Date(left.estimated_start_time).getTime() : Number.MAX_SAFE_INTEGER;
  const rightTime = right.estimated_start_time ? new Date(right.estimated_start_time).getTime() : Number.MAX_SAFE_INTEGER;

  return leftTime - rightTime;
}
