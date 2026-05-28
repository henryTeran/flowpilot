import { useState } from "react";

interface DemoToolsProps {
  disabled: boolean;
  onResetDemo: () => Promise<void>;
  onCreateDemoDay: () => Promise<void>;
  onRefresh: () => void | Promise<void>;
}

type DemoAction = "reset" | "scenario" | "refresh" | null;

export function DemoTools({ disabled, onResetDemo, onCreateDemoDay, onRefresh }: DemoToolsProps) {
  const [activeAction, setActiveAction] = useState<DemoAction>(null);

  async function run(action: Exclude<DemoAction, null>, callback: () => void | Promise<void>) {
    setActiveAction(action);
    try {
      await callback();
    } finally {
      setActiveAction(null);
    }
  }

  return (
    <section className="demo-tools-card">
      <div className="demo-tools-copy">
        <p className="eyebrow">Mode démonstration</p>
        <h2>Stabiliser la journée de test</h2>
        <span>
          Réinitialise les données opérationnelles ou génère une journée réaliste avec file d’attente,
          prestations en cours, retard et RDV sous appel.
        </span>
      </div>

      <div className="demo-tools-actions">
        <button
          type="button"
          className="secondary-button"
          disabled={disabled || Boolean(activeAction)}
          onClick={() => run("refresh", onRefresh)}
        >
          {activeAction === "refresh" ? "Actualisation..." : "Rafraîchir"}
        </button>

        <button
          type="button"
          className="warning-button"
          disabled={disabled || Boolean(activeAction)}
          onClick={() => run("reset", onResetDemo)}
        >
          {activeAction === "reset" ? "Reset..." : "Reset demo"}
        </button>

        <button
          type="button"
          className="primary-button"
          disabled={disabled || Boolean(activeAction)}
          onClick={() => run("scenario", onCreateDemoDay)}
        >
          {activeAction === "scenario" ? "Création..." : "Créer journée de test"}
        </button>
      </div>
    </section>
  );
}
