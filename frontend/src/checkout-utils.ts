import type { QueueTicket, ServiceSession } from "./types";

export function resolveNextCheckoutTicket(
  tickets: Pick<QueueTicket, "id" | "assigned_employee_id" | "status">[],
  identifiedEmployeeId?: string,
) {
  const checkoutStatuses = new Set(["ready_for_checkout", "in_checkout"]);
  const checkoutTickets = tickets.filter((ticket) => checkoutStatuses.has(ticket.status));

  if (!checkoutTickets.length) return undefined;

  if (identifiedEmployeeId) {
    const employeeCheckoutTicket = checkoutTickets.find(
      (ticket) => ticket.assigned_employee_id === identifiedEmployeeId,
    );

    if (employeeCheckoutTicket) {
      return employeeCheckoutTicket;
    }
  }

  return checkoutTickets[0];
}

export function resolveSessionCheckoutTicket(
  tickets: QueueTicket[], finished: ServiceSession, sessionId: string, instituteId: string,
) {
  if (finished.id !== sessionId || finished.institute_id !== instituteId || finished.status !== "completed" || !finished.ticket_line_id) return undefined;
  return tickets.find(ticket => ticket.institute_id === instituteId
    && ["ready_for_checkout", "in_checkout"].includes(ticket.status)
    && [...(ticket.lines || []), ...(ticket.removed_lines || [])].some(line => line.id === finished.ticket_line_id));
}
