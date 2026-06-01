import { useMemo, useState } from "react";
import type { Employee, Service, ServiceCategory } from "../types";

export interface NewTicketWorkflowResult {
  serviceId: string;
  selectedServiceIds: string[];
  customer: {
    lastName: string;
    firstName: string;
    phone: string;
    identificationMode: string;
  };
  passageType: string;
}

interface NewTicketWorkflowProps {
  open: boolean;
  creatorEmployee?: Employee;
  categories: ServiceCategory[];
  services: Service[];
  onClose: () => void;
  onValidate: (result: NewTicketWorkflowResult) => Promise<void> | void;
}

const identificationModes = [
  { code: "scan", label: "Scan carte", help: "Carte abonnée / MultiPass" },
  { code: "passage_bm", label: "Passage BM", help: "Cliente de passage" },
  { code: "nc", label: "NC", help: "Nouvelle cliente" },
  { code: "gift_card", label: "Carte cadeau", help: "Bon / code cadeau" },
];

const passageTypes = [
  { code: "passage", label: "Passage", help: "Prix passage" },
  { code: "contrat", label: "Contrat", help: "Abonnement / prélèvement" },
  { code: "skin", label: "SKIN", help: "Offre SkinMinute" },
  { code: "antip_skin", label: "AntiP SKIN", help: "Anticipation Skin" },
  { code: "vip", label: "VIP", help: "Tarif privilégié" },
];

const stepLabels = ["Cliente", "Passage", "Prestations", "Validation"];

export function NewTicketWorkflow({
  open,
  creatorEmployee,
  categories,
  services,
  onClose,
  onValidate,
}: NewTicketWorkflowProps) {
  const [step, setStep] = useState(0);
  const [customerLastName, setCustomerLastName] = useState("");
  const [customerFirstName, setCustomerFirstName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [identificationMode, setIdentificationMode] = useState("passage_bm");
  const [passageType, setPassageType] = useState("passage");
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedServiceIds, setSelectedServiceIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const usableCategories = useMemo(() => {
    return categories.filter((category) => services.some((service) => service.category_id === category.id));
  }, [categories, services]);

  const activeCategoryId = selectedCategoryId || usableCategories[0]?.id || "";

  const visibleServices = useMemo(() => {
    if (!activeCategoryId) return services;
    return services.filter((service) => service.category_id === activeCategoryId);
  }, [activeCategoryId, services]);

  const selectedServices = useMemo(
    () => selectedServiceIds.map((id) => services.find((service) => service.id === id)).filter(Boolean) as Service[],
    [selectedServiceIds, services]
  );

  const total = useMemo(() => {
    return selectedServices.reduce((sum, service) => sum + getDisplayPrice(service, passageType), 0);
  }, [selectedServices, passageType]);

  if (!open) return null;

  function toggleService(serviceId: string) {
    setSelectedServiceIds((current) => {
      if (current.includes(serviceId)) return current.filter((id) => id !== serviceId);
      return [...current, serviceId];
    });
  }

  async function submitTicket() {
    const firstServiceId = selectedServiceIds[0];
    if (!firstServiceId) return;

    setSubmitting(true);
    try {
      await onValidate({
        serviceId: firstServiceId,
        selectedServiceIds,
        customer: {
          lastName: customerLastName.trim(),
          firstName: customerFirstName.trim(),
          phone: customerPhone.trim(),
          identificationMode,
        },
        passageType,
      });
      resetAndClose();
    } finally {
      setSubmitting(false);
    }
  }

  function resetAndClose() {
    setStep(0);
    setCustomerLastName("");
    setCustomerFirstName("");
    setCustomerPhone("");
    setIdentificationMode("passage_bm");
    setPassageType("passage");
    setSelectedCategoryId("");
    setSelectedServiceIds([]);
    onClose();
  }

  return (
    <div className="bm-ticket-screen" role="dialog" aria-modal="true" aria-labelledby="bm-ticket-title">
      <section className="bm-ticket-window">
        <header className="bm-ticket-header">
          <button type="button" className="bm-ticket-back" onClick={resetAndClose}>
            Retour
          </button>

          <div className="bm-ticket-title-block">
            <h2 id="bm-ticket-title">Nouveau Ticket</h2>
            <p>
              {creatorEmployee
                ? `Création par ${creatorEmployee.first_name}`
                : "Identification collaboratrice requise"}
            </p>
          </div>

          <div className="bm-ticket-steps" aria-label="Étapes nouveau ticket">
            {stepLabels.map((label, index) => (
              <button
                key={label}
                type="button"
                className={`bm-ticket-step ${index === step ? "active" : ""} ${index < step ? "done" : ""}`}
                onClick={() => setStep(index)}
              >
                <span>{index + 1}</span>
                {label}
              </button>
            ))}
          </div>
        </header>

        <main className="bm-ticket-content">
          {step === 0 && (
            <section className="bm-ticket-stage bm-ticket-customer-stage">
              <div className="bm-ticket-stage-title">
                <span>Étape 1</span>
                <h3>Identifier la cliente</h3>
                <p>Rechercher une cliente existante ou créer un passage rapide.</p>
              </div>

              <div className="bm-customer-form">
                <label>
                  Nom
                  <input
                    value={customerLastName}
                    onChange={(event) => setCustomerLastName(event.target.value)}
                    placeholder="Nom de famille"
                  />
                </label>
                <label>
                  Prénom
                  <input
                    value={customerFirstName}
                    onChange={(event) => setCustomerFirstName(event.target.value)}
                    placeholder="Prénom"
                  />
                </label>
                <label>
                  Téléphone
                  <input
                    value={customerPhone}
                    onChange={(event) => setCustomerPhone(event.target.value)}
                    placeholder="Téléphone"
                  />
                </label>
              </div>

              <div className="bm-identification-mode-grid">
                {identificationModes.map((mode) => (
                  <button
                    key={mode.code}
                    type="button"
                    className={`bm-identification-mode ${identificationMode === mode.code ? "active" : ""}`}
                    onClick={() => setIdentificationMode(mode.code)}
                  >
                    <strong>{mode.label}</strong>
                    <span>{mode.help}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {step === 1 && (
            <section className="bm-ticket-stage">
              <div className="bm-ticket-stage-title">
                <span>Étape 2</span>
                <h3>Choisir le type de passage</h3>
                <p>Le type choisi influence les prix et les avantages appliqués au ticket.</p>
              </div>

              <div className="bm-passage-grid">
                {passageTypes.map((type) => (
                  <button
                    key={type.code}
                    type="button"
                    className={`bm-passage-card ${passageType === type.code ? "active" : ""}`}
                    onClick={() => setPassageType(type.code)}
                  >
                    <strong>{type.label}</strong>
                    <span>{type.help}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {step === 2 && (
            <section className="bm-ticket-stage bm-service-selection-stage">
              <div className="bm-service-blue-area">
                <div className="bm-service-blue-header">
                  <div>
                    <span>Étape 3</span>
                    <h3>Sélection des prestations</h3>
                  </div>
                  <strong>{selectedServices.length} prestation(s)</strong>
                </div>

                <div className="bm-service-category-row">
                  {usableCategories.map((category) => (
                    <button
                      key={category.id}
                      type="button"
                      className={activeCategoryId === category.id ? "active" : ""}
                      onClick={() => setSelectedCategoryId(category.id)}
                    >
                      {formatCategoryName(category.name)}
                    </button>
                  ))}
                </div>

                <div className="bm-service-tile-grid">
                  {visibleServices.map((service) => {
                    const selected = selectedServiceIds.includes(service.id);
                    return (
                      <button
                        key={service.id}
                        type="button"
                        className={`bm-service-tile ${selected ? "selected" : ""}`}
                        onClick={() => toggleService(service.id)}
                      >
                        <strong>{service.name}</strong>
                        <span>{formatDuration(service)}</span>
                        <small>{formatPrice(getDisplayPrice(service, passageType))}</small>
                      </button>
                    );
                  })}
                </div>
              </div>
            </section>
          )}

          {step === 3 && (
            <section className="bm-ticket-stage bm-ticket-summary-stage">
              <div className="bm-ticket-stage-title">
                <span>Étape 4</span>
                <h3>Valider le ticket</h3>
                <p>Contrôler la cliente, le passage et les prestations avant de mettre le ticket en attente.</p>
              </div>

              <div className="bm-ticket-summary-grid">
                <article>
                  <span>Cliente</span>
                  <strong>{formatCustomer(customerLastName, customerFirstName)}</strong>
                  <small>{customerPhone || "Téléphone non renseigné"}</small>
                </article>
                <article>
                  <span>Mode</span>
                  <strong>{findLabel(identificationModes, identificationMode)}</strong>
                  <small>{findLabel(passageTypes, passageType)}</small>
                </article>
                <article>
                  <span>Créatrice ticket</span>
                  <strong>{creatorEmployee?.first_name || "Non identifiée"}</strong>
                  <small>La facturation demandera une nouvelle identification.</small>
                </article>
              </div>

              <div className="bm-ticket-lines">
                {selectedServices.length === 0 ? (
                  <p>Aucune prestation sélectionnée.</p>
                ) : (
                  selectedServices.map((service) => (
                    <div key={service.id} className="bm-ticket-line">
                      <span>{service.name}</span>
                      <small>{formatDuration(service)}</small>
                      <strong>{formatPrice(getDisplayPrice(service, passageType))}</strong>
                    </div>
                  ))
                )}
              </div>
            </section>
          )}
        </main>

        <footer className="bm-ticket-footer">
          <div className="bm-ticket-total">
            <span>{selectedServices.length} prestation(s)</span>
            <strong>Total {formatPrice(total)}</strong>
          </div>

          <div className="bm-ticket-footer-actions">
            <button type="button" className="bm-ticket-light-button" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
              Précédent
            </button>
            {step < 3 ? (
              <button type="button" className="bm-ticket-primary-button" onClick={() => setStep(Math.min(3, step + 1))}>
                Continuer
              </button>
            ) : (
              <button
                type="button"
                className="bm-ticket-primary-button"
                onClick={() => void submitTicket()}
                disabled={selectedServiceIds.length === 0 || submitting}
              >
                {submitting ? "Validation..." : "Valider ticket"}
              </button>
            )}
          </div>
        </footer>
      </section>
    </div>
  );
}

function getDisplayPrice(service: Service, passageType: string) {
  if (["contrat", "skin", "antip_skin", "vip"].includes(passageType)) {
    return service.price_member ?? service.price_passage ?? 0;
  }

  return service.price_passage ?? service.price_member ?? 0;
}

function formatPrice(value: number) {
  return `${value.toFixed(2)} CHF`;
}

function formatDuration(service: Service) {
  if (service.duration_max && service.duration_max !== service.duration_min) {
    return `${service.duration_min}/${service.duration_max} min`;
  }

  return `${service.duration_min} min`;
}

function formatCustomer(lastName: string, firstName: string) {
  const fullName = `${firstName.trim()} ${lastName.trim()}`.trim();
  return fullName || "Cliente de passage";
}

function formatCategoryName(name: string) {
  return name.replace(/\s*\+\s*/g, " + ");
}

function findLabel(items: Array<{ code: string; label: string }>, code: string) {
  return items.find((item) => item.code === code)?.label || code;
}
