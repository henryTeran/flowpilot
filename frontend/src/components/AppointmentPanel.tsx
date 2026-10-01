import { useEffect, useMemo, useState } from "react";
import type { Appointment, AppointmentAction, AppointmentCreatePayload, Employee, Service } from "../types";

interface AppointmentPanelProps {
  instituteId: string;
  employees: Employee[];
  services: Service[];
  appointments: Appointment[];
  onCreateAppointment: (payload: AppointmentCreatePayload) => Promise<void>;
  onAppointmentAction: (appointmentId: string, action: AppointmentAction) => Promise<void>;
}

const ACTIVE_APPOINTMENT_STATUSES = new Set(["scheduled", "confirmed", "arrived", "in_progress"]);
const FINAL_APPOINTMENT_STATUSES = new Set(["completed", "cancelled", "no_show"]);

export function AppointmentPanel({
  instituteId,
  employees,
  services,
  appointments,
  onCreateAppointment,
  onAppointmentAction,
}: AppointmentPanelProps) {
  const appointmentServices = services.filter((service) => service.status === "active");
  const availableEmployees = employees.filter((employee) => !["absent", "offline"].includes(employee.status));
  const initialSlot = useMemo(() => getNextRoundedSlot(), []);

  const [customerName, setCustomerName] = useState("");
  const [phone, setPhone] = useState("");
  const [serviceId, setServiceId] = useState(appointmentServices[0]?.id || "");
  const [employeeId, setEmployeeId] = useState(availableEmployees[0]?.id || "");
  const [date, setDate] = useState(initialSlot.date);
  const [time, setTime] = useState(initialSlot.time);
  const [searchTerm, setSearchTerm] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  useEffect(() => {
    if (!serviceId && appointmentServices.length > 0) {
      setServiceId(appointmentServices[0].id);
    }
  }, [appointmentServices, serviceId]);

  useEffect(() => {
    if (!employeeId && availableEmployees.length > 0) {
      setEmployeeId(availableEmployees[0].id);
    }
  }, [availableEmployees, employeeId]);

  const selectedService = services.find((service) => service.id === serviceId);
  const sortedAppointments = [...appointments].sort(
    (left, right) => new Date(left.start_time).getTime() - new Date(right.start_time).getTime(),
  );

  const activeAppointments = sortedAppointments.filter((appointment) => ACTIVE_APPOINTMENT_STATUSES.has(appointment.status));
  const historyAppointments = sortedAppointments.filter((appointment) => FINAL_APPOINTMENT_STATUSES.has(appointment.status));
  const normalizedSearch = searchTerm.trim().toLowerCase();
  const visibleActiveAppointments = normalizedSearch
    ? activeAppointments.filter((appointment) => matchesAppointmentSearch(appointment, employees, services, normalizedSearch))
    : activeAppointments;
  const visibleHistoryAppointments = normalizedSearch
    ? historyAppointments.filter((appointment) => matchesAppointmentSearch(appointment, employees, services, normalizedSearch))
    : historyAppointments;

  async function handleSubmit() {
    if (!instituteId || !serviceId || !employeeId || !customerName.trim() || !date || !time) return;

    setIsSubmitting(true);
    try {
      await onCreateAppointment({
        institute_id: instituteId,
        service_id: serviceId,
        employee_id: employeeId,
        customer_name: customerName.trim(),
        phone: phone.trim() || null,
        start_time: new Date(`${date}T${time}:00`).toISOString(),
      });
      setCustomerName("");
      setPhone("");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleAction(appointmentId: string, action: AppointmentAction) {
    setActionLoadingId(`${appointmentId}:${action}`);
    try {
      await onAppointmentAction(appointmentId, action);
    } finally {
      setActionLoadingId(null);
    }
  }

  return (
    <section className="appointment-panel phase9">
      <div className="appointment-form-card">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">Rendez-vous sous appel</p>
            <h2>Bloquer un créneau</h2>
          </div>
          <span className="counter-badge">{appointments.length} RDV aujourd’hui</span>
        </div>

        <div className="appointment-grid-form">
          <label>
            Cliente
            <input
              value={customerName}
              onChange={(event) => setCustomerName(event.target.value)}
              placeholder="Ex. Mme Dupont"
            />
          </label>

          <label>
            Téléphone
            <input
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="Optionnel"
            />
          </label>

          <label>
            Prestation
            <select value={serviceId} onChange={(event) => setServiceId(event.target.value)}>
              {appointmentServices.map((service) => (
                <option key={service.id} value={service.id}>
                  {service.name} · {service.duration_min} min
                </option>
              ))}
            </select>
          </label>

          <label>
            Collaboratrice
            <select value={employeeId} onChange={(event) => setEmployeeId(event.target.value)}>
              {availableEmployees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.first_name} · {translateEmployeeStatus(employee.status)}
                </option>
              ))}
            </select>
          </label>

          <label>
            Date
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>

          <label>
            Heure
            <input type="time" value={time} onChange={(event) => setTime(event.target.value)} />
          </label>
        </div>

        <div className="appointment-form-footer">
          <div className="selected-summary compact appointment-summary">
            <span>Durée bloquée</span>
            <strong>{selectedService?.duration_min || 0} min</strong>
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting || !customerName.trim() || !serviceId || !employeeId}
          >
            {isSubmitting ? "Création..." : "Créer RDV"}
          </button>
        </div>
      </div>

      <div className="appointment-list-card">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">Agenda du jour</p>
            <h2>RDV actifs</h2>
          </div>
          <span className="counter-badge violet">{visibleActiveAppointments.length} actif(s)</span>
        </div>

        <label className="appointment-search-wrapper" aria-label="Rechercher un rendez-vous">
          <input
            className="appointment-search"
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Client, prestation, collaboratrice…"
          />
        </label>

        {visibleActiveAppointments.length === 0 ? (
          <div className="empty-state">
            {normalizedSearch ? "Aucun rendez-vous ne correspond à la recherche." : "Aucun rendez-vous actif aujourd’hui."}
          </div>
        ) : (
          <div className="appointment-list">
            {visibleActiveAppointments.map((appointment) => (
              <AppointmentCard
                key={appointment.id}
                appointment={appointment}
                employees={employees}
                services={services}
                actionLoadingId={actionLoadingId}
                onAction={handleAction}
              />
            ))}
          </div>
        )}

        <div className="appointment-history-header">
          <p className="eyebrow">Historique RDV</p>
          <span>{visibleHistoryAppointments.length} clôturé(s) / annulé(s)</span>
        </div>

        {visibleHistoryAppointments.length > 0 && (
          <div className="appointment-list history">
            {visibleHistoryAppointments.map((appointment) => (
              <AppointmentCard
                key={appointment.id}
                appointment={appointment}
                employees={employees}
                services={services}
                actionLoadingId={actionLoadingId}
                onAction={handleAction}
                readonly
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function matchesAppointmentSearch(
  appointment: Appointment,
  employees: Employee[],
  services: Service[],
  searchTerm: string,
) {
  const employee = employees.find((item) => item.id === appointment.employee_id);
  const service = services.find((item) => item.id === appointment.service_id);
  const haystack = [
    appointment.customer_name,
    appointment.status,
    service?.name ?? "",
    employee?.first_name ?? "",
    formatTime(appointment.start_time),
  ].join(" ").toLowerCase();

  return haystack.includes(searchTerm);
}

function AppointmentCard({
  appointment,
  employees,
  services,
  actionLoadingId,
  onAction,
  readonly = false,
}: {
  appointment: Appointment;
  employees: Employee[];
  services: Service[];
  actionLoadingId: string | null;
  onAction: (appointmentId: string, action: AppointmentAction) => Promise<void>;
  readonly?: boolean;
}) {
  const service = services.find((item) => item.id === appointment.service_id);
  const employee = employees.find((item) => item.id === appointment.employee_id);
  const actions = getAvailableActions(appointment.status);

  return (
    <article className={`appointment-card status-${appointment.status} ${readonly ? "readonly" : ""}`}>
      <div className="appointment-card-main">
        <div>
          <strong>{formatTime(appointment.start_time)} · {appointment.customer_name}</strong>
          <span>{service?.name || "Prestation"} · {employee?.first_name || "Collaboratrice"}</span>
        </div>
        <small>{formatTime(appointment.start_time)} - {formatTime(appointment.end_time)}</small>
      </div>

      <span className={`appointment-status-badge ${appointment.status}`}>
        {translateAppointmentStatus(appointment.status)}
      </span>

      {!readonly && actions.length > 0 && (
        <div className="appointment-actions">
          {actions.map((action) => {
            const loading = actionLoadingId === `${appointment.id}:${action}`;
            return (
              <button
                key={action}
                type="button"
                className={`appointment-action ${action}`}
                onClick={() => onAction(appointment.id, action)}
                disabled={Boolean(actionLoadingId)}
              >
                {loading ? "..." : translateAppointmentAction(action)}
              </button>
            );
          })}
        </div>
      )}
    </article>
  );
}

function getAvailableActions(status: string): AppointmentAction[] {
  if (["scheduled", "confirmed"].includes(status)) {
    return ["arrive", "start", "no-show", "cancel"];
  }

  if (status === "arrived") {
    return ["start", "no-show", "cancel"];
  }

  if (status === "in_progress") {
    return ["complete"];
  }

  return [];
}

function getNextRoundedSlot() {
  const now = new Date();
  now.setMinutes(Math.ceil((now.getMinutes() + 10) / 15) * 15, 0, 0);
  return {
    date: now.toISOString().slice(0, 10),
    time: now.toTimeString().slice(0, 5),
  };
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("fr-CH", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function translateEmployeeStatus(status: string) {
  const labels: Record<string, string> = {
    available: "disponible",
    busy: "occupée",
    pause: "pause",
    absent: "absente",
    offline: "hors ligne",
    delayed: "retard",
  };
  return labels[status] || status;
}

function translateAppointmentStatus(status: string) {
  const labels: Record<string, string> = {
    scheduled: "Planifié",
    confirmed: "Confirmé",
    arrived: "Arrivée",
    in_progress: "En cours",
    completed: "Terminé",
    no_show: "Absente",
    cancelled: "Annulé",
  };
  return labels[status] || status;
}

function translateAppointmentAction(action: AppointmentAction) {
  const labels: Record<AppointmentAction, string> = {
    arrive: "Arrivée",
    start: "Démarrer",
    complete: "Terminer",
    "no-show": "Absente",
    cancel: "Annuler",
  };
  return labels[action];
}
