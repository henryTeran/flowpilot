import { useEffect, useMemo, useRef, useState } from "react";
import type { Customer, Employee, PaymentMethod, QueueTicket, Service } from "../types";
import { PackageWallet } from "./PackageWallet";
import { PaymentHistory } from "./PaymentHistory";
import { LoyaltyWallet } from "./LoyaltyWallet";
import { MembershipWallet } from "./MembershipWallet";
import { CheckoutCurrency } from "./CheckoutCurrency";
import { GiftCardWallet, cents, type GiftTender } from "./GiftCardWallet";
import { CustomerPicker } from "./CustomerPicker";
import { apiPatch } from "../api/client";
import { getAccessToken } from "../api/session";

interface CheckoutPanelProps {
  onRefresh?: () => Promise<boolean>;
  ticket?: QueueTicket;
  services: Service[];
  employees: Employee[];
  cashierEmployee?: Employee;
  selectedPaymentMethod: PaymentMethod;
  onPaymentMethodChange: (method: PaymentMethod) => void;
  onAddService: (serviceId: string) => void;
  onRemoveLine: (lineId: string) => void;
  onPay: (payment?: { payment_method: PaymentMethod; remainder_method?: "cb" | "especes" | "cheque" }) => void;
  onClose: () => void;
  onCancelTicket?: (ticketId: string) => void;
  onReidentify?: () => void;
}

const PAYMENT_METHODS: Array<{ value: PaymentMethod; label: string }> = [
  { value: "cb", label: "CB" },
  { value: "especes", label: "esp." },
  { value: "cheque", label: "chq." },
];

export function CheckoutPanel({
  ticket,
  services,
  employees,
  cashierEmployee,
  selectedPaymentMethod,
  onPaymentMethodChange,
  onAddService,
  onRemoveLine,
  onPay,
  onClose,
  onCancelTicket,
  onReidentify,
  onRefresh,
}: CheckoutPanelProps) {
  const accessToken = getAccessToken();
  const [serviceToAdd, setServiceToAdd] = useState("");
  const [printCustomerTicket, setPrintCustomerTicket] = useState(false);
  const [customer, setCustomer] = useState<Customer>();
  const [commerceBusy, setCommerceBusy] = useState(false);
  const [loyaltyBusy, setLoyaltyBusy] = useState(!!onRefresh && !!ticket?.customer_id);
  const [loyaltyCoveredLines, setLoyaltyCoveredLines] = useState<string[]>([]);
  const [membershipBusy, setMembershipBusy] = useState(false);
  const [currencyBusy, setCurrencyBusy] = useState(false);
  const [giftBusy, setGiftBusy] = useState(!!onRefresh);
  const [giftTender, setGiftTender] = useState<GiftTender>();
  const [memberCoveredLines, setMemberCoveredLines] = useState<string[]>([]);
  const commercialWriter = useRef<symbol | null>(null);
  function beginCommercialMutation() {
    if (commercialWriter.current) return null;
    const lease = Symbol(); commercialWriter.current = lease;
    return () => { if (commercialWriter.current === lease) commercialWriter.current = null; };
  }
  const [coveredLines, setCoveredLines] = useState<string[]>([]);
  const [historicalLines, setHistoricalLines] = useState<string[]>([]);
  const [identifyOpen, setIdentifyOpen] = useState(false);
  const [identityBusy, setIdentityBusy] = useState(false);
  const [identityError, setIdentityError] = useState<string>();
  const identityEpoch = useRef(0);
  const identityPending = useRef(false);
  useEffect(() => {
    identityEpoch.current++; identityPending.current = false;
    setIdentifyOpen(false); setIdentityBusy(false); setIdentityError(undefined);
    return () => { identityEpoch.current++; };
  }, [ticket?.id, ticket?.institute_id, accessToken]);
  useEffect(() => { setCoveredLines([]); setHistoricalLines([]); }, [ticket?.id]);
  useEffect(() => {
    setCustomer(undefined); setCommerceBusy(false); setMembershipBusy(false); setLoyaltyBusy(!!onRefresh && !!ticket?.customer_id); setLoyaltyCoveredLines([]); setCurrencyBusy(false); setGiftBusy(!!onRefresh); setGiftTender(undefined); setMemberCoveredLines([]); commercialWriter.current = null;
  }, [ticket?.id, ticket?.customer_id, ticket?.institute_id, accessToken]);

  async function identifyCustomer(value?: Customer, reconcileOnly = false) {
    if (!ticket || !onRefresh || identityPending.current) return;
    const epoch = identityEpoch.current;
    const token = getAccessToken();
    const current = () => epoch === identityEpoch.current && token === getAccessToken();
    identityPending.current = true; setIdentityBusy(true); setIdentityError(undefined);
    try {
      if (!reconcileOnly) await apiPatch<QueueTicket>(`/tickets/${ticket.id}/customer`, { customer_id: value?.id ?? null });
      if (!current()) return;
      if (!await onRefresh()) throw new Error("Actualiser le ticket avant de payer");
      if (!current()) return;
      setIdentityBusy(false); setIdentifyOpen(false);
    } catch (reason) {
      if (!current()) return;
      setIdentityError(reason instanceof Error ? reason.message : "Identification indisponible");
      // A lost response may have committed. Keep payment locked until a complete server refresh.
      try {
        const refreshed = await onRefresh();
        if (current() && refreshed) { setIdentityBusy(false); setIdentifyOpen(false); }
      } catch { /* Explicit refresh remains available. */ }
    } finally { if (current()) identityPending.current = false; }
  }

  const orderedServices = useMemo(
    () => [...services].sort((a, b) => a.name.localeCompare(b.name, "fr")),
    [services],
  );

  if (!ticket) {
    return (
      <div className="bm-checkout-empty bm-checkout-clone-empty">
        <strong>Aucun ticket sélectionné</strong>
        <p>Sélectionne un ticket prêt pour la caisse.</p>
      </div>
    );
  }

  const ticketLines = ticket.lines || [];
  const total = ticket.total_amount ?? ticketLines.reduce((sum, line) => sum + Number(line.total || 0), 0);
  const creator = employees.find((employee) => employee.id === ticket.created_by_id);
  const assigned = employees.find((employee) => employee.id === ticket.assigned_employee_id);
  const giftActive = !!giftTender && cents(giftTender.gift_amount) > 0;
  const canEditLines = !commerceBusy && !membershipBusy && !loyaltyBusy && !currencyBusy && !giftBusy && !giftActive && !identityBusy && ["ready_for_checkout", "in_checkout"].includes(ticket.status);

  function handleAddService() {
    if (!serviceToAdd) return;
    onAddService(serviceToAdd);
    setServiceToAdd("");
  }

  return (
    <section className="bm-checkout-clone">
      <main className="bm-checkout-main-card">
        <header className="bm-ticket-cash-header">
          <button type="button" className="bm-cash-back" onClick={onClose} aria-label="Retour">
            ‹
          </button>

          <div className="bm-cash-title-block">
            <h1>Ticket n°{formatTicketNumber(ticket.ticket_number)}</h1>
            <span>{formatTicketStatus(ticket.status)}</span>
            <span>{ticket.currency ? `Devise : ${ticket.currency}` : "Devise non confirmée"}</span>
          </div>

          <div className="bm-cash-top-actions">
            <button type="button" className="bm-cash-top-primary">
              Imprimer un recu provisoire
            </button>
            <button
              type="button"
              className="bm-cash-top-secondary"
              onClick={() => onCancelTicket?.(ticket.id)}
              disabled={!onCancelTicket || ticket.status === "paid" || commerceBusy || membershipBusy || loyaltyBusy || currencyBusy || giftBusy || giftActive || identityBusy || coveredLines.length > 0 || memberCoveredLines.length > 0 || loyaltyCoveredLines.length > 0}
            >
              Clore en annulation
            </button>
          </div>
        </header>

        <section className="bm-customer-cash-card">
          <div className="bm-customer-avatar">
            <span>CL</span>
            <small>Dossier</small>
          </div>

          <div className="bm-customer-cash-info">
            <h2>{customer && customer.id === ticket.customer_id ? customer.display_name : ticket.customer_id ? "Cliente identifiée" : "Cliente de passage"}</h2>
            <div className="bm-customer-meta-grid">
              <span><strong>Téléphone</strong>{customer && customer.id === ticket.customer_id ? customer.phone || "—" : "—"}</span>
              <span><strong>Segment</strong>{ticket.customer_id ? "Identifiée" : "Passage"}</span>
              <span><strong>Arrivee</strong>{formatShortTime(ticket.arrival_time)}</span>
              <span><strong>Origine</strong>File institut</span>
              <span><strong>Dossier</strong>{ticket.ticket_number}</span>
            </div>
          </div>

          <button type="button" className="bm-subscription-link">
            Ouvrir la fiche cliente
          </button>
        </section>

        {onRefresh && canEditLines && coveredLines.length === 0 && memberCoveredLines.length === 0 && loyaltyCoveredLines.length === 0 && <button type="button" onClick={() => setIdentifyOpen(value => !value)}>
          {ticket.customer_id ? "Changer de cliente" : "Identifier la cliente"}
        </button>}
        {onRefresh && <CheckoutCurrency key={`currency:${ticket.institute_id}:${ticket.id}:${ticket.customer_id || ""}:${accessToken}`} ticket={ticket}
          blocked={commerceBusy || membershipBusy || loyaltyBusy || giftBusy || identityBusy || identifyOpen} onRefresh={onRefresh} onBusy={setCurrencyBusy} beginMutation={beginCommercialMutation} />}
        {onRefresh && <GiftCardWallet key={`gift:${ticket.institute_id}:${ticket.id}:${ticket.customer_id || ""}:${accessToken}`} ticket={ticket}
          blocked={commerceBusy || membershipBusy || loyaltyBusy || currencyBusy || identityBusy || identifyOpen} onRefresh={onRefresh}
          onBusy={setGiftBusy} onTender={setGiftTender} beginMutation={beginCommercialMutation} />}
        {identifyOpen && !identityBusy && <CustomerPicker key={`${ticket.institute_id}:${ticket.id}`} instituteId={ticket.institute_id}
          selected={customer} onSelect={value => { void identifyCustomer(value); }} />}
        {identityError && <p role="alert">{identityError}</p>}
        {identityBusy && <button type="button" onClick={() => { void identifyCustomer(undefined, true); }}>Actualiser le ticket</button>}
        {ticket.customer_id && onRefresh && !identifyOpen && !identityBusy && <PackageWallet key={`${ticket.institute_id}:${ticket.id}:${ticket.customer_id}:${accessToken}`}
          ticket={ticket} onRefresh={onRefresh} onBusy={setCommerceBusy} onCustomer={setCustomer}
          blocked={loyaltyBusy || membershipBusy || currencyBusy || giftBusy || giftActive} excludedLines={[...memberCoveredLines, ...loyaltyCoveredLines]} beginMutation={beginCommercialMutation}
          onCoverage={(active, historical) => {
            setCoveredLines(active);
            setHistoricalLines(previous => [...new Set([...previous, ...historical])]);
          }} />}
        {ticket.customer_id && onRefresh && !identifyOpen && !identityBusy && <MembershipWallet key={`member:${ticket.institute_id}:${ticket.id}:${ticket.customer_id}:${accessToken}`}
          ticket={ticket} services={services} blocked={loyaltyBusy || commerceBusy || currencyBusy || giftBusy || giftActive} excludedLines={[...coveredLines, ...loyaltyCoveredLines]} beginMutation={beginCommercialMutation}
          onRefresh={onRefresh} onBusy={setMembershipBusy} onCoverage={(active, historical) => {
            setMemberCoveredLines(active); setHistoricalLines(previous => [...new Set([...previous, ...historical])]);
          }} />}
        {ticket.customer_id && onRefresh && !identifyOpen && !identityBusy && <LoyaltyWallet ticket={ticket}
          blocked={commerceBusy || membershipBusy || currencyBusy || giftBusy || giftActive} excludedLines={[...coveredLines, ...memberCoveredLines]}
          beginMutation={beginCommercialMutation} onRefresh={onRefresh} onBusy={setLoyaltyBusy} onCoverage={(active, historical) => {
            setLoyaltyCoveredLines(active); setHistoricalLines(previous => [...new Set([...previous, ...historical])]);
          }} />}
        {onRefresh && <PaymentHistory instituteId={ticket.institute_id} ticketId={ticket.id} />}
        <section className="bm-cash-action-row">
          <button type="button">▦ Appliquer remise</button>
          <div className="bm-cash-add-service">
            <span>＋ Ajouter prestation</span>
            <select value={serviceToAdd} onChange={(event) => setServiceToAdd(event.target.value)} disabled={!canEditLines}>
              <option value="">Choisir une prestation à ajouter</option>
              {orderedServices.map((service) => (
                <option key={service.id} value={service.id}>
                  {service.name} · {service.duration_min} min · {formatCurrency(Number(service.price_passage || 0), ticket.currency)}
                </option>
              ))}
            </select>
            <button type="button" onClick={handleAddService} disabled={!serviceToAdd || !canEditLines}>
              Ajouter
            </button>
          </div>
          <button type="button">▧ Ajouter article</button>
          <button type="button">▥ Bon cadeau</button>
        </section>

        <section className="bm-cash-lines-card">
          {ticketLines.length === 0 ? (
            <div className="bm-cash-empty-line">Aucune prestation sur ce ticket.</div>
          ) : (
            ticketLines.map((line) => {
              const service = services.find((item) => item.id === line.service_id);
              const removable = canEditLines && ticketLines.length > 1;
              return (
                <article key={line.id} className="bm-cash-line-item">
                  <div className="bm-cash-line-name">
                    <strong>{service?.name || "Prestation"}</strong>
                    <small>{line.duration_minutes} min</small>
                  </div>

                  <div className="bm-cash-line-price">
                    <span>Prix</span>
                    <strong>{formatNumber(Number(line.unit_price || line.total || 0))}</strong>
                  </div>

                  <div className="bm-cash-line-qty">
                    <span>Quantité</span>
                    <div>
                      <button type="button" disabled>−</button>
                      <strong>{line.quantity || 1}</strong>
                      <button type="button" disabled>＋</button>
                    </div>
                  </div>

                  <div className="bm-cash-line-total">
                    <span>Total</span>
                    <strong>{formatNumber(Number(line.total || 0))}</strong>
                  </div>

                  <button
                    type="button"
                    className="bm-cash-trash"
                    onClick={() => onRemoveLine(line.id)}
                    disabled={!removable || line.commercial_history || historicalLines.includes(line.id)}
                    title={line.commercial_history || historicalLines.includes(line.id) ? "Historique commercial a conserver" : removable ? "Retirer cette prestation" : "Impossible de retirer la dernière prestation"}
                  >
                    🗑
                  </button>
                </article>
              );
            })
          )}
        </section>

        <footer className="bm-cash-footer-note">
          Controle avant paiement: verifier les prestations, la duree et les montants du ticket.
        </footer>
      </main>

      <aside className="bm-checkout-side-card">
        <section className="bm-cash-audit-block">
          <span>Créé par</span>
          <strong>{creator?.first_name || "—"}</strong>
          <em>{formatShortTime(ticket.arrival_time)}</em>
        </section>

        <section className="bm-cash-audit-block">
          <span>Encaissé par</span>
          <strong>{cashierEmployee?.first_name || "—"}</strong>
          <em>{cashierEmployee ? "Identifiée" : "Identification requise"}</em>
        </section>

        <button type="button" className="bm-side-identify" onClick={onReidentify}>
          Je m’identifie ↻
        </button>

        <div className="bm-cash-total-box">
          <span>Total</span>
          <strong>{formatCurrency(total, ticket.currency)}</strong>
        </div>

        <p>Émission des cartes cadeaux dans Offres, par la responsable.</p>
        {giftActive && <p>{cents(giftTender!.remaining_due) === 0 ? "Paiement entièrement couvert par les cartes cadeaux" : "Choisir le moyen de paiement du complément"}</p>}

        <div className="bm-cash-payments-rounds">
          {PAYMENT_METHODS.map((method) => (
            <button
              key={method.value}
              type="button"
              className={selectedPaymentMethod === method.value ? "selected" : ""}
              onClick={() => onPaymentMethodChange(method.value)}
            >
              {method.label}
            </button>
          ))}
        </div>

        <label className="bm-print-toggle">
          <span>Imprimer ticket client</span>
          <input
            type="checkbox"
            checked={printCustomerTicket}
            onChange={(event) => setPrintCustomerTicket(event.target.checked)}
          />
        </label>

        <button type="button" className="bm-final-cash-button" onClick={() => {
          if (!giftActive) { onPay(); return; }
          if (cents(giftTender!.remaining_due) === 0) onPay({ payment_method: "carte_cadeau" });
          else if (["cb", "especes", "cheque"].includes(selectedPaymentMethod)) onPay({ payment_method: "mixte", remainder_method: selectedPaymentMethod as "cb" | "especes" | "cheque" });
        }} disabled={!cashierEmployee || commerceBusy || membershipBusy || loyaltyBusy || currencyBusy || giftBusy || identityBusy || ticket.status === "paid"}>
          Enregistrer le paiement
        </button>

        <small className="bm-side-helper">
          Prestations réalisées par {assigned?.first_name || "la collaboratrice de cabine"}. La caisse peut ajuster les lignes avant paiement.
        </small>
      </aside>
    </section>
  );
}

function formatTicketNumber(ticketNumber: string) {
  return ticketNumber.replace(/^D-?/i, "").replace(/^T-?/i, "");
}

function formatTicketStatus(status: string) {
  const labels: Record<string, string> = {
    waiting: "en attente",
    assigned: "affecté",
    in_service: "en cabine",
    ready_for_checkout: "en caisse",
    in_checkout: "encaissement",
    paid: "payé",
    cancelled: "annulé",
  };

  return labels[status] || status;
}

function formatShortTime(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit" });
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("fr-CH", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatCurrency(value: number, currency?: "CHF" | "EUR" | null) {
  if (!currency) return formatNumber(value);
  return new Intl.NumberFormat("fr-CH", {
    style: "currency",
    currency,
  }).format(value);
}
