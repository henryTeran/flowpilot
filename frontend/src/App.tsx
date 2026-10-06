import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getAccessToken, getOperatorRole } from "./api/session";
import { createArrivalIntent, createExtensionIntents, compareQueueArrival } from "./queue-utils";
import { apiGet, apiPatch, apiPost, WS_BASE_URL } from "./api/client";
import { ActionDrawer } from "./components/ActionDrawer";
import { AppointmentPanel } from "./components/AppointmentPanel";
import { FlowPilotSidebar } from "./components/FlowPilotSidebar";
import { CheckoutPanel } from "./components/CheckoutPanel";
import { InventoryPanel } from "./components/InventoryPanel";
import { CommercePanel } from "./components/CommercePanel";
import { ChiffresPanel } from "./components/ChiffresPanel";
import { PaymentCashflows } from "./components/PaymentCashflows";
import { CompactQueuePanel } from "./components/CompactQueuePanel";
import { DemoTools } from "./components/DemoTools";
import { EmployeeIdentityModal, type IdentityContext } from "./components/EmployeeIdentityModal";
import { NewTicketWorkflow, type NewTicketWorkflowResult } from "./components/NewTicketWorkflow";
import { PlanningBoard } from "./components/PlanningBoard";
import { resolveNextCheckoutTicket, resolveSessionCheckoutTicket } from "./checkout-utils";
import { QueuePanel } from "./components/QueuePanel";
import { useAssignmentOptions } from "./features/useAssignmentOptions";
import { connectPlanning } from "./features/planningConnection";
import { createRefreshGate } from "./features/refreshGate";
import { TicketsHomePanel } from "./components/TicketsHomePanel";
import type {
  Appointment,
  AppointmentAction,
  AppointmentCreatePayload,
  AppointmentUpdatePayload,
  Employee,
  Institute,
  ChiffresSummary,
  PlanningAvailability,
  PlanningDay,
  PaymentMethod,
  QueueTicket,
  Service,
  ServiceCategory,
  ServiceSession,
} from "./types";

export default function App({ onLogout }: { onLogout?: () => void } = {}) {
  const [institutes, setInstitutes] = useState<Institute[]>([]);
  const [selectedInstituteId, setSelectedInstituteId] = useState("");
  const operationalRefreshGate = useRef(createRefreshGate());
  operationalRefreshGate.current.setContext(selectedInstituteId);
  useEffect(() => () => operationalRefreshGate.current.invalidate(), []);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [categories, setCategories] = useState<ServiceCategory[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [tickets, setTickets] = useState<QueueTicket[]>([]);
  const [planning, setPlanning] = useState<PlanningDay | undefined>();
  const [availability, setAvailability] = useState<PlanningAvailability | undefined>();
  const [chiffres, setChiffres] = useState<ChiffresSummary | undefined>();
  const [chiffresLoading, setChiffresLoading] = useState(false);
  const chiffresReadSequence = useRef(0);
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
  const [mainView, setMainView] = useState<"planning" | "tickets" | "chiffres" | "offres" | "inventory">("planning");
  const [identityModalOpen, setIdentityModalOpen] = useState(false);
  const [identityContext, setIdentityContext] = useState<IdentityContext>("general");
  const [afterIdentityAction, setAfterIdentityAction] = useState<"newTicket" | "checkout" | null>(null);
  const [ticketWorkflowOpen, setTicketWorkflowOpen] = useState(false);
  const arrivalIntent = useRef(createArrivalIntent());
  const workflowIntent = useRef(createArrivalIntent());
  const arrivalSubmitting = useRef(false);
  const extensionIntents = useRef(createExtensionIntents());
  const extendingSessions = useRef(new Set<string>());

  useEffect(() => {
    setEmployees([]); setTickets([]); setPlanning(undefined); setAvailability(undefined);
    chiffresReadSequence.current++;
    setChiffres(undefined); setAppointments([]); setTicketServiceMap({});
    setSelectedTicketId(""); setSelectedCheckoutTicketId(""); setSelectedEmployeeId("");
    setIdentifiedEmployeeId(""); setActiveDrawer(null); setIdentityModalOpen(false); setTicketWorkflowOpen(false);
    setAfterIdentityAction(null); setChiffresLoading(false); setError(null);
  }, [selectedInstituteId]);

  const selectedInstitute = useMemo(
    () => institutes.find((institute) => institute.id === selectedInstituteId),
    [institutes, selectedInstituteId]
  );

  const selectedTicket = useMemo(
    () => tickets.find((ticket) => ticket.id === selectedTicketId),
    [tickets, selectedTicketId]
  );
  const assignment = useAssignmentOptions(selectedInstituteId, selectedTicket);
  useEffect(() => {
    if (selectedTicket?.assigned_employee_id) {
      setSelectedEmployeeId(selectedTicket.assigned_employee_id);
      return;
    }
    if (assignment.status !== "ready") return;
    if (!assignment.options.some((option) => option.employee_id === selectedEmployeeId && option.assignable)) {
      const next = assignment.options.find((option) => option.assignable);
      if (next) setSelectedEmployeeId(next.employee_id);
    }
  }, [assignment.status, assignment.options, selectedEmployeeId, selectedTicket?.assigned_employee_id]);

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

  function captureOperationalContext() {
    const stamp = operationalRefreshGate.current.captureContext();
    const token = getAccessToken();
    return () => operationalRefreshGate.current.sameContext(stamp) && token === getAccessToken();
  }

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
    const isCurrent = captureOperationalContext();
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
        if (!isCurrent()) return;
        setActiveDrawer("checkout");
        await refreshOperationalData();
      } catch (err) {
        if (!isCurrent()) return;
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
    if (!selectedInstituteId) return false;
    const request = operationalRefreshGate.current.begin(selectedInstituteId);
    if (request === null) return false;
    const token = getAccessToken();
    const reportRequest = ++chiffresReadSequence.current;
    setChiffresLoading(true);
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

      if (!operationalRefreshGate.current.current(request) || token !== getAccessToken() || reportRequest !== chiffresReadSequence.current) return false;
      setEmployees(employeesResponse);
      setTickets(ticketsResponse);
      setPlanning(planningResponse);
      setAvailability(availabilityResponse);
      setChiffres(chiffresResponse);
      setAppointments(appointmentsResponse);
      setSelectedEmployeeId(current => employeesResponse.some(employee => employee.id === current)
        ? current : employeesResponse[0]?.id || "");
      return true;
    } catch (err) {
      if (!operationalRefreshGate.current.current(request) || token !== getAccessToken() || reportRequest !== chiffresReadSequence.current) return false;
      setChiffres(undefined);
      setError(err instanceof Error ? err.message : "Erreur pendant le rafraîchissement");
      return false;
    } finally {
      if (operationalRefreshGate.current.current(request) && token === getAccessToken() && reportRequest === chiffresReadSequence.current) setChiffresLoading(false);
    }
  }, [selectedInstituteId]);

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
    return connectPlanning({
      url: `${WS_BASE_URL}/institutes/${encodeURIComponent(selectedInstituteId)}/planning?token=${encodeURIComponent(getAccessToken() || "")}`,
      onStatus: setRealtimeStatus,
      onRefresh: () => void refreshOperationalData(),
    });
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
    const isCurrent = captureOperationalContext();
    if (!selectedInstituteId || !selectedServiceId || arrivalSubmitting.current) return;
    arrivalSubmitting.current = true;
    setError(null);
    try {
      const created = await apiPost<QueueTicket>("/tickets", {
        institute_id: selectedInstituteId,
        service_id: selectedServiceId,
        idempotency_key: arrivalIntent.current.keyFor({ institute_id: selectedInstituteId, service_ids: [selectedServiceId] }),
      });
      if (!isCurrent()) return;
      arrivalIntent.current.complete();
      setTickets((current) => [...current.filter((ticket) => ticket.id !== created.id), created].sort(compareQueueArrival));
      setTicketServiceMap((current) => ({ ...current, [created.id]: [selectedServiceId] }));
      setSelectedTicketId(created.id);
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de créer le ticket");
    } finally {
      arrivalSubmitting.current = false;
    }
  }

  async function handleCreateWorkflowTicket(result: NewTicketWorkflowResult) {
    const isCurrent = captureOperationalContext();
    if (!selectedInstituteId || result.selectedServiceIds.length === 0) return;

    const firstServiceId = result.selectedServiceIds[0];

    setError(null);
    try {
      const created = await apiPost<QueueTicket>("/tickets", {
        institute_id: selectedInstituteId,
        service_id: firstServiceId,
        service_ids: result.selectedServiceIds,
        customer_id: result.customer.customerId,
        created_by_id: identifiedEmployeeId || undefined,
        idempotency_key: workflowIntent.current.keyFor({ institute_id: selectedInstituteId, service_ids: result.selectedServiceIds, created_by_id: identifiedEmployeeId || undefined, customer_id: result.customer.customerId }),
      });
      if (!isCurrent()) return;
      workflowIntent.current.complete();
      setTickets((current) => [...current.filter((ticket) => ticket.id !== created.id), created].sort(compareQueueArrival));

      setSelectedServiceId(firstServiceId);
      setTicketServiceMap((current) => ({ ...current, [created.id]: result.selectedServiceIds }));
      setSelectedTicketId(created.id);
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de valider le nouveau ticket");
      throw err;
    }
  }

  async function handleUnassignTicket() {
    const isCurrent = captureOperationalContext();
    if (!selectedTicketId) return;
    setError(null);
    try {
      await apiPatch<QueueTicket>(`/tickets/${selectedTicketId}/unassign`);
      if (!isCurrent()) return;
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de remettre le ticket en attente");
    }
  }

  async function handleAssignTicket() {
    const isCurrent = captureOperationalContext();
    if (!selectedTicketId || !selectedEmployeeId) return;
    if (assignment.status !== "ready" || !assignment.options.some((option) => option.employee_id === selectedEmployeeId && option.assignable)) return;

    if (!selectedTicket || selectedTicket.status !== "waiting") {
      setError("Seul un ticket en attente peut être affecté.");
      return;
    }

    setError(null);
    try {
      await apiPatch<QueueTicket>(`/tickets/${selectedTicketId}/assign`, {
        employee_id: selectedEmployeeId,
      });
      if (!isCurrent()) return;
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible d’affecter le ticket");
    }
  }

  async function handleStartSession() {
    const isCurrent = captureOperationalContext();
    if (!selectedTicketId || !selectedEmployeeId) return;
    if (assignment.status !== "ready" || !assignment.options.some((option) => option.employee_id === selectedEmployeeId && option.assignable)) return;

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
        if (!isCurrent()) return;
      }

      await apiPost("/planning/sessions/start", {
        ticket_id: selectedTicketId,
        employee_id: selectedEmployeeId,
        service_id: serviceId,
      });
      if (!isCurrent()) return;
      setSelectedTicketId("");
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de démarrer la séance");
    }
  }

  async function handleFinishSession(sessionId: string) {
    const isCurrent = captureOperationalContext();
    setError(null);
    try {
      await apiPatch(`/planning/sessions/${sessionId}/finish`);
      if (!isCurrent()) return;
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de terminer la prestation");
    }
  }

  async function handleFinishSessionAndCheckout(sessionId: string) {
    const isCurrent = captureOperationalContext();
    setError(null);
    try {
      const finished = await apiPatch<ServiceSession>(`/planning/sessions/${sessionId}/finish`);
      if (!isCurrent()) return;
      const refreshedTickets = await apiGet<QueueTicket[]>(`/tickets/waiting?institute_id=${encodeURIComponent(selectedInstituteId ?? "")}`);
      if (!isCurrent()) return;
      setTickets(refreshedTickets);

      const nextCheckoutTicket = resolveSessionCheckoutTicket(refreshedTickets, finished, sessionId, selectedInstituteId ?? "");
      if (!nextCheckoutTicket) {
        throw new Error("Prestation terminée : son ticket est introuvable en caisse. Actualisez la file.");
      }
      handleOpenCheckout(nextCheckoutTicket.id);

      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de terminer la prestation et ouvrir la caisse");
    }
  }

  async function handleFinishActiveEmployeeSession(employeeId: string) {
    const isCurrent = captureOperationalContext();
    if (!selectedInstituteId) return;

    setError(null);
    try {
      await apiPatch(`/planning/institutes/${selectedInstituteId}/employees/${employeeId}/finish-active-session`);
      if (!isCurrent()) return;
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de clôturer la prestation active");
    }
  }

  async function handleExtendSession(sessionId: string, minutes: number) {
    const isCurrent = captureOperationalContext();
    if (extendingSessions.current.has(sessionId)) return;
    extendingSessions.current.add(sessionId);
    setError(null);
    try {
      await apiPatch(`/planning/sessions/${sessionId}/extend`, {
        minutes, idempotency_key: extensionIntents.current.keyFor(sessionId, minutes),
      });
      if (!isCurrent()) return;
      extensionIntents.current.complete(sessionId);
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de prolonger la prestation");
    } finally {
      extendingSessions.current.delete(sessionId);
    }
  }

  async function handleCancelTicket(ticketId: string) {
    const isCurrent = captureOperationalContext();
    setError(null);
    try {
      await apiPatch(`/tickets/${ticketId}/cancel`);
      if (!isCurrent()) return;
      if (selectedTicketId === ticketId) {
        setSelectedTicketId("");
      }
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible d’annuler le ticket");
    }
  }

  async function handleChangeEmployeeStatus(employeeId: string, status: string) {
    const isCurrent = captureOperationalContext();
    setError(null);
    try {
      await apiPatch(`/employees/${employeeId}/status`, { status });
      if (!isCurrent()) return;
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
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
    const isCurrent = captureOperationalContext();
    if (!selectedCheckoutTicketId || !serviceId) return;

    setError(null);
    try {
      await apiPatch<QueueTicket>(`/tickets/${selectedCheckoutTicketId}/checkout/lines/add`, {
        service_id: serviceId,
      });
      if (!isCurrent()) return;
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible d’ajouter la prestation");
    }
  }

  async function handleRemoveCheckoutLine(lineId: string) {
    const isCurrent = captureOperationalContext();
    if (!selectedCheckoutTicketId || !lineId) return;

    setError(null);
    try {
      await apiPatch<QueueTicket>(`/tickets/${selectedCheckoutTicketId}/checkout/lines/${lineId}/remove`);
      if (!isCurrent()) return;
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de retirer la prestation");
    }
  }

  async function handlePayCheckout(payment?: { payment_method: PaymentMethod; remainder_method?: "cb" | "especes" | "cheque" }) {
    const isCurrent = captureOperationalContext();
    if (!selectedCheckoutTicketId || !identifiedEmployeeId) {
      setError("Identifie la collaboratrice qui encaisse avant de valider le paiement.");
      return;
    }

    setError(null);
    try {
      await apiPatch<QueueTicket>(`/tickets/${selectedCheckoutTicketId}/checkout/pay`, {
        employee_id: identifiedEmployeeId,
        payment_method: payment?.payment_method || selectedPaymentMethod,
        ...(payment?.remainder_method ? { remainder_method: payment.remainder_method } : {}),
      });
      if (!isCurrent()) return;

      const refreshedTickets = await apiGet<QueueTicket[]>(`/tickets/waiting?institute_id=${encodeURIComponent(selectedInstituteId ?? "")}`);
      if (!isCurrent()) return;
      setTickets(refreshedTickets);

      const nextCheckoutTicket = resolveNextCheckoutTicket(refreshedTickets, identifiedEmployeeId);
      if (nextCheckoutTicket) {
        setSelectedCheckoutTicketId(nextCheckoutTicket.id);
        setSelectedTicketId(nextCheckoutTicket.id);
        setActiveDrawer("checkout");
        await refreshOperationalData();
        return;
      }

      setSelectedCheckoutTicketId("");
      setSelectedTicketId("");
      setActiveDrawer(null);
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de valider le paiement");
    }
  }

  async function handleCreateAppointment(payload: AppointmentCreatePayload) {
    const isCurrent = captureOperationalContext();
    setError(null);
    try {
      await apiPost<Appointment>("/appointments", payload);
      if (!isCurrent()) return;
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de créer le rendez-vous");
      throw err;
    }
  }

  async function handleUpdateAppointment(appointmentId: string, payload: AppointmentUpdatePayload) {
    const isCurrent = captureOperationalContext();
    setError(null);
    try {
      await apiPatch<Appointment>(`/appointments/${appointmentId}`, payload);
      if (!isCurrent()) return;
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de modifier le rendez-vous");
      throw err;
    }
  }

  async function handleAppointmentAction(appointmentId: string, action: AppointmentAction) {
    const isCurrent = captureOperationalContext();
    setError(null);
    try {
      const updated = await apiPatch<Appointment>(`/appointments/${appointmentId}/${action}`);
      if (!isCurrent()) return;
      await refreshOperationalData();
      if (!isCurrent()) return;
      if (action === "complete" && updated.checkout_ticket_id) handleOpenCheckout(updated.checkout_ticket_id);
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de modifier le rendez-vous");
      throw err;
    }
  }

  async function handleResetDemo() {
    const isCurrent = captureOperationalContext();
    if (!selectedInstituteId) return;
    setError(null);
    try {
      await apiPost(`/dev/reset-demo?institute_id=${encodeURIComponent(selectedInstituteId)}`);
      if (!isCurrent()) return;
      setSelectedTicketId("");
      setSelectedEmployeeId("");
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de réinitialiser la démo");
      throw err;
    }
  }

  async function handleCreateDemoDay() {
    const isCurrent = captureOperationalContext();
    if (!selectedInstituteId) return;
    setError(null);
    try {
      await apiPost(`/dev/create-demo-day?institute_id=${encodeURIComponent(selectedInstituteId)}`);
      if (!isCurrent()) return;
      setSelectedTicketId("");
      setSelectedEmployeeId("");
      await refreshOperationalData();
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de créer la journée de test");
      throw err;
    }
  }

  async function handleRefreshChiffres() {
    const sameContext = captureOperationalContext();
    const reportRequest = ++chiffresReadSequence.current;
    const isCurrent = () => sameContext() && reportRequest === chiffresReadSequence.current;
    if (!selectedInstituteId) return;

    setChiffres(undefined);
    setChiffresLoading(true);
    setError(null);
    try {
      const response = await apiGet<ChiffresSummary>(
        `/tickets/chiffres?institute_id=${encodeURIComponent(selectedInstituteId)}`
      );
      if (!isCurrent()) return;
      setChiffres(response);
    } catch (err) {
      if (!isCurrent()) return;
      setError(err instanceof Error ? err.message : "Impossible de charger les chiffres");
    } finally {
      if (isCurrent()) setChiffresLoading(false);
    }
  }

  return (
    <div className="bm-app-shell">
      <FlowPilotSidebar
        activeItem={mainView === "chiffres" ? "dashboard" : mainView}
        onOpenPlanning={() => { setActiveDrawer(null); setMainView("planning"); }}
        onOpenTickets={() => { setActiveDrawer(null); setMainView("tickets"); }}
        onOpenDashboard={() => { setActiveDrawer(null); setMainView("chiffres"); }}
        onOpenInventory={["accueil", "responsable_institut"].includes(getOperatorRole() || "") ? () => { setActiveDrawer(null); setMainView("inventory"); } : undefined}
        onOpenOffers={() => { setActiveDrawer(null); setMainView("offres"); }}
        onLogout={onLogout}
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

        {mainView === "inventory" && <InventoryPanel instituteId={selectedInstituteId} timezone={selectedInstitute?.timezone} services={services} />}
        {mainView === "offres" && selectedInstituteId && <CommercePanel key={selectedInstituteId} instituteId={selectedInstituteId} services={services} />}

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
                <button type="button" className="bm-main-action" disabled={loading || !selectedInstituteId || !planning} onClick={() => setTicketWorkflowOpen(true)}>
                  Créer nouveau ticket
                </button>
                <button type="button" className="bm-secondary-action" disabled={loading || !selectedInstituteId || !planning} onClick={() => setActiveDrawer("appointments")}>
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
                onTicketSelect={(ticketId) => { handleTicketSelection(ticketId); setActiveDrawer("tickets"); }}
                onOpenTickets={() => setActiveDrawer("tickets")}
                onFinishActiveEmployeeSession={handleFinishActiveEmployeeSession}
                onChangeEmployeeStatus={handleChangeEmployeeStatus}
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
              onRefresh={async () => { await refreshOperationalData(); }}
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
              instituteId={selectedInstituteId}
              chiffres={chiffres}
              loading={chiffresLoading}
              onRefresh={handleRefreshChiffres}
            />
            <PaymentCashflows instituteId={selectedInstituteId} />
          </main>
        )}

        <ActionDrawer
          open={activeDrawer === "newTicket"}
          title="Créer un nouveau ticket"
          subtitle={identifiedEmployee ? `Créateur identifié : ${identifiedEmployee.first_name}` : "Choisissez une prestation pour créer un passage anonyme."}
          onClose={() => setActiveDrawer(null)}
        >
          <QueuePanel
            assignment={assignment}
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
            onUnassignTicket={handleUnassignTicket}
            onStartSession={handleStartSession}
            onCancelTicket={handleCancelTicket}
            onFinishActiveEmployeeSession={handleFinishActiveEmployeeSession}
            onChangeEmployeeStatus={handleChangeEmployeeStatus}
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
            assignment={assignment}
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
            onUnassignTicket={handleUnassignTicket}
            onStartSession={handleStartSession}
            onCancelTicket={handleCancelTicket}
            onFinishActiveEmployeeSession={handleFinishActiveEmployeeSession}
            onChangeEmployeeStatus={handleChangeEmployeeStatus}
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
          onRefresh={refreshOperationalData}
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
            onUpdateAppointment={handleUpdateAppointment}
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
            onRefresh={async () => { await refreshOperationalData(); }}
          />
        </ActionDrawer>

        <NewTicketWorkflow
          key={selectedInstituteId}
          instituteId={selectedInstituteId}
          open={ticketWorkflowOpen}
          creatorEmployee={identifiedEmployee}
          ticketStats={ticketStats}
          categories={categories}
          services={services}
          onRequestIdentity={() => openIdentity("create_ticket")}
          onClose={() => { workflowIntent.current.complete(); setTicketWorkflowOpen(false); }}
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

function getTopBreadcrumb(view: "planning" | "tickets" | "chiffres" | "offres" | "inventory") {
  if (view === "inventory") return "Accueil / Inventaire";
  if (view === "offres") return "Accueil / Offres";
  if (view === "tickets") return "Accueil / Tickets";
  if (view === "chiffres") return "Accueil / Chiffres";
  return "Accueil / Planning";
}

function getTopTitle(view: "planning" | "tickets" | "chiffres" | "offres" | "inventory") {
  if (view === "inventory") return "Inventaire";
  if (view === "offres") return "Offres";
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
