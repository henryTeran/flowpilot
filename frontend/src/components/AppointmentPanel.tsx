import { useEffect, useMemo, useRef, useState } from "react";
import type { Appointment, AppointmentAction, AppointmentCreatePayload, AppointmentUpdatePayload, Employee, Service } from "../types";
import { CustomerPicker } from "./CustomerPicker";
import { instituteInstants, instituteSlot, nextInstituteSlot } from "../institute-calendar";
import { instituteTimeZone, formatInstituteTime } from "../institute-time";
import { getAccessToken } from "../api/session";

interface AppointmentPanelProps {
  timezone?: string;
  instituteId: string;
  employees: Employee[];
  services: Service[];
  appointments: Appointment[];
  loadAppointments?: (instituteId: string, day: string) => Promise<Appointment[]>;
  onCreateAppointment: (payload: AppointmentCreatePayload) => Promise<void>;
  onUpdateAppointment?: (appointmentId: string, payload: AppointmentUpdatePayload) => Promise<void>;
  onAppointmentAction: (appointmentId: string, action: AppointmentAction) => Promise<void>;
}

const ACTIVE_APPOINTMENT_STATUSES = new Set(["scheduled", "confirmed", "arrived", "in_progress"]);
const FINAL_APPOINTMENT_STATUSES = new Set(["completed", "cancelled", "no_show"]);

export function AppointmentPanel(props: AppointmentPanelProps) {
  const zone = instituteTimeZone(props.timezone);
  return <View key={JSON.stringify([props.instituteId, zone, getAccessToken()])} {...props} timezone={zone} />;
}

function View({
  timezone = "UTC",
  instituteId,
  employees,
  services,
  appointments,
  loadAppointments,
  onCreateAppointment,
  onUpdateAppointment,
  onAppointmentAction,
}: AppointmentPanelProps) {
  const appointmentServices = services.filter((service) => service.status === "active");
  const availableEmployees = employees.filter((employee) => !["absent", "offline"].includes(employee.status));
  const initialSlot = useMemo(() => nextInstituteSlot(timezone), [timezone]);
  const [agendaDay, setAgendaDay] = useState(() => instituteSlot(new Date(), timezone)!.date);
  const [agenda, setAgenda] = useState<{ day: string; rows: Appointment[] }>();
  const [agendaError, setAgendaError] = useState<string>();
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!loadAppointments) return;
    let disposed = false;
    const token = getAccessToken();
    setAgenda(undefined);
    setAgendaError(undefined);
    const civilDate = new Date(`${agendaDay}T12:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(agendaDay) || agendaDay.startsWith("0000")
      || !Number.isFinite(civilDate.getTime()) || civilDate.toISOString().slice(0, 10) !== agendaDay) {
      setAgendaError("Choisissez une date valide.");
      return;
    }
    void loadAppointments(instituteId, agendaDay).then(rows => {
      if (disposed || token !== getAccessToken()) return;
      if (!Array.isArray(rows) || rows.some(row => !row || row.institute_id !== instituteId
        || ![row.id, row.service_id, row.employee_id, row.customer_name, row.status].every(value => typeof value === "string")
        || [row.customer_id, row.checkout_ticket_id, row.phone, row.notes].some(value => value != null && typeof value !== "string")
        || (!ACTIVE_APPOINTMENT_STATUSES.has(row.status) && !FINAL_APPOINTMENT_STATUSES.has(row.status))
        || instituteSlot(row.start_time, timezone)?.date !== agendaDay || !instituteSlot(row.end_time, timezone)
        || Date.parse(row.end_time) <= Date.parse(row.start_time)) || new Set(rows.map(row => row.id)).size !== rows.length) {
        throw new Error("Réponse de l’agenda invalide.");
      }
      setAgenda({ day: agendaDay, rows });
    }).catch(error => {
      if (!disposed && token === getAccessToken()) setAgendaError(error instanceof Error ? error.message : "Lecture de l’agenda impossible.");
    });
    return () => { disposed = true; };
  }, [agendaDay, instituteId, timezone, loadAppointments, appointments, revision]);
  const agendaAppointments = loadAppointments ? agenda?.day === agendaDay ? agenda.rows : [] : appointments;

  const [customerName, setCustomerName] = useState("");
  const [customerId, setCustomerId] = useState<string>();
  const [phone, setPhone] = useState("");
  const [serviceId, setServiceId] = useState(appointmentServices[0]?.id || "");
  const [employeeId, setEmployeeId] = useState(availableEmployees[0]?.id || "");
  const [date, setDate] = useState(initialSlot.date);
  const [time, setTime] = useState(initialSlot.time);
  const [occurrence, setOccurrence] = useState(initialSlot.instant);
  const [original, setOriginal] = useState<{ date: string; time: string; instant: string; fold: string }>();
  const candidates = useMemo(() => instituteInstants(date, time, timezone), [date, time, timezone]);
  const selectedInstant = candidates.length === 1 ? candidates[0] : candidates.includes(occurrence) ? occurrence : undefined;
  const [searchTerm, setSearchTerm] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const creationIntent = useRef<{ facts: string; key: string } | null>(null);

  useEffect(() => { setEditingId(null); setFormError(null); setCustomerName(""); setPhone(""); }, [instituteId]);

  function editAppointment(appointment: Appointment) {
    if (isSubmitting || actionLoadingId) return;
    const slot = instituteSlot(appointment.start_time, timezone);
    if (!slot) { setFormError("Horaire du rendez-vous a verifier"); return; }
    const fold = instituteInstants(slot.date, slot.time, timezone).find(value => Math.abs(Date.parse(value) - Date.parse(appointment.start_time)) < 60000) || "";
    setOccurrence(fold);
    setOriginal({ date: slot.date, time: slot.time, instant: appointment.start_time, fold });
    setEditingId(appointment.id);
    setCustomerName(appointment.customer_name);
    setCustomerId(appointment.customer_id || undefined);
    setPhone(appointment.phone || "");
    setServiceId(appointment.service_id);
    setEmployeeId(appointment.employee_id);
    setDate(slot.date);
    setTime(slot.time);
    setFormError(null);
  }

  useEffect(() => {
    if (!serviceId && appointmentServices.length > 0) {
      setServiceId(appointmentServices[0].id);
    }
  }, [appointmentServices, serviceId]);

  useEffect(() => {
    if (!availableEmployees.some(employee => employee.id === employeeId) && availableEmployees.length > 0) {
      setEmployeeId(availableEmployees[0].id);
    }
  }, [availableEmployees, employeeId]);

  const selectedService = services.find((service) => service.id === serviceId);
  const sortedAppointments = [...agendaAppointments].sort(
    (left, right) => new Date(left.start_time).getTime() - new Date(right.start_time).getTime(),
  );

  const activeAppointments = sortedAppointments.filter((appointment) => ACTIVE_APPOINTMENT_STATUSES.has(appointment.status));
  const historyAppointments = sortedAppointments.filter((appointment) => FINAL_APPOINTMENT_STATUSES.has(appointment.status));
  const availableQuickEmployees = availableEmployees.slice(0, 4);
  const normalizedSearch = searchTerm.trim().toLowerCase();
  const visibleActiveAppointments = normalizedSearch
    ? activeAppointments.filter((appointment) => matchesAppointmentSearch(appointment, employees, services, normalizedSearch, timezone))
    : activeAppointments;
  const visibleHistoryAppointments = normalizedSearch
    ? historyAppointments.filter((appointment) => matchesAppointmentSearch(appointment, employees, services, normalizedSearch, timezone))
    : historyAppointments;

  async function handleSubmit() {
    if (isSubmitting || actionLoadingId) return;
    if (!instituteId || !serviceId || !employeeId || !customerName.trim() || !date || !time) return;

    if (!selectedInstant) {
      setFormError(candidates.length > 1 ? "Cette heure se repete : choisissez son occurrence." : "Cette date ou heure n'existe pas dans le fuseau de l'institut.");
      return;
    }
    setIsSubmitting(true);
    setFormError(null);
    try {
      const payload = {
        institute_id: instituteId,
        service_id: serviceId,
        employee_id: employeeId,
        customer_name: customerName.trim(),
        customer_id: customerId || null,
        phone: phone.trim() || null,
        start_time: original && original.date === date && original.time === time && original.fold === selectedInstant
          ? original.instant : selectedInstant,
      };
      if (editingId && onUpdateAppointment) {
        const { institute_id, ...changes } = payload;
        await onUpdateAppointment(editingId, changes);
      } else {
        const facts = JSON.stringify(payload);
        if (creationIntent.current?.facts !== facts) {
          creationIntent.current = { facts, key: crypto.randomUUID() };
        }
        await onCreateAppointment({ ...payload, idempotency_key: creationIntent.current.key });
        creationIntent.current = null;
      }
      setEditingId(null);
      setOriginal(undefined);
      setCustomerName("");
      setCustomerId(undefined);
      setPhone("");
      setAgendaDay(date);
      setRevision(value => value + 1);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer le rendez-vous");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleAction(appointmentId: string, action: AppointmentAction) {
    if (isSubmitting || actionLoadingId) return;
    setActionLoadingId(`${appointmentId}:${action}`);
    try {
      await onAppointmentAction(appointmentId, action);
      setRevision(value => value + 1);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de modifier le rendez-vous");
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

        <p className="appointment-zone">Dates et heures de l’institut : {timezone}</p>
        <fieldset className="appointment-fields" aria-label="Données du rendez-vous" disabled={isSubmitting || Boolean(actionLoadingId)}>
        <CustomerPicker key={`${instituteId}:${editingId || "new"}`} instituteId={instituteId}
          selected={customerId ? { id: customerId, display_name: customerName, phone: phone || null } : undefined}
          clearLabel="Autre cliente" onSelect={customer => {
            setCustomerId(customer?.id); setCustomerName(customer?.display_name || ""); setPhone(customer?.phone || "");
          }} />
        <div className="appointment-grid-form">
          <label>
            Cliente
            <input
              value={customerName}
              onChange={(event) => { setCustomerName(event.target.value); setCustomerId(undefined); }}
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

          {availableQuickEmployees.length > 0 && (
            <div className="appointment-quick-employee-block">
              <span className="quick-employee-label">Prochaine dispo</span>
              <div className="quick-employee-list">
                {availableQuickEmployees.map((employee) => (
                  <button
                    key={employee.id}
                    type="button"
                    className={`quick-employee-chip ${employeeId === employee.id ? "active" : ""}`}
                    onClick={() => setEmployeeId(employee.id)}
                  >
                    {employee.first_name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <label>
            Date
            <input type="date" value={date} onChange={(event) => { setDate(event.target.value); setOccurrence(""); setFormError(null); }} />
          </label>

          <label>
            Heure
            <input type="time" value={time} onChange={(event) => { setTime(event.target.value); setOccurrence(""); setFormError(null); }} />
          </label>
        </div>

        {candidates.length > 1 && <label className="appointment-occurrence">
          Heure du changement d’heure
          <select aria-label="Occurrence de l’heure" value={selectedInstant || ""} onChange={event => { setOccurrence(event.target.value); setFormError(null); }}>
            <option value="">Choisir la première ou la seconde occurrence</option>
            {candidates.map((value, index) => <option key={value} value={value}>
              {index === 0 ? "Première" : "Seconde"} occurrence ({new Intl.DateTimeFormat("fr-CH", { timeZone: timezone, timeZoneName: "shortOffset" }).formatToParts(new Date(value)).find(part => part.type === "timeZoneName")?.value})
            </option>)}
          </select>
        </label>}
        </fieldset>
        <div className="appointment-form-footer">
          <div className="selected-summary compact appointment-summary">
            <span>Durée bloquée</span>
            <strong>{selectedService?.duration_min || 0} min</strong>
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting || Boolean(actionLoadingId) || !customerName.trim() || !serviceId || !employeeId}
          >
            {isSubmitting ? "Enregistrement..." : editingId ? "Enregistrer les modifications" : "Créer RDV"}
          </button>
        </div>
        {editingId && <button type="button" disabled={isSubmitting || Boolean(actionLoadingId)} onClick={() => { setEditingId(null); setOriginal(undefined); setCustomerId(undefined); setCustomerName(""); setPhone(""); }}>Annuler la modification</button>}
        {formError && <p role="alert">{formError}</p>}
      </div>

      <div className="appointment-list-card">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">Agenda · {agendaDay}</p>
            <h2>RDV actifs</h2>
          </div>
          <span className="counter-badge violet">{visibleActiveAppointments.length} actif(s)</span>
        </div>

        {loadAppointments && <label className="appointment-search-wrapper">Date de l’agenda
          <input className="appointment-search" type="date" aria-label="Date de l’agenda" value={agendaDay}
            disabled={isSubmitting || Boolean(actionLoadingId)} onChange={event => setAgendaDay(event.target.value)} />
        </label>}
        {loadAppointments && !agenda && !agendaError && <p role="status">Lecture de l’agenda…</p>}
        {agendaError && <div role="alert">{agendaError} <button type="button" onClick={() => setRevision(value => value + 1)}>Réessayer</button></div>}

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
            {normalizedSearch ? "Aucun rendez-vous ne correspond à la recherche." : loadAppointments && !agenda ? "Agenda indisponible." : "Aucun rendez-vous actif à cette date."}
          </div>
        ) : (
          <div className="appointment-list">
            {visibleActiveAppointments.map((appointment) => (
              <AppointmentCard
                key={appointment.id}
                appointment={appointment}
                timezone={timezone}
                employees={employees}
                services={services}
                actionLoadingId={isSubmitting ? "submitting" : actionLoadingId}
                onAction={handleAction}
                onEdit={onUpdateAppointment ? editAppointment : undefined}
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
                timezone={timezone}
                employees={employees}
                services={services}
                actionLoadingId={isSubmitting ? "submitting" : actionLoadingId}
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
  timezone: string,
) {
  const employee = employees.find((item) => item.id === appointment.employee_id);
  const service = services.find((item) => item.id === appointment.service_id);
  const haystack = [
    appointment.customer_name,
    appointment.status,
    service?.name ?? "",
    employee?.first_name ?? "",
    formatInstituteTime(appointment.start_time, timezone),
  ].join(" ").toLowerCase();

  return haystack.includes(searchTerm);
}

function agendaTime(value: string, timezone: string) {
  const label = formatInstituteTime(value, timezone);
  const slot = instituteSlot(value, timezone);
  if (!slot || instituteInstants(slot.date, slot.time, timezone).length < 2) return label;
  const offset = new Intl.DateTimeFormat("fr-CH", { timeZone: timezone, timeZoneName: "shortOffset" })
    .formatToParts(new Date(value)).find(part => part.type === "timeZoneName")?.value;
  return `${label} (${offset})`;
}

function AppointmentCard({
  timezone,
  appointment,
  employees,
  services,
  actionLoadingId,
  onAction,
  onEdit,
  readonly = false,
}: {
  timezone: string;
  appointment: Appointment;
  employees: Employee[];
  services: Service[];
  actionLoadingId: string | null;
  onAction: (appointmentId: string, action: AppointmentAction) => Promise<void>;
  onEdit?: (appointment: Appointment) => void;
  readonly?: boolean;
}) {
  const service = services.find((item) => item.id === appointment.service_id);
  const employee = employees.find((item) => item.id === appointment.employee_id);
  const actions = getAvailableActions(appointment.status);

  return (
    <article className={`appointment-card status-${appointment.status} ${readonly ? "readonly" : ""}`}>
      <div className="appointment-card-main">
        <div>
          <strong>{agendaTime(appointment.start_time, timezone)} · {appointment.customer_name}</strong>
          <span>{service?.name || "Prestation"} · {employee?.first_name || "Collaboratrice"}</span>
        </div>
        <small>{agendaTime(appointment.start_time, timezone)} - {agendaTime(appointment.end_time, timezone)}</small>
      </div>

      <span className={`appointment-status-badge ${appointment.status}`}>
        {translateAppointmentStatus(appointment.status)}
      </span>

      {!readonly && actions.length > 0 && (
        <div className="appointment-actions">
          {onEdit && ["scheduled", "confirmed"].includes(appointment.status) && <button type="button" disabled={Boolean(actionLoadingId)} onClick={() => onEdit(appointment)}>Modifier</button>}
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
  if (status === "scheduled") return ["confirm", "arrive", "start", "no-show", "cancel"];
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
    confirm: "Confirmer",
    arrive: "Arrivée",
    start: "Démarrer",
    complete: "Terminer",
    "no-show": "Absente",
    cancel: "Annuler",
  };
  return labels[action];
}
