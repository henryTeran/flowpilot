import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { AssignmentOption, QueueTicket } from "../types";

export interface AssignmentState {
  status: "idle" | "loading" | "ready" | "error";
  options: AssignmentOption[];
  retry: () => void;
}

export function useAssignmentOptions(instituteId: string, ticket?: QueueTicket): AssignmentState {
  const ticketId = ticket && ["waiting", "assigned"].includes(ticket.status) ? ticket.id : "";
  const context = `${instituteId}:${ticketId}`;
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{ context: string; status: AssignmentState["status"]; options: AssignmentOption[] }>({
    context: "", status: "idle", options: [],
  });
  useEffect(() => {
    let cancelled = false;
    if (!instituteId || !ticketId) {
      setState({ context, status: "idle", options: [] });
      return;
    }
    setState({ context, status: "loading", options: [] });
    apiGet<{ options: AssignmentOption[] }>(
      `/availability/${encodeURIComponent(ticketId)}/assignment-options?institute_id=${encodeURIComponent(instituteId)}`,
    ).then((response) => {
      if (!cancelled) setState({ context, status: "ready", options: response.options });
    }).catch(() => {
      if (!cancelled) setState({ context, status: "error", options: [] });
    });
    return () => { cancelled = true; };
  }, [instituteId, ticketId, ticket, context, revision]);
  const current = state.context === context ? state : { status: ticketId ? "loading" as const : "idle" as const, options: [] };
  return { status: current.status, options: current.options, retry: () => setRevision((value) => value + 1) };
}

export function assignmentReason(reason: string) {
  if (reason.startsWith("service doesn't fit")) return "La séance ne tient pas avant le prochain rendez-vous.";
  const reasons: Record<string, string> = {
    employee_reserved: "Cette collaboratrice a déjà un ticket affecté.",
    ticket_already_assigned: "Ce ticket est affecté à une autre collaboratrice.",
    employee_unavailable: "Cette collaboratrice est indisponible.",
    employee_pause: "Cette collaboratrice est en pause.",
    employee_absent: "Cette collaboratrice est absente.",
    employee_offline: "Cette collaboratrice est hors ligne.",
    session_overdue: "Termine ou prolonge la prestation en retard.",
    in_progress_session: "Cette collaboratrice est encore en prestation.",
    upcoming_appointment: "Un rendez-vous occupe ce créneau.",
    capacity_unknown: "La prochaine disponibilité est indéterminée.",
  };
  return reasons[reason] || "Cette collaboratrice ne peut pas prendre cette séance maintenant.";
}
