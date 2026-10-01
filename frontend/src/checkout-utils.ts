import type { QueueTicket } from "./types";

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
