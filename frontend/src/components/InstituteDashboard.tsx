import type { InstituteDashboardRead } from "../types";

interface InstituteDashboardProps {
  dashboard?: InstituteDashboardRead;
}

export function InstituteDashboard({ dashboard }: InstituteDashboardProps) {
  if (!dashboard) {
    return (
      <section className="institute-dashboard skeleton">
        <DashboardTile label="Statut institut" value="Chargement" />
        <DashboardTile label="File active" value="—" />
        <DashboardTile label="Occupation" value="—" />
        <DashboardTile label="Attente moyenne" value="—" />
      </section>
    );
  }

  const activeQueue = dashboard.tickets_waiting + dashboard.tickets_assigned;
  const occupationLabel = `${dashboard.sessions_active}/${dashboard.employees_total}`;
  const waitLabel = dashboard.average_wait_minutes === null || dashboard.average_wait_minutes === undefined
    ? "—"
    : `${dashboard.average_wait_minutes} min`;

  return (
    <section className={`institute-dashboard ${dashboard.operational_status}`}>
      <DashboardTile
        label="Statut institut"
        value={translateOperationalStatus(dashboard.operational_status)}
        detail={dashboard.alert_message || "Flux opérationnel sous contrôle"}
      />
      <DashboardTile
        label="File active"
        value={activeQueue}
        detail={`${dashboard.tickets_waiting} attente · ${dashboard.tickets_assigned} affecté(s)`}
      />
      <DashboardTile
        label="Occupation"
        value={occupationLabel}
        detail={`${dashboard.employees_available} dispo · ${dashboard.employees_busy} occupée(s) · ${dashboard.employees_delayed} retard`}
      />
      <DashboardTile
        label="Attente moyenne"
        value={waitLabel}
        detail={formatNextAvailability(dashboard)}
      />
      <DashboardTile
        label="Prestations jour"
        value={dashboard.sessions_completed_today + dashboard.sessions_active}
        detail={`${dashboard.sessions_completed_today} terminée(s) · ${dashboard.sessions_active} en cours`}
      />
    </section>
  );
}

function DashboardTile({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return (
    <article className="dashboard-tile">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </article>
  );
}

function translateOperationalStatus(status: string) {
  const labels: Record<string, string> = {
    calm: "Calme",
    normal: "Normal",
    busy: "Chargé",
    alert: "Alerte",
  };
  return labels[status] || status;
}

function formatNextAvailability(dashboard: InstituteDashboardRead) {
  if (dashboard.next_available_minutes === null || dashboard.next_available_minutes === undefined) {
    return "Prochaine disponibilité à confirmer";
  }

  if (dashboard.next_available_minutes <= 0) {
    return `${dashboard.next_available_employee_name || "Une collaboratrice"} disponible maintenant`;
  }

  return `${dashboard.next_available_employee_name || "Prochain créneau"} dans ${dashboard.next_available_minutes} min`;
}
