import { useEffect, useMemo, useState } from "react";
import type { Appointment, AppointmentCreatePayload, Employee, Service } from "../types";

interface AppointmentPanelProps {
  instituteId: string;
  employees: Employee[];
  services: Service[];
  appointments: Appointment[];
  onCreateAppointment: (payload: AppointmentCreatePayload) => Promise<void>;
  onCancelAppointment: (appointmentId: string) => Promise<void>;
}

export function AppointmentPanel({
  instituteId,
  employees,
  services,
  appointments,
  onCreateAppointment,
  onCancelAppointment,
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
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  return (
    <section className="appointment-panel">
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
        <p className="eyebrow">Agenda du jour</p>
        <h2>RDV planifiés</h2>

        {sortedAppointments.length === 0 ? (
          <div className="empty-state">Aucun rendez-vous sous appel aujourd’hui.</div>
        ) : (
          <div className="appointment-list">
            {sortedAppointments.map((appointment) => {
              const service = services.find((item) => item.id === appointment.service_id);
              const employee = employees.find((item) => item.id === appointment.employee_id);
              return (
                <article className="appointment-card" key={appointment.id}>
                  <div>
                    <strong>{formatTime(appointment.start_time)} · {appointment.customer_name}</strong>
                    <span>{service?.name || "Prestation"} · {employee?.first_name || "Collaboratrice"}</span>
                  </div>
                  <button type="button" onClick={() => onCancelAppointment(appointment.id)}>
                    Annuler
                  </button>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
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
  };
  return labels[status] || status;
}
