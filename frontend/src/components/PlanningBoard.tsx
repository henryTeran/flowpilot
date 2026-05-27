import type { Employee, PlanningDay, Service, ServiceSession } from "../types";

interface PlanningBoardProps {
  planning?: PlanningDay;
  employees: Employee[];
  services: Service[];
  onFinishSession: (sessionId: string) => void;
  onExtendSession: (sessionId: string, minutes: number) => void;
}

const DAY_START_HOUR = 9;
const DAY_END_HOUR = 20;
const TOTAL_MINUTES = (DAY_END_HOUR - DAY_START_HOUR) * 60;

export function PlanningBoard({ planning, employees, services, onFinishSession, onExtendSession }: PlanningBoardProps) {
  const nowPosition = getNowPositionPercent();
  const rows = planning?.rows || employees.map((employee) => ({
    employee_id: employee.id,
    employee_name: employee.first_name,
    employee_status: employee.status,
    sessions: [] as ServiceSession[],
  }));

  return (
    <main className="planning-shell">
      <div className="kpi-strip">
        <KpiCard label="Collaboratrices actives" value={rows.length} />
        <KpiCard label="Prestations en cours" value={rows.reduce((sum, row) => sum + row.sessions.filter((session) => session.status === "in_progress" || session.status === "extended").length, 0)} />
        <KpiCard label="Créneaux visibles" value="09:00 - 20:00" />
      </div>

      <section className="planning-card">
        <div className="timeline-header">
          <div className="employee-header">Collaboratrice</div>
          <div className="time-axis">
            {Array.from({ length: DAY_END_HOUR - DAY_START_HOUR + 1 }, (_, index) => DAY_START_HOUR + index).map((hour) => (
              <span key={hour}>{String(hour).padStart(2, "0")}:00</span>
            ))}
          </div>
        </div>

        <div className="timeline-body">
          <div className="now-cursor" style={{ left: `calc(210px + ${nowPosition}%)` }}>
            <span>Maintenant</span>
          </div>

          {rows.map((row) => (
            <div className="timeline-row" key={row.employee_id}>
              <div className="employee-cell">
                <strong>{row.employee_name}</strong>
                <span className={`status-dot ${row.employee_status}`}>{translateStatus(row.employee_status)}</span>
              </div>

              <div className="slots-cell">
                {Array.from({ length: DAY_END_HOUR - DAY_START_HOUR }, (_, index) => (
                  <div className="hour-grid-line" key={index} />
                ))}

                {row.sessions.length === 0 && <div className="free-label">Libre</div>}

                {row.sessions.map((session) => {
                  const service = services.find((item) => item.id === session.service_id);
                  const block = getSessionBlock(session);
                  return (
                    <article
                      key={session.id}
                      className={`session-block ${session.status}`}
                      style={{ left: `${block.left}%`, width: `${block.width}%` }}
                    >
                      <div>
                        <strong>{service?.name || "Prestation"}</strong>
                        <span>{session.duration_minutes} min · {translateStatus(session.status)}</span>
                      </div>
                      <div className="session-actions">
                        <button onClick={() => onExtendSession(session.id, 5)}>+5</button>
                        <button onClick={() => onExtendSession(session.id, 10)}>+10</button>
                        <button onClick={() => onFinishSession(session.id)}>Fin</button>
                      </div>
                    </article>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="kpi-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function getSessionBlock(session: ServiceSession) {
  const start = new Date(session.start_time);
  const end = new Date(session.real_end_time || session.planned_end_time);
  const startMinutes = start.getHours() * 60 + start.getMinutes();
  const endMinutes = end.getHours() * 60 + end.getMinutes();
  const left = ((startMinutes - DAY_START_HOUR * 60) / TOTAL_MINUTES) * 100;
  const width = Math.max(((endMinutes - startMinutes) / TOTAL_MINUTES) * 100, 4);

  return {
    left: clamp(left, 0, 100),
    width: clamp(width, 4, 100),
  };
}

function getNowPositionPercent() {
  const now = new Date();
  const minutes = now.getHours() * 60 + now.getMinutes();
  const percent = ((minutes - DAY_START_HOUR * 60) / TOTAL_MINUTES) * 100;
  return clamp(percent, 0, 100);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function translateStatus(status: string) {
  const labels: Record<string, string> = {
    available: "Disponible",
    busy: "Occupée",
    pause: "Pause",
    absent: "Absente",
    offline: "Hors ligne",
    planned: "Planifiée",
    in_progress: "En cours",
    extended: "Prolongée",
    completed: "Terminée",
    delayed: "Retard",
    cancelled: "Annulée",
    waiting: "En attente",
    assigned: "Affectée",
  };
  return labels[status] || status;
}
