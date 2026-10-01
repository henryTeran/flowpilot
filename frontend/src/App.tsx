import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPatch, apiPost, WS_BASE_URL } from "./api/client";
import { ActionDrawer } from "./components/ActionDrawer";
import { AppointmentPanel } from "./components/AppointmentPanel";
import { FlowPilotSidebar } from "./components/FlowPilotSidebar";
import { CheckoutPanel } from "./components/CheckoutPanel";
import { ChiffresPanel } from "./components/ChiffresPanel";
import { CompactQueuePanel } from "./components/CompactQueuePanel";
import { DemoTools } from "./components/DemoTools";
import { EmployeeIdentityModal, type IdentityContext } from "./components/EmployeeIdentityModal";
import { NewTicketWorkflow, type NewTicketWorkflowResult } from "./components/NewTicketWorkflow";
import { PlanningBoard } from "./components/PlanningBoard";
import { resolveNextCheckoutTicket } from "./checkout-utils";
import { QueuePanel } from "./components/QueuePanel";
import { TicketsHomePanel } from "./components/TicketsHomePanel";
import type {
  Appointment,
  AppointmentAction,
  AppointmentCreatePayload,
  Employee,
  Institute,
  ChiffresSummary,
  PlanningAvailability,
  PlanningDay,
  PaymentMethod,
  QueueTicket,
  Service,
  ServiceCategory,
} from "./types";

export default function App() {
  const [institutes, setInstitutes] = useState<Institute[]>([]);
  const [selectedInstituteId, setSelectedInstituteId] = useState("");
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [categories, setCategories] = useState<ServiceCategory[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [tickets, setTickets] = useState<QueueTicket[]>([]);
  const [planning, setPlanning] = useState<PlanningDay | undefined>();
  const [availability, setAvailability] = useState<PlanningAvailability | undefined>();
  const [chiffres, setChiffres] = useState<ChiffresSummary | undefined>();
  const [chiffresLoading, setChiffresLoading] = useState(false);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedServiceId, setSelectedServiceId] = useState("");
  const [selectedTicketId, setSelectedTicketId] = useState("");
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [identifiedEmployeeId, setIdentifiedEmployeeId] = useState("");
  const [selectedCheckoutTicketId, setSelectedCheckoutTicketId] = useState("");
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<PaymentMethod>("cb");
  const [ticketServiceMap, setTicketServiceMap] = useState<Record<string, string[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [realtimeStatus, setRealtimeStatus] = useState<"connected" | "connecting" | "disconnected">("disconnected");
  const [activeDrawer, setActiveDrawer] = useState<"newTicket" | "tickets" | "checkout" | "appointments" | "dashboard" | "demo" | null>(null);
  const [mainView, setMainView] = useState<"planning" | "tickets" | "chiffres">("planning");
  const [identityModalOpen, setIdentityModalOpen] = useState(false);
  const [identityContext, setIdentityContext] = useState<IdentityContext>("general");
  const [afterIdentityAction, setAfterIdentityAction] = useState<"newTicket" | "checkout" | null>(null);
  const [ticketWorkflowOpen, setTicketWorkflowOpen] = useState(false);

  const selectedInstitute = useMemo(
    () => institutes.find((institute) => institute.id === selectedInstituteId),
    [institutes, selectedInstituteId]
  );

  const selectedTicket = useMemo(
    () => tickets.find((ticket) => ticket.id === selectedTicketId),
    [tickets, selectedTicketId]
  );

  const selectedCheckoutTicket = useMemo(
    () => tickets.find((ticket) => ticket.id === selectedCheckoutTicketId),
    [tickets, selectedCheckoutTicketId]
  );

  const identifiedEmployee = useMemo(
    () => employees.find((employee) => employee.id === identifiedEmployeeId),
    [employees, identifiedEmployeeId]
  );

  const activeAppointmentsToday = useMemo(
    () => appointments.filter((appointment) => !["completed", "cancelled", "no_show"].includes(appointment.status)).length,
    [appointments]
  );

  const completedAppointmentsToday = useMemo(
    () => appointments.filter((appointment) => appointment.status === "completed").length,
    [appointments]
  );

  const checkoutCount = useMemo(
    () => tickets.filter((ticket) => ["ready_for_checkout", "in_checkout"].includes(ticket.status)).length,
    [tickets]
  );

  const delayedEmployeesCount = useMemo(
    () => employees.filter((employee) => employee.status === "delayed").length,
    [employees]
  );

  const ticketStats = useMemo(() => computeTicketStats(tickets), [tickets]);

  function handleTicketSelection(ticketId: string) {
    setSelectedTicketId(ticketId);

    const ticket = tickets.find((item) => item.id === ticketId);
    if (ticket?.assigned_employee_id) {
      setSelectedEmployeeId(ticket.assigned_employee_id);
    }

    const nextServiceId = getNextPendingTicketServiceId(ticket, ticketServiceMap);
    if (nextServiceId) {
      setSelectedServiceId(nextServiceId);
    }
  }

  function handleEmployeeSelection(employeeId: string) {
    if (selectedTicket?.assigned_employee_id && selectedTicket.assigned_employee_id !== employeeId) {
      setError("Ce ticket est déjà affecté à une autre collaboratrice.");
      return;
    }

    setSelectedEmployeeId(employeeId);
  }

  function openIdentity(context: IdentityContext, afterAction: "newTicket" | "checkout" | null = null) {
    setIdentityContext(context);
    setAfterIdentityAction(afterAction);
    setIdentityModalOpen(true);
  }

  async function handleIdentifyEmployee(employeeId: string) {
    setIdentifiedEmployeeId(employeeId);
    if (!selectedEmployeeId) setSelectedEmployeeId(employeeId);

    if (afterIdentityAction === "newTicket") {
      setTicketWorkflowOpen(true);
    }

    if (afterIdentityAction === "checkout" && selectedCheckoutTicketId) {
      try {
        await apiPatch<QueueTicket>(`/tickets/${selectedCheckoutTicketId}/checkout/start`, {
          employee_id: employeeId,
        });
        setActiveDrawer("checkout");
        await refreshOperationalData();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Impossible d’ouvrir l’encaissement");
      }
    }

    setAfterIdentityAction(null);
  }

  function closeIdentityModal() {
    setIdentityModalOpen(false);
    setAfterIdentityAction(null);
  }

  const loadStaticData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [institutesResponse, categoriesResponse, servicesResponse] = await Promise.all([
        apiGet<Institute[]>("/institutes"),
        apiGet<ServiceCategory[]>("/services/categories"),
        apiGet<Service[]>("/services/catalog"),
      ]);

      setInstitutes(institutesResponse);
      setCategories(categoriesResponse);
      setServices(servicesResponse);

      if (!selectedInstituteId && institutesResponse.length > 0) {
        setSelectedInstituteId(institutesResponse[0].id);
      }
      if (!selectedServiceId && servicesResponse.length > 0) {
        setSelectedServiceId(servicesResponse[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur au chargement des données");
    } finally {
      setLoading(false);
    }
  }, [selectedInstituteId, selectedServiceId]);

  const refreshOperationalData = useCallback(async () => {
    if (!selectedInstituteId) return;
    setError(null);
    try {
      const [employeesResponse, ticketsResponse, planningResponse, availabilityResponse, chiffresResponse, appointmentsResponse] = await Promise.all([
        apiGet<Employee[]>(`/employees?institute_id=${encodeURIComponent(selectedInstituteId)}`),
        apiGet<QueueTicket[]>(`/tickets/waiting?institute_id=${encodeURIComponent(selectedInstituteId)}`),
        apiGet<PlanningDay>(`/planning/institutes/${encodeURIComponent(selectedInstituteId)}/today`),
        apiGet<PlanningAvailability>(`/planning/institutes/${encodeURIComponent(selectedInstituteId)}/availability`),
        apiGet<ChiffresSummary>(`/tickets/chiffres?institute_id=${encodeURIComponent(selectedInstituteId)}`),
        apiGet<Appointment[]>(`/appointments?institute_id=${encodeURIComponent(selectedInstituteId)}`),
      ]);

      setEmployees(employeesResponse);
      setTickets(ticketsResponse);
      setPlanning(planningResponse);
      setAvailability(availabilityResponse);
      setChiffres(chiffresResponse);
      setAppointments(appointmentsResponse);
      if (!selectedEmployeeId && employeesResponse.length > 0) {
        setSelectedEmployeeId(employeesResponse[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur pendant le rafraîchissement");
    }
  }, [selectedInstituteId, selectedEmployeeId]);

  useEffect(() => {
    void loadStaticData();
  }, [loadStaticData]);

  useEffect(() => {
    void refreshOperationalData();
    const interval = window.setInterval(() => void refreshOperationalData(), 10000);
    return () => window.clearInterval(interval);
  }, [refreshOperationalData]);

  useEffect(() => {
    if (!selectedInstituteId) return;
    setRealtimeStatus("connecting");
    const socket = new WebSocket(`${WS_BASE_URL}/institutes/${selectedInstituteId}/planning`);
    const pingInterval = window.setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send("ping");
    }, 20000);

    socket.onopen = () => setRealtimeStatus("connected");
    socket.onclose = () => setRealtimeStatus("disconnected");
    socket.onerror = () => setRealtimeStatus("disconnected");
    socket.onmessage = () => void refreshOperationalData();

    return () => {
      window.clearInterval(pingInterval);
      socket.close();
    };
  }, [selectedInstituteId, refreshOperationalData]);

  useEffect(() => {
    if (selectedTicketId && !tickets.some((ticket) => ticket.id === selectedTicketId)) {
      setSelectedTicketId("");
    }
    if (selectedCheckoutTicketId && !tickets.some((ticket) => ticket.id === selectedCheckoutTicketId)) {
      setSelectedCheckoutTicketId("");
    }
  }, [tickets, selectedTicketId, selectedCheckoutTicketId]);

  async function handleCreateTicket() {
    if (!selectedInstituteId || !selectedServiceId) return;
    setError(null);
    try {
      const created = await apiPost<QueueTicket>("/tickets", {
        institute_id: selectedInstituteId,
        service_id: selectedServiceId,
      });
      setTicketServiceMap((current) => ({ ...current, [created.id]: [selectedServiceId] }));
      setSelectedTicketId(created.id);
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de créer le ticket");
    }
  }

  async function handleCreateWorkflowTicket(result: NewTicketWorkflowResult) {
    if (!selectedInstituteId || result.selectedServiceIds.length === 0) return;

    const firstServiceId = result.selectedServiceIds[0];

    setError(null);
    try {
      const created = await apiPost<QueueTicket>("/tickets", {
        institute_id: selectedInstituteId,
        service_id: firstServiceId,
        service_ids: result.selectedServiceIds,
        created_by_id: identifiedEmployeeId || undefined,
      });

      setSelectedServiceId(firstServiceId);
      setTicketServiceMap((current) => ({ ...current, [created.id]: result.selectedServiceIds }));
      setSelectedTicketId(created.id);
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de valider le nouveau ticket");
      throw err;
    }
  }

  async function handleAssignTicket() {
    if (!selectedTicketId || !selectedEmployeeId) return;

    if (!selectedTicket || selectedTicket.status !== "waiting") {
      setError("Seul un ticket en attente peut être affecté.");
      return;
    }

    setError(null);
    try {
      await apiPatch<QueueTicket>(`/tickets/${selectedTicketId}/assign`, {
        employee_id: selectedEmployeeId,
      });
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible d’affecter le ticket");
    }
  }

  async function handleStartSession() {
    if (!selectedTicketId || !selectedEmployeeId) return;

    if (!selectedTicket || !["waiting", "assigned"].includes(selectedTicket.status)) {
      setError("Ce ticket est déjà en cours ou terminé. Il ne peut plus être redémarré.");
      return;
    }

    if (selectedTicket.assigned_employee_id && selectedTicket.assigned_employee_id !== selectedEmployeeId) {
      setError("Ce ticket est déjà affecté à une autre collaboratrice.");
      return;
    }

    const selectedTicketServiceIds = getTicketServiceIds(selectedTicket, ticketServiceMap);
    const serviceId = selectedTicketServiceIds[0] || selectedServiceId;

    if (!serviceId) {
      setError("Ce ticket ne contient aucune prestation.");
      return;
    }

    setError(null);
    try {
      if (selectedTicket.status === "waiting") {
        await apiPatch<QueueTicket>(`/tickets/${selectedTicketId}/assign`, {
          employee_id: selectedEmployeeId,
        });
      }

      await apiPost("/planning/sessions/start", {
        ticket_id: selectedTicketId,
        employee_id: selectedEmployeeId,
        service_id: serviceId,
      });
      setSelectedTicketId("");
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de démarrer la séance");
    }
  }

  async function handleFinishSession(sessionId: string) {
    setError(null);
    try {
      await apiPatch(`/planning/sessions/${sessionId}/finish`);
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de terminer la prestation");
    }
  }

  async function handleFinishSessionAndCheckout(sessionId: string) {
    setError(null);
    try {
      await apiPatch(`/planning/sessions/${sessionId}/finish`);
      const refreshedTickets = await apiGet<QueueTicket[]>(`/tickets/waiting?institute_id=${encodeURIComponent(selectedInstituteId ?? "")}`);
      setTickets(refreshedTickets);

      const nextCheckoutTicket = resolveNextCheckoutTicket(refreshedTickets, identifiedEmployeeId);

      if (nextCheckoutTicket) {
        setSelectedTicketId(nextCheckoutTicket.id);
        setSelectedCheckoutTicketId(nextCheckoutTicket.id);
        if (identifiedEmployeeId) {
          setActiveDrawer("checkout");
          return;
        }
      }

      if (identifiedEmployeeId) {
        setActiveDrawer("checkout");
      } else {
        handleOpenCheckout("");
      }

      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de terminer la prestation et ouvrir la caisse");
    }
  }

  async function handleFinishActiveEmployeeSession(employeeId: string) {
    if (!selectedInstituteId) return;

    setError(null);
    try {
      await apiPatch(`/planning/institutes/${selectedInstituteId}/employees/${employeeId}/finish-active-session`);
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de clôturer la prestation active");
    }
  }

  async function handleExtendSession(sessionId: string, minutes: number) {
    setError(null);
    try {
      await apiPatch(`/planning/sessions/${sessionId}/extend`, { minutes });
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de prolonger la prestation");
    }
  }

  async function handleCancelTicket(ticketId: string) {
    setError(null);
    try {
      await apiPatch(`/tickets/${ticketId}/cancel`);
      if (selectedTicketId === ticketId) {
        setSelectedTicketId("");
      }
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible d’annuler le ticket");
    }
  }

  async function handleChangeEmployeeStatus(employeeId: string, status: string) {
    setError(null);
    try {
      await apiPatch(`/employees/${employeeId}/status`, { status });
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de modifier le statut collaboratrice");
    }
  }

  function handleOpenCheckout(ticketId: string) {
    setSelectedTicketId(ticketId);
    setSelectedCheckoutTicketId(ticketId);

    if (identifiedEmployeeId) {
      setActiveDrawer("checkout");
      return;
    }

    openIdentity("checkout", "checkout");
  }

  async function handleAddCheckoutService(serviceId: string) {
    if (!selectedCheckoutTicketId || !serviceId) return;

    setError(null);
    try {
      await apiPatch<QueueTicket>(`/tickets/${selectedCheckoutTicketId}/checkout/lines/add`, {
        service_id: serviceId,
      });
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible d’ajouter la prestation");
    }
  }

  async function handleRemoveCheckoutLine(lineId: string) {
    if (!selectedCheckoutTicketId || !lineId) return;

    setError(null);
    try {
      await apiPatch<QueueTicket>(`/tickets/${selectedCheckoutTicketId}/checkout/lines/${lineId}/remove`);
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de retirer la prestation");
    }
  }

  async function handlePayCheckout() {
    if (!selectedCheckoutTicketId || !identifiedEmployeeId) {
      setError("Identifie la collaboratrice qui encaisse avant de valider le paiement.");
      return;
    }

    setError(null);
    try {
      await apiPatch<QueueTicket>(`/tickets/${selectedCheckoutTicketId}/checkout/pay`, {
        employee_id: identifiedEmployeeId,
        payment_method: selectedPaymentMethod,
      });
      setSelectedCheckoutTicketId("");
      setSelectedTicketId("");
      setActiveDrawer(null);
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de valider le paiement");
    }
  }

  async function handleCreateAppointment(payload: AppointmentCreatePayload) {
    setError(null);
    try {
      await apiPost<Appointment>("/appointments", payload);
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de créer le rendez-vous");
      throw err;
    }
  }

  async function handleAppointmentAction(appointmentId: string, action: AppointmentAction) {
    setError(null);
    try {
      await apiPatch<Appointment>(`/appointments/${appointmentId}/${action}`);
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de modifier le rendez-vous");
      throw err;
    }
  }

  async function handleResetDemo() {
    if (!selectedInstituteId) return;
    setError(null);
    try {
      await apiPost(`/dev/reset-demo?institute_id=${encodeURIComponent(selectedInstituteId)}`);
      setSelectedTicketId("");
      setSelectedEmployeeId("");
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de réinitialiser la démo");
      throw err;
    }
  }

  async function handleCreateDemoDay() {
    if (!selectedInstituteId) return;
    setError(null);
    try {
      await apiPost(`/dev/create-demo-day?institute_id=${encodeURIComponent(selectedInstituteId)}`);
      setSelectedTicketId("");
      setSelectedEmployeeId("");
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de créer la journée de test");
      throw err;
    }
  }

  async function handleRefreshChiffres() {
    if (!selectedInstituteId) return;

    setChiffresLoading(true);
    setError(null);
    try {
      const response = await apiGet<ChiffresSummary>(
        `/tickets/chiffres?institute_id=${encodeURIComponent(selectedInstituteId)}`
      );
      setChiffres(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de charger les chiffres");
    } finally {
      setChiffresLoading(false);
    }
  }

  return (
    <div className="bm-app-shell">
      <FlowPilotSidebar
        activeItem={mainView === "chiffres" ? "Chiffres" : mainView === "tickets" ? "Tickets" : "Accueil"}
        onOpenAccueil={() => { setActiveDrawer(null); setMainView("planning"); }}
        onOpenTickets={() => { setActiveDrawer(null); setMainView("tickets"); }}
        onOpenDashboard={() => { setActiveDrawer(null); setMainView("chiffres"); }}
      />

      <div className="bm-content-shell">
        <header className="bm-top-strip">
          <div className="bm-top-left">
            <p>{getTopBreadcrumb(mainView)}</p>
            <h1>{getTopTitle(mainView)}</h1>
          </div>

          <div className="bm-top-controls">
            <select
              value={selectedInstituteId}
              onChange={(event) => setSelectedInstituteId(event.target.value)}
              aria-label="Choisir l’institut"
            >
              {institutes.map((institute) => (
                <option key={institute.id} value={institute.id}>
                  {institute.name}
                </option>
              ))}
            </select>

            <button type="button" className="bm-identity-button" onClick={() => openIdentity("general")}>
              {identifiedEmployee ? `Identifiée : ${identifiedEmployee.first_name}` : "Je m’identifie"}
            </button>

            <span className={`bm-live-state ${realtimeStatus}`}>
              {translateRealtimeStatus(realtimeStatus)}
            </span>
          </div>
        </header>

        {error && <div className="bm-banner error">{error}</div>}
        {loading && <div className="bm-banner loading">Chargement des données...</div>}

        {mainView === "planning" && (
          <>
            <section className="bm-planning-toolbar">
              <div className="bm-institute-summary">
                <span>Institut</span>
                <strong>{selectedInstitute?.name || "Aucun institut"}</strong>
                <small>{selectedInstitute?.address || selectedInstitute?.city || "Adresse non renseignée"}</small>
              </div>

              <div className="bm-toolbar-stat">
                <span>Prochaine dispo</span>
                <strong>{formatAvailabilityHeadline(availability)}</strong>
                <small>{formatAvailabilityDetail(availability)}</small>
              </div>

              <div className="bm-toolbar-stat compact">
                <span>Tickets</span>
                <strong>{tickets.length}</strong>
                <small>actif(s)</small>
              </div>

              <div className="bm-toolbar-stat compact">
                <span>RDV</span>
                <strong>{activeAppointmentsToday}</strong>
                <small>{completedAppointmentsToday} terminé(s)</small>
              </div>

              <div className="bm-toolbar-stat compact">
                <span>À encaisser</span>
                <strong>{checkoutCount}</strong>
                <small>{delayedEmployeesCount} retard(s)</small>
              </div>

              <div className="bm-primary-actions">
                <button type="button" className="bm-main-action" onClick={() => setTicketWorkflowOpen(true)}>
                  Créer nouveau ticket
                </button>
                <button type="button" className="bm-secondary-action" onClick={() => setActiveDrawer("appointments")}>
                  RDV sous appel
                </button>
              </div>
            </section>

            <main className="bm-workspace">
              <section className="bm-planning-panel">
                <div className="bm-section-title">
                  <div>
                    <span>Visualisation journée</span>
                    <h2>Collaboratrices, prestations, RDV et disponibilité</h2>
                  </div>
                  <div className="bm-section-actions">
                    <button type="button" onClick={() => void refreshOperationalData()}>Rafraîchir</button>
                    <button type="button" onClick={() => setActiveDrawer("demo")}>Démo</button>
                  </div>
                </div>

                <PlanningBoard
                  planning={planning}
                  employees={employees}
                  services={services}
                  appointments={appointments}
                  availability={availability}
                  onFinishSession={handleFinishSession}
                  onFinishAndOpenCheckout={handleFinishSessionAndCheckout}
                  onExtendSession={handleExtendSession}
                  onChangeEmployeeStatus={handleChangeEmployeeStatus}
                  onFinishActiveEmployeeSession={handleFinishActiveEmployeeSession}
                />
              </section>

              <CompactQueuePanel
                tickets={tickets}
                services={services}
                employees={employees}
                selectedTicketId={selectedTicketId}
                ticketServiceMap={ticketServiceMap}
                onTicketSelect={handleTicketSelection}
                onOpenTickets={() => setActiveDrawer("tickets")}
                onFinishActiveEmployeeSession={handleFinishActiveEmployeeSession}
                onStartCheckout={handleOpenCheckout}
              />
            </main>
          </>
        )}

        {mainView === "tickets" && (
          <main className="bm-workspace bm-workspace-full">
            <TicketsHomePanel
              tickets={tickets}
              services={services}
              employees={employees}
              ticketStats={ticketStats}
              onCreateTicket={() => setTicketWorkflowOpen(true)}
              onRefresh={refreshOperationalData}
              onManageTicket={(ticket) => {
                handleTicketSelection(ticket.id);
                if (isCheckoutTicket(ticket.status)) {
                  handleOpenCheckout(ticket.id);
                } else {
                  setMainView("planning");
                }
              }}
            />
          </main>
        )}

        {mainView === "chiffres" && (
          <main className="bm-workspace bm-workspace-full">
            <ChiffresPanel
              chiffres={chiffres}
              loading={chiffresLoading}
              onRefresh={handleRefreshChiffres}
            />
          </main>
        )}

        <ActionDrawer
          open={activeDrawer === "newTicket"}
          title="Créer un nouveau ticket"
          subtitle={identifiedEmployee ? `Créateur identifié : ${identifiedEmployee.first_name}` : "Identification collaboratrice obligatoire avant création."}
          onClose={() => setActiveDrawer(null)}
        >
          <QueuePanel
            tickets={tickets}
            services={services}
            categories={categories}
            employees={employees}
            availability={availability}
            selectedCategoryId={selectedCategoryId}
            selectedServiceId={selectedServiceId}
            selectedTicketId={selectedTicketId}
            selectedEmployeeId={selectedEmployeeId}
            ticketServiceMap={ticketServiceMap}
            onCategoryChange={setSelectedCategoryId}
            onServiceChange={setSelectedServiceId}
            onTicketChange={handleTicketSelection}
            onEmployeeChange={handleEmployeeSelection}
            onCreateTicket={handleCreateTicket}
            onAssignTicket={handleAssignTicket}
            onStartSession={handleStartSession}
            onCancelTicket={handleCancelTicket}
            onFinishActiveEmployeeSession={handleFinishActiveEmployeeSession}
            onStartCheckout={handleOpenCheckout}
          />
        </ActionDrawer>

        <ActionDrawer
          open={activeDrawer === "tickets"}
          title="Tickets"
          subtitle="Tickets en attente, affectés ou en prestation."
          onClose={() => setActiveDrawer(null)}
        >
          <QueuePanel
            tickets={tickets}
            services={services}
            categories={categories}
            employees={employees}
            availability={availability}
            selectedCategoryId={selectedCategoryId}
            selectedServiceId={selectedServiceId}
            selectedTicketId={selectedTicketId}
            selectedEmployeeId={selectedEmployeeId}
            ticketServiceMap={ticketServiceMap}
            onCategoryChange={setSelectedCategoryId}
            onServiceChange={setSelectedServiceId}
            onTicketChange={handleTicketSelection}
            onEmployeeChange={handleEmployeeSelection}
            onCreateTicket={handleCreateTicket}
            onAssignTicket={handleAssignTicket}
            onStartSession={handleStartSession}
            onCancelTicket={handleCancelTicket}
            onFinishActiveEmployeeSession={handleFinishActiveEmployeeSession}
            onStartCheckout={handleOpenCheckout}
          />
        </ActionDrawer>

        <ActionDrawer
          open={activeDrawer === "checkout"}
          title="Encaissement"
          subtitle={identifiedEmployee ? `Collaboratrice identifiée : ${identifiedEmployee.first_name}` : "Ré-identification obligatoire avant paiement."}
          onClose={() => setActiveDrawer(null)}
        >
          <CheckoutPanel
            ticket={selectedCheckoutTicket}
            services={services}
            employees={employees}
            cashierEmployee={identifiedEmployee}
            selectedPaymentMethod={selectedPaymentMethod}
            onPaymentMethodChange={setSelectedPaymentMethod}
            onAddService={handleAddCheckoutService}
            onRemoveLine={handleRemoveCheckoutLine}
            onPay={handlePayCheckout}
            onClose={() => setActiveDrawer(null)}
            onCancelTicket={handleCancelTicket}
            onReidentify={() => openIdentity("checkout", "checkout")}
          />
        </ActionDrawer>

        <ActionDrawer
          open={activeDrawer === "appointments"}
          title="Rendez-vous sous appel"
          subtitle="Créer un RDV et le visualiser dans le planning."
          onClose={() => setActiveDrawer(null)}
        >
          <AppointmentPanel
            instituteId={selectedInstituteId}
            employees={employees}
            services={services}
            appointments={appointments}
            onCreateAppointment={handleCreateAppointment}
            onAppointmentAction={handleAppointmentAction}
          />
        </ActionDrawer>

        <ActionDrawer
          open={activeDrawer === "demo"}
          title="Mode démonstration"
          subtitle="Réinitialiser ou générer une journée de test."
          onClose={() => setActiveDrawer(null)}
        >
          <DemoTools
            disabled={!selectedInstituteId}
            onResetDemo={handleResetDemo}
            onCreateDemoDay={handleCreateDemoDay}
            onRefresh={refreshOperationalData}
          />
        </ActionDrawer>

        <NewTicketWorkflow
          open={ticketWorkflowOpen}
          creatorEmployee={identifiedEmployee}
          ticketStats={ticketStats}
          categories={categories}
          services={services}
          onRequestIdentity={() => openIdentity("create_ticket")}
          onClose={() => setTicketWorkflowOpen(false)}
          onValidate={handleCreateWorkflowTicket}
        />

        <EmployeeIdentityModal
          open={identityModalOpen}
          employees={employees}
          identifiedEmployeeId={identifiedEmployeeId}
          context={identityContext}
          onIdentify={handleIdentifyEmployee}
          onClose={closeIdentityModal}
        />
      </div>
    </div>
  );
}


function computeTicketStats(tickets: QueueTicket[]) {
  const waitingStatuses = new Set(["waiting", "assigned", "in_service", "in_progress"]);
  const checkoutStatuses = new Set(["ready_for_checkout", "in_checkout", "checkout"]);
  const paidStatuses = new Set(["paid", "completed"]);

  return tickets.reduce(
    (stats, ticket) => {
      const amount = ticket.total_amount ?? ticket.lines?.reduce((sum, line) => sum + (line.total ?? 0), 0) ?? 0;

      if (checkoutStatuses.has(ticket.status)) {
        stats.checkoutCount += 1;
        stats.checkoutAmount += amount;
      } else if (paidStatuses.has(ticket.status)) {
        stats.salesCount += 1;
        stats.salesAmount += amount;
      } else if (waitingStatuses.has(ticket.status)) {
        stats.waitingCount += 1;
        stats.waitingAmount += amount;
      }

      return stats;
    },
    {
      waitingCount: 0,
      waitingAmount: 0,
      checkoutCount: 0,
      checkoutAmount: 0,
      salesCount: 0,
      salesAmount: 0,
    }
  );
}

function isCheckoutTicket(status: string) {
  return ["ready_for_checkout", "in_checkout", "checkout"].includes(status);
}

function getTopBreadcrumb(view: "planning" | "tickets" | "chiffres") {
  if (view === "tickets") return "Accueil / Tickets";
  if (view === "chiffres") return "Accueil / Chiffres";
  return "Accueil / Planning";
}

function getTopTitle(view: "planning" | "tickets" | "chiffres") {
  if (view === "tickets") return "Tickets";
  if (view === "chiffres") return "Chiffres";
  return "Planning institut";
}

function getTicketServiceIds(ticket: QueueTicket | undefined, fallbackMap: Record<string, string[]>) {
  if (!ticket) return [];

  if (ticket.lines && ticket.lines.length > 0) {
    return ticket.lines.map((line) => line.service_id);
  }

  return fallbackMap[ticket.id] || [];
}

function getNextPendingTicketServiceId(ticket: QueueTicket | undefined, fallbackMap: Record<string, string[]>) {
  if (!ticket) return "";

  const pendingLine = ticket.lines?.find((line) => line.status !== "completed" && line.status !== "in_progress");
  if (pendingLine) return pendingLine.service_id;

  const activeLine = ticket.lines?.find((line) => line.status === "in_progress");
  if (activeLine) return activeLine.service_id;

  return fallbackMap[ticket.id]?.[0] || "";
}

function formatAvailabilityHeadline(availability?: PlanningAvailability) {
  if (!availability) return "Calcul en cours";

  if (availability.wait_minutes === null || availability.wait_minutes === undefined) {
    return availability.active_sessions > 0
      ? "À confirmer"
      : "Aucune disponibilité";
  }

  if (availability.wait_minutes <= 0) {
    return `${availability.next_employee_name || "Une collaboratrice"} maintenant`;
  }

  return `${availability.wait_minutes} min`;
}

function formatAvailabilityDetail(availability?: PlanningAvailability) {
  if (!availability) return "Calcul de disponibilité en cours.";

  const delayedCount = availability.employees.filter(
    (employee) => employee.employee_status === "delayed"
  ).length;

  if (!availability.next_available_at) {
    return delayedCount > 0
      ? `${delayedCount} prestation(s) en retard à clôturer.`
      : "Toutes les collaboratrices sont indisponibles.";
  }

  const time = new Intl.DateTimeFormat("fr-CH", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(availability.next_available_at));

  const delayText = delayedCount > 0 ? ` · ${delayedCount} retard` : "";
  return `${availability.next_employee_name || "Prochain créneau"} à ${time}${delayText}`;
}

function translateRealtimeStatus(status: "connected" | "connecting" | "disconnected") {
  const labels = {
    connected: "Temps réel actif",
    connecting: "Connexion...",
    disconnected: "Hors ligne",
  };
  return labels[status];
}
