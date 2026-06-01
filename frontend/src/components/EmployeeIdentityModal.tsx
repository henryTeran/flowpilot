import type { Employee } from "../types";

interface EmployeeIdentityModalProps {
  open: boolean;
  employees: Employee[];
  identifiedEmployeeId: string;
  onIdentify: (employeeId: string) => void;
  onClose: () => void;
}

export function EmployeeIdentityModal({
  open,
  employees,
  identifiedEmployeeId,
  onIdentify,
  onClose,
}: EmployeeIdentityModalProps) {
  if (!open) return null;

  return (
    <div className="bm-modal-layer" role="dialog" aria-modal="true">
      <button className="bm-modal-backdrop" type="button" aria-label="Fermer" onClick={onClose} />
      <section className="bm-identity-modal">
        <header className="bm-modal-header">
          <div>
            <p>Identification</p>
            <h2>Je m’identifie</h2>
          </div>
          <button type="button" onClick={onClose}>Fermer</button>
        </header>

        <p className="bm-modal-help">
          Sélectionne la collaboratrice qui effectue l’action. Cette étape sera réutilisée pour la création du ticket et l’encaissement.
        </p>

        <div className="bm-identity-grid">
          {employees.map((employee) => (
            <button
              key={employee.id}
              type="button"
              className={`bm-identity-card ${identifiedEmployeeId === employee.id ? "selected" : ""}`}
              onClick={() => {
                onIdentify(employee.id);
                onClose();
              }}
            >
              <strong>{employee.first_name}</strong>
              <span>{translateEmployeeStatus(employee.status)}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function translateEmployeeStatus(status: string) {
  const labels: Record<string, string> = {
    available: "Disponible",
    busy: "Occupée",
    pause: "Pause",
    absent: "Absente",
    offline: "Hors ligne",
    delayed: "Retard",
  };
  return labels[status] || status;
}
