import type { Employee } from "../types";

export type IdentityContext = "general" | "create_ticket" | "checkout" | "workday";

interface EmployeeIdentityModalProps {
  open: boolean;
  employees: Employee[];
  identifiedEmployeeId: string;
  context?: IdentityContext;
  onIdentify: (employeeId: string) => void;
  onClose: () => void;
}

const contextText: Record<IdentityContext, { eyebrow: string; title: string; help: string }> = {
  general: {
    eyebrow: "Identification collaboratrice",
    title: "Je m’identifie",
    help: "Choisissez la collaboratrice qui effectue l’action sur la tablette.",
  },
  create_ticket: {
    eyebrow: "Création ticket",
    title: "Je m’identifie",
    help: "Avant de créer le ticket, la personne à la réception doit s’identifier.",
  },
  checkout: {
    eyebrow: "Encaissement",
    title: "Je m’identifie",
    help: "Avant d’encaisser, la collaboratrice qui a réalisé la prestation doit s’identifier.",
  },
  workday: {
    eyebrow: "Début de journée",
    title: "Je m’identifie",
    help: "Identifiez-vous pour déclarer votre arrivée, votre départ et vos pauses.",
  },
};

export function EmployeeIdentityModal({
  open,
  employees,
  identifiedEmployeeId,
  context = "general",
  onIdentify,
  onClose,
}: EmployeeIdentityModalProps) {
  if (!open) return null;

  const copy = contextText[context];

  return (
    <div className="bm-identify-screen" role="dialog" aria-modal="true" aria-labelledby="bm-identify-title">
      <section className="bm-identify-panel">
        <header className="bm-identify-header">
          <button type="button" className="bm-identify-back" onClick={onClose}>
            Retour
          </button>
          <div>
            <p>{copy.eyebrow}</p>
            <h2 id="bm-identify-title">{copy.title}</h2>
            <span>{copy.help}</span>
          </div>
        </header>

        <div className="bm-identify-grid" aria-label="Liste des collaboratrices">
          {employees.map((employee, index) => {
            const selected = identifiedEmployeeId === employee.id;
            const code = formatEmployeeCode(employee, index);
            return (
              <button
                key={employee.id}
                type="button"
                className={`bm-identify-card ${selected ? "selected" : ""}`}
                onClick={() => {
                  onIdentify(employee.id);
                  onClose();
                }}
              >
                <span className="bm-identify-code">{code}</span>
                <strong>{employee.first_name}</strong>
                <small>{formatStatus(employee.status)}</small>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function formatEmployeeCode(employee: Employee, index: number) {
  if (employee.code) return employee.code;

  const numericId = employee.id.replace(/\D/g, "").slice(-5);
  if (numericId) return numericId.padStart(5, "0");

  return String(16370 + index).padStart(5, "0");
}

function formatStatus(status: string) {
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
