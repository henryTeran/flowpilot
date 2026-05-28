import type { Employee, PlanningAvailability, QueueTicket, Service, ServiceCategory } from "../types";

interface QueuePanelProps {
  tickets: QueueTicket[];
  services: Service[];
  categories: ServiceCategory[];
  employees: Employee[];
  availability?: PlanningAvailability;
  selectedCategoryId: string;
  selectedServiceId: string;
  selectedTicketId: string;
  selectedEmployeeId: string;
  ticketServiceMap: Record<string, string>;
  onCategoryChange: (id: string) => void;
  onServiceChange: (id: string) => void;
  onTicketChange: (id: string) => void;
  onEmployeeChange: (id: string) => void;
  onCreateTicket: () => void;
  onAssignTicket: () => void;
  onStartSession: () => void;
  onCancelTicket: (ticketId: string) => void;
}

const ACTIONABLE_TICKET_STATUSES = new Set(["waiting", "assigned"]);
const CANCELLABLE_TICKET_STATUSES = new Set(["waiting", "assigned"]);

export function QueuePanel({
  tickets,
  services,
  categories,
  employees,
  availability,
  selectedCategoryId,
  selectedServiceId,
  selectedTicketId,
  selectedEmployeeId,
  ticketServiceMap,
  onCategoryChange,
  onServiceChange,
  onTicketChange,
  onEmployeeChange,
  onCreateTicket,
  onAssignTicket,
  onStartSession,
  onCancelTicket,
}: QueuePanelProps) {
  const filteredServices = selectedCategoryId
    ? services.filter((service) => service.category_id === selectedCategoryId)
    : services;

  const selectedTicket = tickets.find((ticket) => ticket.id === selectedTicketId);
  const selectedTicketServiceId = selectedTicket ? ticketServiceMap[selectedTicket.id] : undefined;
  const selectedTicketService = services.find((service) => service.id === selectedTicketServiceId);
  const selectedService = services.find((service) => service.id === selectedServiceId);
  const selectedEmployee = employees.find((employee) => employee.id === selectedEmployeeId);
  const selectedEmployeeEffectiveStatus = selectedEmployee
    ? getEffectiveEmployeeStatus(selectedEmployee.id, selectedEmployee.status, availability)
    : undefined;
  const selectedTicketIsActionable = Boolean(selectedTicket && ACTIONABLE_TICKET_STATUSES.has(selectedTicket.status));
  const selectedTicketIsWaiting = selectedTicket?.status === "waiting";
  const selectedTicketIsAssigned = selectedTicket?.status === "assigned";
  const lockedEmployeeId = selectedTicket?.assigned_employee_id || "";
  const isLockedToAnotherEmployee = Boolean(
    lockedEmployeeId && selectedEmployeeId && lockedEmployeeId !== selectedEmployeeId,
  );
  const employeeCanStart = Boolean(selectedEmployee && selectedEmployeeEffectiveStatus === "available");
  const canAssignTicket = Boolean(selectedTicketIsWaiting && selectedEmployeeId && employeeCanStart);
  const canStartSession = Boolean(
    selectedTicketIsActionable &&
    selectedEmployeeId &&
    employeeCanStart &&
    (!lockedEmployeeId || lockedEmployeeId === selectedEmployeeId)
  );

  const waitingTickets = tickets.filter((ticket) => ticket.status === "waiting");
  const assignedTickets = tickets.filter((ticket) => ticket.status === "assigned");
  const inProgressTickets = tickets.filter((ticket) => ticket.status === "in_progress");
  const actionableTickets = tickets.filter((ticket) => ACTIONABLE_TICKET_STATUSES.has(ticket.status));

  return (
    <aside className="queue-panel">
      <section className="panel-card availability-card">
        <p className="eyebrow">Disponibilité live</p>
        <h2>{formatAvailabilityTitle(availability)}</h2>
        <p>{formatAvailabilityDescription(availability)}</p>
      </section>

      <section className="panel-card">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">Accueil</p>
            <h2>Créer un ticket</h2>
          </div>
          <span className="counter-badge">{waitingTickets.length + assignedTickets.length} à traiter</span>
        </div>

        <label>Catégorie</label>
        <select value={selectedCategoryId} onChange={(event) => onCategoryChange(event.target.value)}>
          <option value="">Toutes les catégories</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>{category.name}</option>
          ))}
        </select>

        <label>Prestation</label>
        <select value={selectedServiceId} onChange={(event) => onServiceChange(event.target.value)}>
          <option value="">Choisir une prestation</option>
          {filteredServices.map((service) => (
            <option key={service.id} value={service.id}>
              {service.name} · {service.duration_min} min
            </option>
          ))}
        </select>

        {selectedService && (
          <div className="selected-summary compact">
            <span>Durée standard</span>
            <strong>{selectedService.duration_min} min</strong>
          </div>
        )}

        <button className="primary-button" onClick={onCreateTicket} disabled={!selectedServiceId}>
          Ajouter à la file
        </button>
      </section>

      <section className="panel-card queue-list-card">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">File d’attente</p>
            <h2>Tickets actifs</h2>
          </div>
        </div>

        {tickets.length === 0 ? (
          <div className="empty-state">Aucun ticket actif.</div>
        ) : (
          <div className="ticket-list ticket-list-grouped">
            <TicketGroup
              title="À prendre"
              tickets={waitingTickets}
              empty="Aucune cliente en attente."
              services={services}
              employees={employees}
              selectedTicketId={selectedTicketId}
              ticketServiceMap={ticketServiceMap}
              onTicketChange={onTicketChange}
              onCancelTicket={onCancelTicket}
            />

            <TicketGroup
              title="Affectés"
              tickets={assignedTickets}
              empty="Aucun ticket affecté."
              services={services}
              employees={employees}
              selectedTicketId={selectedTicketId}
              ticketServiceMap={ticketServiceMap}
              onTicketChange={onTicketChange}
              onCancelTicket={onCancelTicket}
            />

            <TicketGroup
              title="En prestation"
              tickets={inProgressTickets}
              empty="Aucune prestation en cours depuis la file."
              services={services}
              employees={employees}
              selectedTicketId={selectedTicketId}
              ticketServiceMap={ticketServiceMap}
              onTicketChange={onTicketChange}
              onCancelTicket={onCancelTicket}
            />
          </div>
        )}
      </section>

      <section className="panel-card">
        <p className="eyebrow">Action rapide</p>
        <h2>Démarrer une prestation</h2>

        <label>Ticket sélectionné</label>
        <select value={selectedTicketId} onChange={(event) => onTicketChange(event.target.value)}>
          <option value="">Choisir un ticket</option>
          {actionableTickets.map((ticket) => (
            <option key={ticket.id} value={ticket.id}>{ticket.ticket_number} · {translateStatus(ticket.status)}</option>
          ))}
        </select>

        <label>Collaboratrice</label>
        <select
          value={selectedEmployeeId}
          onChange={(event) => onEmployeeChange(event.target.value)}
          disabled={Boolean(selectedTicketIsAssigned && lockedEmployeeId)}
        >
          <option value="">Choisir une collaboratrice</option>
          {employees.map((employee) => {
            const effectiveStatus = getEffectiveEmployeeStatus(employee.id, employee.status, availability);
            const disabled = effectiveStatus !== "available" || Boolean(lockedEmployeeId && lockedEmployeeId !== employee.id);
            return (
              <option key={employee.id} value={employee.id} disabled={disabled}>
                {employee.first_name} · {translateStatus(effectiveStatus)}
              </option>
            );
          })}
        </select>

        <div className="selected-summary">
          <span>Prestation</span>
          <strong>{selectedTicketService?.name || selectedService?.name || "Choisir une prestation"}</strong>
        </div>

        {selectedTicket && !selectedTicketIsActionable && (
          <p className="inline-warning">
            Ce ticket est {translateStatus(selectedTicket.status).toLowerCase()} : il se clôture depuis le bloc planning, pas depuis l’action rapide.
          </p>
        )}

        {selectedEmployee && selectedEmployeeEffectiveStatus !== "available" && (
          <p className="inline-warning">
            {selectedEmployee.first_name} est {translateStatus(selectedEmployeeEffectiveStatus || selectedEmployee.status).toLowerCase()} : termine la prestation ou attends la fin du RDV avant d’en démarrer une autre.
          </p>
        )}

        {isLockedToAnotherEmployee && (
          <p className="inline-warning">
            Ce ticket est déjà affecté à une autre collaboratrice. Il faut d’abord annuler ou modifier l’affectation côté métier.
          </p>
        )}

        <div className="button-row">
          <button className="secondary-button" onClick={onAssignTicket} disabled={!canAssignTicket}>
            Affecter
          </button>
          <button className="primary-button" onClick={onStartSession} disabled={!canStartSession}>
            Démarrer
          </button>
        </div>
      </section>
    </aside>
  );
}

interface TicketGroupProps {
  title: string;
  tickets: QueueTicket[];
  empty: string;
  services: Service[];
  employees: Employee[];
  selectedTicketId: string;
  ticketServiceMap: Record<string, string>;
  onTicketChange: (id: string) => void;
  onCancelTicket: (ticketId: string) => void;
}

function TicketGroup({
  title,
  tickets,
  empty,
  services,
  employees,
  selectedTicketId,
  ticketServiceMap,
  onTicketChange,
  onCancelTicket,
}: TicketGroupProps) {
  return (
    <div className="ticket-group">
      <div className="ticket-group-title">
        <span>{title}</span>
        <strong>{tickets.length}</strong>
      </div>

      {tickets.length === 0 ? (
        <div className="ticket-group-empty">{empty}</div>
      ) : (
        tickets.map((ticket) => {
          const service = services.find((item) => item.id === ticketServiceMap[ticket.id]);
          const employee = employees.find((item) => item.id === ticket.assigned_employee_id);
          const isLocked = ticket.status === "in_progress" || ticket.status === "completed";
          const canCancel = CANCELLABLE_TICKET_STATUSES.has(ticket.status);

          return (
            <div
              key={ticket.id}
              className={`ticket-card ${selectedTicketId === ticket.id ? "selected" : ""} ${isLocked ? "locked" : ""}`}
              onClick={() => onTicketChange(ticket.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") onTicketChange(ticket.id);
              }}
            >
              <div className="ticket-card-topline">
                <strong>{ticket.ticket_number}</strong>
                <span>{formatTicketWait(ticket)}</span>
              </div>
              <div className="ticket-card-body">
                <span>{service?.name || "Prestation à confirmer"}</span>
                <small>
                  {employee ? `Affecté à ${employee.first_name}` : "Non affecté"}
                </small>
              </div>
              <div className="ticket-card-footer">
                <span className={`status-badge status-badge-${ticket.status}`}>{translateStatus(ticket.status)}</span>
                {canCancel ? (
                  <button
                    className="ticket-mini-button"
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onCancelTicket(ticket.id);
                    }}
                  >
                    Annuler
                  </button>
                ) : (
                  <small className="ticket-hint">À clôturer dans le planning</small>
                )}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

function getEffectiveEmployeeStatus(
  employeeId: string,
  fallbackStatus: string,
  availability?: PlanningAvailability,
) {
  return availability?.employees.find((employee) => employee.employee_id === employeeId)?.employee_status || fallbackStatus;
}

function formatTicketWait(ticket: QueueTicket) {
  if (ticket.status === "in_progress") return "En cours";
  if (!ticket.estimated_start_time) return "Attente à calculer";
  const diffMs = new Date(ticket.estimated_start_time).getTime() - Date.now();
  const minutes = Math.max(0, Math.ceil(diffMs / 60000));
  if (minutes <= 0) return "Maintenant";
  return `~ ${minutes} min`;
}

function formatAvailabilityTitle(availability?: PlanningAvailability) {
  if (!availability) return "Calcul en cours";

  if (availability.wait_minutes === null || availability.wait_minutes === undefined) {
    return availability.active_sessions > 0
      ? "Disponibilité à confirmer"
      : "Aucune collaboratrice disponible";
  }

  if (availability.wait_minutes <= 0) {
    return `${availability.next_employee_name || "Disponible"} maintenant`;
  }

  return `${availability.wait_minutes} min avant prochain créneau`;
}

function formatAvailabilityDescription(availability?: PlanningAvailability) {
  if (!availability) return "Calcul en cours...";

  const delayedCount = availability.employees.filter(
    (employee) => employee.employee_status === "delayed"
  ).length;

  const delayText = delayedCount > 0 ? ` · ${delayedCount} retard à clôturer` : "";
  return `${availability.active_sessions} prestation(s) en cours · ${availability.waiting_tickets} ticket(s) à traiter${delayText}`;
}

function translateStatus(status: string) {
  const labels: Record<string, string> = {
    available: "Disponible",
    busy: "Occupée",
    pause: "Pause",
    absent: "Absente",
    offline: "Hors ligne",
    delayed: "Retard",
    waiting: "En attente",
    assigned: "Affecté",
    in_progress: "En cours",
    completed: "Terminé",
    cancelled: "Annulé",
  };
  return labels[status] || status;
}
