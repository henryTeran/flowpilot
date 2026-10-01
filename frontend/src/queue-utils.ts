import type { Employee, QueueTicket } from "./types";

export function shouldOfferDelayedReleaseAction(
  ticket: Pick<QueueTicket, "status" | "assigned_employee_id"> | undefined,
  employee: Pick<Employee, "status"> | null | undefined,
) {
  if (!ticket || !employee || !ticket.assigned_employee_id) return false;

  const actionableStatuses = new Set(["assigned", "in_progress", "ready_for_checkout", "in_checkout"]);
  return employee.status === "delayed" && actionableStatuses.has(ticket.status);
}
