import type { Employee, QueueTicket, Service, ServiceCategory } from "../types";

interface QueuePanelProps {
  tickets: QueueTicket[];
  services: Service[];
  categories: ServiceCategory[];
  employees: Employee[];
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
}

export function QueuePanel({
  tickets,
  services,
  categories,
  employees,
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
}: QueuePanelProps) {
  const filteredServices = selectedCategoryId
    ? services.filter((service) => service.category_id === selectedCategoryId)
    : services;

  const selectedTicket = tickets.find((ticket) => ticket.id === selectedTicketId);
  const selectedTicketServiceId = selectedTicket ? ticketServiceMap[selectedTicket.id] : undefined;
  const selectedTicketService = services.find((service) => service.id === selectedTicketServiceId);

  return (
    <aside className="queue-panel">
      <section className="panel-card">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">Accueil</p>
            <h2>Créer un ticket</h2>
          </div>
          <span className="counter-badge">{tickets.length} en attente</span>
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

        <button className="primary-button" onClick={onCreateTicket} disabled={!selectedServiceId}>
          Ajouter à la file
        </button>
      </section>

      <section className="panel-card queue-list-card">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">File d’attente</p>
            <h2>Tickets sans RDV</h2>
          </div>
        </div>

        {tickets.length === 0 ? (
          <div className="empty-state">Aucun ticket en attente.</div>
        ) : (
          <div className="ticket-list">
            {tickets.map((ticket) => {
              const service = services.find((item) => item.id === ticketServiceMap[ticket.id]);
              const employee = employees.find((item) => item.id === ticket.assigned_employee_id);

              return (
                <button
                  key={ticket.id}
                  className={`ticket-card ${selectedTicketId === ticket.id ? "selected" : ""}`}
                  onClick={() => onTicketChange(ticket.id)}
                >
                  <strong>{ticket.ticket_number}</strong>
                  <span>{service?.name || "Prestation à confirmer"}</span>
                  <small>
                    {employee ? `Affecté à ${employee.first_name}` : "Non affecté"} · {ticket.status}
                  </small>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section className="panel-card">
        <p className="eyebrow">Action rapide</p>
        <h2>Démarrer une prestation</h2>

        <label>Ticket sélectionné</label>
        <select value={selectedTicketId} onChange={(event) => onTicketChange(event.target.value)}>
          <option value="">Choisir un ticket</option>
          {tickets.map((ticket) => (
            <option key={ticket.id} value={ticket.id}>{ticket.ticket_number}</option>
          ))}
        </select>

        <label>Collaboratrice</label>
        <select value={selectedEmployeeId} onChange={(event) => onEmployeeChange(event.target.value)}>
          <option value="">Choisir une collaboratrice</option>
          {employees.map((employee) => (
            <option key={employee.id} value={employee.id}>{employee.first_name} · {employee.status}</option>
          ))}
        </select>

        <div className="selected-summary">
          <span>Prestation</span>
          <strong>{selectedTicketService?.name || "Utilise la prestation actuellement sélectionnée"}</strong>
        </div>

        <div className="button-row">
          <button className="secondary-button" onClick={onAssignTicket} disabled={!selectedTicketId || !selectedEmployeeId}>
            Affecter
          </button>
          <button className="primary-button" onClick={onStartSession} disabled={!selectedTicketId || !selectedEmployeeId}>
            Démarrer
          </button>
        </div>
      </section>
    </aside>
  );
}
