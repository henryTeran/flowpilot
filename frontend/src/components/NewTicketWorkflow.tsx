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

type TicketStats = {
  waitingCount: number;
  waitingAmount: number;
  checkoutCount: number;
  checkoutAmount: number;
  salesCount: number;
  salesAmount: number;
};

interface NewTicketWorkflowProps {
  open: boolean;
  creatorEmployee?: Employee;
  ticketStats?: TicketStats;
  categories: ServiceCategory[];
  services: Service[];
  onRequestIdentity?: () => void;
  onClose: () => void;
  onValidate: (result: NewTicketWorkflowResult) => Promise<void> | void;
}

const identificationModes = [
  { code: "scan", label: "Scanner carte", help: "Carte abonnée / MultiPass", icon: "▥" },
  { code: "passage_bm", label: "Passage BM", help: "Cliente de passage", icon: "body\nminute" },
  { code: "nc", label: "NC", help: "Nouvelle cliente", icon: "□" },
  { code: "gift_card", label: "Carte cadeau", help: "Bon / code cadeau", icon: "▤" },
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
  ticketStats,
  categories,
  services,
  onRequestIdentity,
  onClose,
  onValidate,
}: NewTicketWorkflowProps) {
  const [step, setStep] = useState(2);
  const [customerLastName, setCustomerLastName] = useState("");
  const [customerFirstName, setCustomerFirstName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [identificationMode, setIdentificationMode] = useState("passage_bm");
  const [passageType, setPassageType] = useState("passage");
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedServiceIds, setSelectedServiceIds] = useState<string[]>([]);
  const [serviceSearch, setServiceSearch] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const usableCategories = useMemo(() => {
    return categories.filter((category) => services.some((service) => service.category_id === category.id));
  }, [categories, services]);

  const activeCategoryId = selectedCategoryId || usableCategories[0]?.id || "";

  const visibleServices = useMemo(() => {
    if (!activeCategoryId) return services;
    return services.filter((service) => service.category_id === activeCategoryId);
  }, [activeCategoryId, services]);

  const filteredServices = useMemo(() => {
    const query = serviceSearch.trim().toLowerCase();
    if (!query) return visibleServices;

    return visibleServices.filter((service) => {
      const haystack = `${service.name} ${service.category_id}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [serviceSearch, visibleServices]);

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
    if (!firstServiceId || submitting) return;

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
    } catch {
      // The parent displays the API error. Keep this arrival open for retry.
    } finally {
      setSubmitting(false);
    }
  }

  function resetAndClose() {
    setStep(2);
    setCustomerLastName("");
    setCustomerFirstName("");
    setCustomerPhone("");
    setIdentificationMode("passage_bm");
    setPassageType("passage");
    setSelectedCategoryId("");
    setSelectedServiceIds([]);
    setServiceSearch("");
    onClose();
  }

  return (
    <div className="bm-ticket-screen" role="dialog" aria-modal="true" aria-labelledby="bm-ticket-title">
      <section className="bm-ticket-window bm-ticket-window-clone">
        <header className="bm-ticket-header bm-new-ticket-header-clone">
          <button type="button" className="bm-ticket-back" onClick={resetAndClose}>
            ‹
          </button>

          <div className="bm-ticket-title-block clone-title">
            <h2 id="bm-ticket-title">Nouveau Ticket</h2>
          </div>

          <div className="bm-new-ticket-counter-row">
            <SmallCounter title="En attente" count={ticketStats?.waitingCount ?? 0} amount={ticketStats?.waitingAmount ?? 0} active />
            <SmallCounter title="En caisse" count={ticketStats?.checkoutCount ?? 0} amount={ticketStats?.checkoutAmount ?? 0} />
            <SmallCounter title="Ventes" count={ticketStats?.salesCount ?? 0} amount={ticketStats?.salesAmount ?? 0} />
          </div>
        </header>

        <main className="bm-ticket-content bm-new-ticket-content-clone">
          {step === 0 && (
            <section className="bm-ticket-stage bm-ticket-customer-stage clone-customer-stage">
              <div className="bm-ticket-identification-strip">
                <div className="bm-dash-placeholder">-</div>
                <button type="button" className="bm-identify-pill-inline" onClick={onRequestIdentity}>
                  {creatorEmployee ? `${creatorEmployee.first_name} identifié(e)` : "Je m’identifie"}
                  <span>⌕</span>
                </button>
              </div>

              <div className="bm-customer-form clone-customer-form">
                <input
                  value={customerLastName}
                  onChange={(event) => setCustomerLastName(event.target.value)}
                  placeholder="Nom"
                />
                <input
                  value={customerFirstName}
                  onChange={(event) => setCustomerFirstName(event.target.value)}
                  placeholder="Prénom"
                />
                <input
                  value={customerPhone}
                  onChange={(event) => setCustomerPhone(event.target.value)}
                  placeholder="Numéro de téléphone"
                />
              </div>

              <div className="bm-identification-mode-grid clone-identification-grid">
                {identificationModes.map((mode) => (
                  <button
                    key={mode.code}
                    type="button"
                    className={`bm-identification-mode clone-identification-card ${identificationMode === mode.code ? "active" : ""}`}
                    onClick={() => setIdentificationMode(mode.code)}
                  >
                    <span className="bm-mode-icon">{mode.icon}</span>
                    <strong>{mode.label}</strong>
                  </button>
                ))}
              </div>
            </section>
          )}

          {step === 1 && (
            <section className="bm-ticket-stage">
              <div className="bm-ticket-stage-title">
                <span>Type de passage</span>
                <h3>Choisir le passage ou l’abonnement</h3>
                <p>Cette étape reprend le choix Passage, Contrat, SKIN ou VIP du logiciel actuel.</p>
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
                    <span>Sélection prestations</span>
                    <h3>Ajouter une ou plusieurs prestations</h3>
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

                <div className="bm-service-filter-row">
                  <input
                    className="bm-service-search"
                    type="search"
                    value={serviceSearch}
                    onChange={(event) => setServiceSearch(event.target.value)}
                    placeholder="Rechercher une prestation"
                    aria-label="Rechercher une prestation"
                  />
                  {serviceSearch && (
                    <button type="button" className="bm-service-clear" onClick={() => setServiceSearch("")}>
                      Effacer
                    </button>
                  )}
                </div>

                {filteredServices.length === 0 ? (
                  <div className="bm-service-empty-state">
                    Aucune prestation ne correspond à la recherche dans cette catégorie.
                  </div>
                ) : (
                  <div className="bm-service-tile-grid">
                    {filteredServices.map((service) => {
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
                )}
              </div>
            </section>
          )}

          {step === 3 && (
            <section className="bm-ticket-stage bm-ticket-summary-stage">
              <div className="bm-ticket-stage-title">
                <span>Validation</span>
                <h3>Contrôler le ticket avant mise en attente</h3>
                <p>La facturation demandera une nouvelle identification de la collaboratrice qui a réalisé la prestation.</p>
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
                  <small>Identification possible avant validation.</small>
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
          <div className="bm-ticket-progress-clone" aria-label="Étapes nouveau ticket">
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

          <div className="bm-ticket-total">
            <span>{selectedServices.length} prestation(s)</span>
            <strong>Total {formatPrice(total)}</strong>
          </div>

          <div className="bm-ticket-footer-actions">
            <button type="button" className="bm-ticket-light-button" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
              Précédent
            </button>
            {step < 2 ? (
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
                {submitting ? "Validation..." : "Ajouter à la file"}
              </button>
            )}
          </div>
        </footer>
      </section>
    </div>
  );
}

function SmallCounter({ title, count, amount, active = false }: { title: string; count: number; amount: number; active?: boolean }) {
  return (
    <article className={`bm-new-ticket-counter ${active ? "active" : ""}`}>
      <span>{count}</span>
      <div>
        <strong>{title}</strong>
        <small>{formatPrice(amount)}</small>
      </div>
    </article>
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
