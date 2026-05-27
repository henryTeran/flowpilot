import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPatch, apiPost, WS_BASE_URL } from "./api/client";
import { PlanningBoard } from "./components/PlanningBoard";
import { QueuePanel } from "./components/QueuePanel";
import { TopBar } from "./components/TopBar";
import type { Employee, Institute, PlanningDay, QueueTicket, Service, ServiceCategory } from "./types";

export default function App() {
  const [institutes, setInstitutes] = useState<Institute[]>([]);
  const [selectedInstituteId, setSelectedInstituteId] = useState("");
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [categories, setCategories] = useState<ServiceCategory[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [tickets, setTickets] = useState<QueueTicket[]>([]);
  const [planning, setPlanning] = useState<PlanningDay | undefined>();
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
      const [employeesResponse, ticketsResponse, planningResponse] = await Promise.all([
        apiGet<Employee[]>(`/employees?institute_id=${encodeURIComponent(selectedInstituteId)}`),
        apiGet<QueueTicket[]>(`/tickets/waiting?institute_id=${encodeURIComponent(selectedInstituteId)}`),
        apiGet<PlanningDay>(`/planning/institutes/${encodeURIComponent(selectedInstituteId)}/today`),
      ]);

      setEmployees(employeesResponse);
      setTickets(ticketsResponse);
      setPlanning(planningResponse);
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
    const serviceId = ticketServiceMap[selectedTicketId] || selectedServiceId;
    if (!serviceId) {
      setError("Choisis une prestation avant de démarrer la session.");
      return;
    }

    setError(null);
    try {
      await apiPatch<QueueTicket>(`/tickets/${selectedTicketId}/assign`, {
        employee_id: selectedEmployeeId,
      });
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

  return (
    <div className="app-shell">
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
          selectedCategoryId={selectedCategoryId}
          selectedServiceId={selectedServiceId}
          selectedTicketId={selectedTicketId}
          selectedEmployeeId={selectedEmployeeId}
          ticketServiceMap={ticketServiceMap}
          onCategoryChange={setSelectedCategoryId}
          onServiceChange={setSelectedServiceId}
          onTicketChange={setSelectedTicketId}
          onEmployeeChange={setSelectedEmployeeId}
          onCreateTicket={handleCreateTicket}
          onAssignTicket={handleAssignTicket}
          onStartSession={handleStartSession}
        />

        <div className="main-column">
          <div className="context-card">
            <div>
              <p className="eyebrow">Institut actif</p>
              <h2>{selectedInstitute?.name || "Aucun institut"}</h2>
              <span>{selectedInstitute?.address || "Adresse non renseignée"}</span>
            </div>
            <div className="time-card">
              <span>Objectif terrain</span>
              <strong>annoncer l’attente en moins de 10 s</strong>
            </div>
          </div>

          <PlanningBoard
            planning={planning}
            employees={employees}
            services={services}
            onFinishSession={handleFinishSession}
            onExtendSession={handleExtendSession}
          />
        </div>
      </div>
    </div>
  );
}
