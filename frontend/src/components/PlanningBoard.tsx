import type { CSSProperties } from "react";
import type { Appointment, Employee, PlanningAvailability, PlanningDay, Service, ServiceSession } from "../types";

interface PlanningBoardProps {
  planning?: PlanningDay;
  employees: Employee[];
  services: Service[];
  appointments: Appointment[];
  availability?: PlanningAvailability;
  onFinishSession: (sessionId: string) => void;
  onExtendSession: (sessionId: string, minutes: number) => void;
  onChangeEmployeeStatus: (employeeId: string, status: string) => void;
}

const BUSINESS_START_HOUR = 9;
const BUSINESS_END_HOUR = 20;
const ACTIVE_STATUSES = new Set(["planned", "in_progress", "extended", "delayed"]);

export function PlanningBoard({
  planning,
  employees,
  services,
  appointments,
  availability,
  onFinishSession,
  onExtendSession,
  onChangeEmployeeStatus,
}: PlanningBoardProps) {
  const rows = planning?.rows || employees.map((employee) => ({
    employee_id: employee.id,
    employee_name: employee.first_name,
    employee_status: employee.status,
    sessions: [] as ServiceSession[],
  }));

  const timelineRange = getTimelineRange();
  const totalMinutes = (timelineRange.endHour - timelineRange.startHour) * 60;
  const nowPosition = getNowPositionPercent(timelineRange);
  const hourMarks = Array.from(
    { length: timelineRange.endHour - timelineRange.startHour + 1 },
    (_, index) => timelineRange.startHour + index,
  );
  const isDemoOutOfHours = isOutsideBusinessHours(new Date());

  return (
    <main className="planning-shell">
      <div className="kpi-strip">
        <KpiCard label="Collaboratrices actives" value={rows.length} />
        <KpiCard label="Prestations en cours" value={availability?.active_sessions ?? countActiveSessions(rows)} />
        <KpiCard label="Prochain créneau" value={formatNextSlot(availability)} />
      </div>

      {isDemoOutOfHours && (
        <div className="demo-clock-banner">
          Mode démo hors horaires : l’axe démarre autour de l’heure réelle pour que le curseur et les blocs restent alignés.
        </div>
      )}

      <section className="planning-card">
        <div className="timeline-header">
          <div className="employee-header">Collaboratrice</div>
          <div className="time-axis">
            {hourMarks.map((hour) => {
              const left = ((hour - timelineRange.startHour) / (timelineRange.endHour - timelineRange.startHour)) * 100;
              return (
                <span className="time-axis-hour" key={hour} style={{ left: `${left}%` }}>
                  {String(hour).padStart(2, "0")}:00
                </span>
              );
            })}
          </div>
        </div>

        <div className="timeline-body">
          {rows.map((row, rowIndex) => {
            const availabilityRow = availability?.employees.find((item) => item.employee_id === row.employee_id);
            const rowAppointments = appointments.filter(
              (appointment) => appointment.employee_id === row.employee_id && appointment.status !== "cancelled",
            );
            const hasActiveSession = row.sessions.some((session) => ACTIVE_STATUSES.has(session.status));
            const hasAppointment = rowAppointments.length > 0;
            const displayStatus = availabilityRow?.employee_status || row.employee_status;
            const isBlockedByActiveSession = Boolean(availabilityRow?.active_session_id);

            return (
              <div className="timeline-row" key={row.employee_id}>
                <div className="employee-cell">
                  <div>
                    <strong>{row.employee_name}</strong>
                    <span className={`status-dot ${displayStatus}`}>{translateStatus(displayStatus)}</span>
                  </div>

                  <small className={`employee-availability ${displayStatus === "delayed" ? "warning" : ""}`}>
                    {formatEmployeeAvailability(availabilityRow)}
                  </small>

                  <div className="employee-actions">
                    <button
                      type="button"
                      onClick={() => onChangeEmployeeStatus(row.employee_id, "pause")}
                      disabled={isBlockedByActiveSession}
                      title={isBlockedByActiveSession ? "Terminer la prestation avant de changer le statut" : "Mettre en pause"}
                    >
                      Pause
                    </button>
                    <button
                      type="button"
                      onClick={() => onChangeEmployeeStatus(row.employee_id, "available")}
                      disabled={isBlockedByActiveSession}
                      title={isBlockedByActiveSession ? "Terminer la prestation avant de rendre disponible" : "Rendre disponible"}
                    >
                      Dispo
                    </button>
                  </div>
                </div>

                <div
                  className="slots-cell"
                  style={{ "--hour-count": timelineRange.endHour - timelineRange.startHour } as CSSProperties}
                >
                  <div className="row-now-cursor" style={{ left: `${nowPosition}%` }}>
                    {rowIndex === 0 && <span>Maintenant</span>}
                  </div>

                  {Array.from({ length: timelineRange.endHour - timelineRange.startHour }, (_, index) => (
                    <div className="hour-grid-line" key={index} />
                  ))}

                  {!hasActiveSession && !hasAppointment && <div className="free-label">Libre</div>}

                  {row.sessions.map((session) => {
                    const service = services.find((item) => item.id === session.service_id);
                    const block = getSessionBlock(session, timelineRange, totalMinutes);
                    if (!block) return null;

                    const sessionMeta = getSessionMeta(session);
                    const canEdit = ACTIVE_STATUSES.has(session.status);
                    const serviceName = service?.name || "Prestation";
                    const detailText = `${serviceName} · ${session.duration_minutes} min · ${sessionMeta.label} · ${sessionMeta.timeLabel}`;
                    const isCompact = block.width < 10 || session.duration_minutes <= 15;
                    const isMicro = block.width < 5;

                    return (
                      <article
                        key={session.id}
                        className={`session-block ${sessionMeta.visualStatus} ${isCompact ? "compact" : ""} ${isMicro ? "micro" : ""}`}
                        style={{ left: `${block.left}%`, width: `${block.width}%` }}
                        title={detailText}
                        aria-label={detailText}
                        data-session-title={serviceName}
                        data-session-meta={`${session.duration_minutes} min · ${sessionMeta.label} · ${sessionMeta.timeLabel}`}
                      >
                        <div className="session-content">
                          <strong>{serviceName}</strong>
                          <span>{session.duration_minutes} min · {sessionMeta.label}</span>
                          <small>{sessionMeta.timeLabel}</small>
                        </div>

                        {isCompact && (
                          <div className="compact-session-info" aria-hidden="true">
                            <strong>{getShortServiceName(serviceName)}</strong>
                            <span>{session.duration_minutes} min</span>
                          </div>
                        )}

                        {canEdit && (
                          <div className="session-actions">
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                onExtendSession(session.id, 5);
                              }}
                            >
                              +5
                            </button>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                onExtendSession(session.id, 10);
                              }}
                            >
                              +10
                            </button>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                onFinishSession(session.id);
                              }}
                            >
                              Fin
                            </button>
                          </div>
                        )}
                      </article>
                    );
                  })}

                  {rowAppointments.map((appointment) => {
                    const service = services.find((item) => item.id === appointment.service_id);
                    const block = getAppointmentBlock(appointment, timelineRange, totalMinutes);
                    if (!block) return null;

                    const serviceName = service?.name || "Rendez-vous";
                    const detailText = `${appointment.customer_name} · ${serviceName} · ${formatClock(appointment.start_time)}-${formatClock(appointment.end_time)}`;
                    const isCompact = block.width < 10;

                    return (
                      <article
                        key={appointment.id}
                        className={`appointment-block ${isCompact ? "compact" : ""}`}
                        style={{ left: `${block.left}%`, width: `${block.width}%` }}
                        title={detailText}
                        aria-label={detailText}
                        data-appointment-title={appointment.customer_name}
                        data-appointment-meta={`${serviceName} · ${formatClock(appointment.start_time)}`}
                      >
                        <div className="appointment-block-content">
                          <strong>{appointment.customer_name}</strong>
                          <span>{serviceName}</span>
                          <small>{formatClock(appointment.start_time)} · RDV</small>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </main>
  );
}


function getShortServiceName(name: string) {
  const normalized = name.trim();
  if (normalized.length <= 10) return normalized;

  const words = normalized.split(/\s+/);
  if (words.length >= 2) {
    const initials = words.slice(0, 2).map((word) => word[0]?.toUpperCase()).join("");
    return initials || normalized.slice(0, 8);
  }

  return `${normalized.slice(0, 8)}…`;
}

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="kpi-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function countActiveSessions(rows: Array<{ sessions: ServiceSession[] }>) {
  return rows.reduce((sum, row) => sum + row.sessions.filter((session) => ACTIVE_STATUSES.has(session.status)).length, 0);
}

interface TimelineRange {
  startHour: number;
  endHour: number;
}

function getTimelineRange(): TimelineRange {
  const now = new Date();

  if (!isOutsideBusinessHours(now)) {
    return { startHour: BUSINESS_START_HOUR, endHour: BUSINESS_END_HOUR };
  }

  // En démo hors horaires, on centre la vue autour de l'heure réelle.
  // Exemple à 02:38 : axe 01:00 -> 06:00, curseur réellement à 02:38.
  const currentHour = now.getHours();
  const startHour = Math.max(0, currentHour - 1);
  const endHour = Math.min(24, Math.max(startHour + 5, currentHour + 3));

  return { startHour, endHour };
}

function isOutsideBusinessHours(date: Date) {
  const hour = date.getHours();
  return hour < BUSINESS_START_HOUR || hour >= BUSINESS_END_HOUR;
}

function getSessionBlock(session: ServiceSession, range: TimelineRange, totalMinutes: number) {
  const start = new Date(session.start_time);
  const end = new Date(session.real_end_time || session.planned_end_time);
  const startMinutes = start.getHours() * 60 + start.getMinutes();
  const endMinutes = end.getHours() * 60 + end.getMinutes();
  const rangeStart = range.startHour * 60;
  const rangeEnd = range.endHour * 60;

  if (endMinutes <= rangeStart || startMinutes >= rangeEnd) {
    return null;
  }

  const visibleStart = Math.max(startMinutes, rangeStart);
  const visibleEnd = Math.min(endMinutes, rangeEnd);
  const left = ((visibleStart - rangeStart) / totalMinutes) * 100;
  const proportionalWidth = ((visibleEnd - visibleStart) / totalMinutes) * 100;
  const width = Math.min(Math.max(proportionalWidth, 1.25), 100 - left);

  return {
    left: clamp(left, 0, 100),
    width: clamp(width, 1.25, 100),
  };
}

function getAppointmentBlock(appointment: Appointment, range: TimelineRange, totalMinutes: number) {
  const start = new Date(appointment.start_time);
  const end = new Date(appointment.end_time);
  const startMinutes = start.getHours() * 60 + start.getMinutes();
  const endMinutes = end.getHours() * 60 + end.getMinutes();
  const rangeStart = range.startHour * 60;
  const rangeEnd = range.endHour * 60;

  if (endMinutes <= rangeStart || startMinutes >= rangeEnd) {
    return null;
  }

  const visibleStart = Math.max(startMinutes, rangeStart);
  const visibleEnd = Math.min(endMinutes, rangeEnd);
  const left = ((visibleStart - rangeStart) / totalMinutes) * 100;
  const proportionalWidth = ((visibleEnd - visibleStart) / totalMinutes) * 100;
  const width = Math.min(Math.max(proportionalWidth, 1.6), 100 - left);

  return {
    left: clamp(left, 0, 100),
    width: clamp(width, 1.6, 100),
  };
}

function formatClock(value: string) {
  return new Intl.DateTimeFormat("fr-CH", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function getSessionMeta(session: ServiceSession) {
  const now = Date.now();
  const end = new Date(session.planned_end_time).getTime();
  const diffMinutes = Math.ceil((end - now) / 60000);
  const isLate = ACTIVE_STATUSES.has(session.status) && diffMinutes < 0;

  if (session.status === "completed") {
    return {
      visualStatus: "completed",
      label: "Terminée",
      timeLabel: "Prestation clôturée",
    };
  }

  if (isLate) {
    return {
      visualStatus: "delayed",
      label: "Retard",
      timeLabel: `retard ${Math.abs(diffMinutes)} min`,
    };
  }

  if (session.status === "extended") {
    return {
      visualStatus: "extended",
      label: "Prolongée",
      timeLabel: `reste ${Math.max(diffMinutes, 0)} min`,
    };
  }

  return {
    visualStatus: session.status,
    label: translateStatus(session.status),
    timeLabel: `reste ${Math.max(diffMinutes, 0)} min`,
  };
}

function getNowPositionPercent(range: TimelineRange) {
  const now = new Date();
  const minutes = now.getHours() * 60 + now.getMinutes();
  const rangeStart = range.startHour * 60;
  const rangeEnd = range.endHour * 60;
  const percent = ((minutes - rangeStart) / (rangeEnd - rangeStart)) * 100;
  return clamp(percent, 0, 100);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function formatNextSlot(availability?: PlanningAvailability) {
  if (!availability || availability.wait_minutes === null || availability.wait_minutes === undefined) return "—";
  if (availability.wait_minutes <= 0) return "Maintenant";
  return `${availability.wait_minutes} min`;
}

function formatEmployeeAvailability(row?: PlanningAvailability["employees"][number]) {
  if (!row) return "Disponibilité à calculer";

  if (row.active_session_id && !row.available_at) {
    return "En retard — terminer la prestation";
  }

  if (row.wait_minutes === null || row.wait_minutes === undefined) {
    return "Indisponible";
  }

  if (row.wait_minutes <= 0) return "Disponible maintenant";
  return `Disponible dans ${row.wait_minutes} min`;
}

function translateStatus(status: string) {
  const labels: Record<string, string> = {
    available: "Disponible",
    busy: "Occupée",
    pause: "Pause",
    absent: "Absente",
    offline: "Hors ligne",
    delayed: "Retard",
    planned: "Planifiée",
    in_progress: "En cours",
    extended: "Prolongée",
    completed: "Terminée",
    cancelled: "Annulée",
    waiting: "En attente",
    assigned: "Affectée",
  };
  return labels[status] || status;
}
