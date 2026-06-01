import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPatch, apiPost, WS_BASE_URL } from "./api/client";
import { ActionDrawer } from "./components/ActionDrawer";
import { AppointmentPanel } from "./components/AppointmentPanel";
import { BodyMinuteSidebar } from "./components/BodyMinuteSidebar";
import { CompactQueuePanel } from "./components/CompactQueuePanel";
import { DemoTools } from "./components/DemoTools";
import { EmployeeIdentityModal, type IdentityContext } from "./components/EmployeeIdentityModal";
import { InstituteDashboard } from "./components/InstituteDashboard";
import { NewTicketWorkflow, type NewTicketWorkflowResult } from "./components/NewTicketWorkflow";
import { PlanningBoard } from "./components/PlanningBoard";
import { QueuePanel } from "./components/QueuePanel";
import type {
  Appointment,
  AppointmentAction,
  AppointmentCreatePayload,
  Employee,
  Institute,
  InstituteDashboardRead,
  PlanningAvailability,
  PlanningDay,
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
  const [dashboard, setDashboard] = useState<InstituteDashboardRead | undefined>();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedServiceId, setSelectedServiceId] = useState("");
  const [selectedTicketId, setSelectedTicketId] = useState("");
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [identifiedEmployeeId, setIdentifiedEmployeeId] = useState("");
  const [ticketServiceMap, setTicketServiceMap] = useState<Record<string, string[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [realtimeStatus, setRealtimeStatus] = useState<"connected" | "connecting" | "disconnected">("disconnected");
  const [activeDrawer, setActiveDrawer] = useState<"newTicket" | "tickets" | "appointments" | "dashboard" | "demo" | null>(null);
  const [identityModalOpen, setIdentityModalOpen] = useState(false);
  const [identityContext, setIdentityContext] = useState<IdentityContext>("general");
  const [afterIdentityAction, setAfterIdentityAction] = useState<"newTicket" | null>(null);
  const [ticketWorkflowOpen, setTicketWorkflowOpen] = useState(false);

  const selectedInstitute = useMemo(
    () => institutes.find((institute) => institute.id === selectedInstituteId),
    [institutes, selectedInstituteId]
  );

  const selectedTicket = useMemo(
    () => tickets.find((ticket) => ticket.id === selectedTicketId),
    [tickets, selectedTicketId]
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

  function openIdentity(context: IdentityContext, afterAction: "newTicket" | null = null) {
    setIdentityContext(context);
    setAfterIdentityAction(afterAction);
    setIdentityModalOpen(true);
  }

  function handleIdentifyEmployee(employeeId: string) {
    setIdentifiedEmployeeId(employeeId);
    if (!selectedEmployeeId) setSelectedEmployeeId(employeeId);

    if (afterIdentityAction === "newTicket") {
      setTicketWorkflowOpen(true);
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
      const [employeesResponse, ticketsResponse, planningResponse, availabilityResponse, dashboardResponse, appointmentsResponse] = await Promise.all([
        apiGet<Employee[]>(`/employees?institute_id=${encodeURIComponent(selectedInstituteId)}`),
        apiGet<QueueTicket[]>(`/tickets/waiting?institute_id=${encodeURIComponent(selectedInstituteId)}`),
        apiGet<PlanningDay>(`/planning/institutes/${encodeURIComponent(selectedInstituteId)}/today`),
        apiGet<PlanningAvailability>(`/planning/institutes/${encodeURIComponent(selectedInstituteId)}/availability`),
        apiGet<InstituteDashboardRead>(`/dashboard/institutes/${encodeURIComponent(selectedInstituteId)}/live`),
        apiGet<Appointment[]>(`/appointments?institute_id=${encodeURIComponent(selectedInstituteId)}`),
      ]);

      setEmployees(employeesResponse);
      setTickets(ticketsResponse);
      setPlanning(planningResponse);
      setAvailability(availabilityResponse);
      setDashboard(dashboardResponse);
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
  }, [tickets, selectedTicketId]);

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
    const serviceId = selectedTicketServiceIds.includes(selectedServiceId)
      ? selectedServiceId
      : getNextPendingTicketServiceId(selectedTicket, ticketServiceMap);

    if (!serviceId) {
      setError("Choisis une prestation du ticket avant de démarrer la session.");
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
      setError(err instanceof Error ? err.message : "Impossible de démarrer la prestation");
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

  return (
    <div className="bm-app-shell">
      <BodyMinuteSidebar
        activeItem="Accueil"
        onOpenTickets={() => setActiveDrawer("tickets")}
        onOpenDashboard={() => setActiveDrawer("dashboard")}
      />

      <div className="bm-content-shell">
        <header className="bm-top-strip">
          <div className="bm-top-left">
            <p>Accueil / Planning</p>
            <h1>Planning institut</h1>
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

          <div className="bm-primary-actions">
            <button type="button" className="bm-main-action" onClick={() => openIdentity("create_ticket", "newTicket")}>
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
          />
        </main>

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
          open={activeDrawer === "dashboard"}
          title="Chiffres"
          subtitle="Indicateurs opérationnels provisoires avant module chiffres complet."
          onClose={() => setActiveDrawer(null)}
        >
          <InstituteDashboard dashboard={dashboard} />
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
          categories={categories}
          services={services}
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
