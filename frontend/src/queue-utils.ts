import type { Employee, QueueTicket } from "./types";

export function compareQueueArrival(left: Pick<QueueTicket, "id" | "arrival_time">, right: Pick<QueueTicket, "id" | "arrival_time">) {
  const difference = new Date(left.arrival_time).getTime() - new Date(right.arrival_time).getTime();
  return difference || (left.id < right.id ? -1 : left.id > right.id ? 1 : 0);
}

export function createArrivalIntent() {
  let fingerprint = "";
  let key = "";
  return {
    keyFor(payload: { institute_id: string; service_ids: string[]; created_by_id?: string }) {
      const next = JSON.stringify({ ...payload, service_ids: [...payload.service_ids].sort() });
      if (next !== fingerprint || !key) {
        fingerprint = next;
        key = crypto.randomUUID();
      }
      return key;
    },
    complete() { fingerprint = ""; key = ""; },
  };
}

export function shouldOfferDelayedReleaseAction(
  ticket: Pick<QueueTicket, "status" | "assigned_employee_id"> | undefined,
  employee: Pick<Employee, "status"> | null | undefined,
) {
  if (!ticket || !employee || !ticket.assigned_employee_id) return false;

  const actionableStatuses = new Set(["assigned", "in_progress", "ready_for_checkout", "in_checkout"]);
  return employee.status === "delayed" && actionableStatuses.has(ticket.status);
}
