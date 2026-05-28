import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPatch, apiPost, WS_BASE_URL } from "./api/client";
import { AppointmentPanel } from "./components/AppointmentPanel";
import { InstituteDashboard } from "./components/InstituteDashboard";
import { PlanningBoard } from "./components/PlanningBoard";
import { QueuePanel } from "./components/QueuePanel";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import type {
  Appointment,
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
  const [ticketServiceMap, setTicketServiceMap] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [realtimeStatus, setRealtimeStatus] = useState<"connected" | "connecting" | "disconnected">("disconnected");

  const selectedInstitute = useMemo(
    () => institutes.find((institute) => institute.id === selectedInstituteId),
    [institutes, selectedInstituteId]
  );

  const selectedTicket = useMemo(
    () => tickets.find((ticket) => ticket.id === selectedTicketId),
    [tickets, selectedTicketId]
  );

  function handleTicketSelection(ticketId: string) {
    setSelectedTicketId(ticketId);

    const ticket = tickets.find((item) => item.id === ticketId);
    if (ticket?.assigned_employee_id) {
      setSelectedEmployeeId(ticket.assigned_employee_id);
    }
  }

  function handleEmployeeSelection(employeeId: string) {
    if (selectedTicket?.assigned_employee_id && selectedTicket.assigned_employee_id !== employeeId) {
      setError("Ce ticket est déjà affecté à une autre collaboratrice.");
      return;
    }

    setSelectedEmployeeId(employeeId);
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
      setTicketServiceMap((current) => ({ ...current, [created.id]: selectedServiceId }));
      setSelectedTicketId(created.id);
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de créer le ticket");
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

    const serviceId = ticketServiceMap[selectedTicketId] || selectedServiceId;
    if (!serviceId) {
      setError("Choisis une prestation avant de démarrer la session.");
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

  async function handleCancelAppointment(appointmentId: string) {
    setError(null);
    try {
      await apiPatch<Appointment>(`/appointments/${appointmentId}/cancel`);
      await refreshOperationalData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible d’annuler le rendez-vous");
    }
  }

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="content-shell">
        <TopBar
          institutes={institutes}
          selectedInstituteId={selectedInstituteId}
          realtimeStatus={realtimeStatus}
          onInstituteChange={setSelectedInstituteId}
          onRefresh={refreshOperationalData}
        />

        {error && <div className="error-banner">{error}</div>}
        {loading && <div className="loading-banner">Chargement des données...</div>}

        <div className="workspace">
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
          />

          <div className="main-column">
            <div className="context-card">
              <div>
                <p className="eyebrow">Institut actif</p>
                <h2>{selectedInstitute?.name || "Aucun institut"}</h2>
                <span>{selectedInstitute?.address || "Adresse non renseignée"}</span>
              </div>
              <div className="time-card availability-highlight">
                <span>Prochaine disponibilité</span>
                <strong>{formatAvailabilityHeadline(availability)}</strong>
                <small>{formatAvailabilityDetail(availability)}</small>
              </div>
            </div>

            <InstituteDashboard dashboard={dashboard} />

            <AppointmentPanel
              instituteId={selectedInstituteId}
              employees={employees}
              services={services}
              appointments={appointments}
              onCreateAppointment={handleCreateAppointment}
              onCancelAppointment={handleCancelAppointment}
            />

            <PlanningBoard
              planning={planning}
              employees={employees}
              services={services}
              appointments={appointments}
              availability={availability}
              onFinishSession={handleFinishSession}
              onExtendSession={handleExtendSession}
              onChangeEmployeeStatus={handleChangeEmployeeStatus}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function formatAvailabilityHeadline(availability?: PlanningAvailability) {
  if (!availability) return "Calcul en cours";

  if (availability.wait_minutes === null || availability.wait_minutes === undefined) {
    return availability.active_sessions > 0
      ? "Disponibilité à confirmer"
      : "Aucune disponibilité";
  }

  if (availability.wait_minutes <= 0) {
    return `${availability.next_employee_name || "Une collaboratrice"} disponible maintenant`;
  }

  return `${availability.wait_minutes} min d’attente`;
}

function formatAvailabilityDetail(availability?: PlanningAvailability) {
  if (!availability) return "Calcul de disponibilité en cours.";

  const delayedCount = availability.employees.filter(
    (employee) => employee.employee_status === "delayed"
  ).length;

  if (!availability.next_available_at) {
    return delayedCount > 0
      ? `${delayedCount} prestation(s) en retard à clôturer avant de libérer la disponibilité.`
      : "Toutes les collaboratrices sont indisponibles.";
  }

  const time = new Intl.DateTimeFormat("fr-CH", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(availability.next_available_at));

  const delayText = delayedCount > 0 ? ` · ${delayedCount} retard à clôturer` : "";
  return `${availability.next_employee_name || "Prochain créneau"} à ${time}${delayText}`;
}
