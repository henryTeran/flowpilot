import type { InstituteDashboardRead } from "../types";

interface InstituteDashboardProps {
  dashboard?: InstituteDashboardRead;
}

const STATUS_CONFIG: Record<string, { label: string; subtitle: string; tone: string }> = {
  calm: {
    label: "Calme",
    subtitle: "Flux opérationnel sous contrôle",
    tone: "calm",
  },
  normal: {
    label: "Normal",
    subtitle: "Activité stable, aucune action urgente",
    tone: "normal",
  },
  busy: {
    label: "Chargé",
    subtitle: "Surveiller la file et les prochaines disponibilités",
    tone: "busy",
  },
  alert: {
    label: "Alerte",
    subtitle: "Action terrain nécessaire",
    tone: "alert",
  },
};

export function InstituteDashboard({ dashboard }: InstituteDashboardProps) {
  if (!dashboard) {
    return (
      <section className="institute-dashboard-v2 skeleton">
        <div className="dashboard-main-card">
          <p className="dashboard-status-label">Statut institut</p>
          <h2>Chargement</h2>
          <span>Synchronisation des KPIs opérationnels...</span>
        </div>
        <div className="dashboard-kpi-grid">
          <DashboardKpi label="File active" value="—" detail="—" />
          <DashboardKpi label="Occupation" value="—" detail="—" />
          <DashboardKpi label="Retards" value="—" detail="—" />
          <DashboardKpi label="Attente" value="—" detail="—" />
        </div>
      </section>
    );
  }

  const status = STATUS_CONFIG[dashboard.operational_status] || STATUS_CONFIG.normal;
  const activeQueue = dashboard.tickets_waiting + dashboard.tickets_assigned;
  const activeEmployees = dashboard.employees_busy + dashboard.employees_delayed;
  const occupationPercent = dashboard.employees_total > 0
    ? Math.round((activeEmployees / dashboard.employees_total) * 100)
    : 0;
  const activeSessionsLabel = `${dashboard.sessions_active}/${dashboard.employees_total}`;
  const waitLabel = dashboard.average_wait_minutes === null || dashboard.average_wait_minutes === undefined
    ? "—"
    : `${dashboard.average_wait_minutes} min`;
  const todaySessions = dashboard.sessions_completed_today + dashboard.sessions_active;
  const alertText = dashboard.alert_message || buildDefaultAlert(dashboard);

  return (
    <section className={`institute-dashboard-v2 ${status.tone}`}>
      <div className="dashboard-main-card">
        <div className="dashboard-main-topline">
          <div>
            <p className="dashboard-status-label">Statut institut</p>
            <h2>{status.label}</h2>
          </div>
          <span className={`dashboard-status-pill ${status.tone}`}>{status.label}</span>
        </div>

        <p className="dashboard-main-description">
          {dashboard.alert_message || status.subtitle}
        </p>

        <div className="dashboard-progress-block">
          <div className="dashboard-progress-label">
            <span>Occupation terrain</span>
            <strong>{occupationPercent}%</strong>
          </div>
          <div className="dashboard-progress-track">
            <div className="dashboard-progress-fill" style={{ width: `${Math.min(100, occupationPercent)}%` }} />
          </div>
        </div>

        <div className="dashboard-chip-row">
          <span>{dashboard.employees_available} dispo</span>
          <span>{dashboard.employees_busy} occupée(s)</span>
          <span>{dashboard.employees_delayed} retard</span>
        </div>
      </div>

      <div className="dashboard-kpi-grid">
        <DashboardKpi
          label="File active"
          value={activeQueue}
          detail={`${dashboard.tickets_waiting} à prendre · ${dashboard.tickets_assigned} affecté(s)`}
        />
        <DashboardKpi
          label="Occupation"
          value={activeSessionsLabel}
          detail={`${dashboard.sessions_active} prestation(s) en cours`}
        />
        <DashboardKpi
          label="Retards"
          value={dashboard.sessions_delayed}
          detail={dashboard.sessions_delayed > 0 ? "À clôturer ou prolonger" : "Aucun retard actif"}
          danger={dashboard.sessions_delayed > 0}
        />
        <DashboardKpi
          label="Attente moyenne"
          value={waitLabel}
          detail={formatNextAvailability(dashboard)}
        />
        <DashboardKpi
          label="Prestations jour"
          value={todaySessions}
          detail={`${dashboard.sessions_completed_today} terminée(s) · ${dashboard.sessions_active} en cours`}
        />
        <DashboardKpi
          label="Tickets clôturés"
          value={dashboard.tickets_completed_today}
          detail={`${dashboard.tickets_cancelled_today} annulé(s) aujourd’hui`}
        />
      </div>

      <div className={`dashboard-alert-card ${dashboard.sessions_delayed > 0 || dashboard.operational_status === "alert" ? "visible" : "soft"}`}>
        <span>{dashboard.sessions_delayed > 0 || dashboard.operational_status === "alert" ? "Alerte terrain" : "Contrôle terrain"}</span>
        <strong>{alertText}</strong>
      </div>
    </section>
  );
}

function DashboardKpi({
  label,
  value,
  detail,
  danger = false,
}: {
  label: string;
  value: string | number;
  detail: string;
  danger?: boolean;
}) {
  return (
    <article className={`dashboard-kpi-card ${danger ? "danger" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function formatNextAvailability(dashboard: InstituteDashboardRead) {
  if (dashboard.next_available_minutes === null || dashboard.next_available_minutes === undefined) {
    return "Créneau à confirmer";
  }

  if (dashboard.next_available_minutes <= 0) {
    return `${dashboard.next_available_employee_name || "Une collaboratrice"} disponible maintenant`;
  }

  return `${dashboard.next_available_employee_name || "Prochain créneau"} dans ${dashboard.next_available_minutes} min`;
}

function buildDefaultAlert(dashboard: InstituteDashboardRead) {
  if (dashboard.sessions_delayed > 0) {
    return `${dashboard.sessions_delayed} prestation(s) en retard : prolonger ou terminer depuis le planning.`;
  }

  if (dashboard.tickets_waiting + dashboard.tickets_assigned > 0 && dashboard.employees_available === 0) {
    return "Des clientes attendent et aucune collaboratrice n’est immédiatement disponible.";
  }

  return "Aucune alerte critique. Continuer le suivi depuis le planning temps réel.";
}
