export type ApiStatus = "idle" | "loading" | "success" | "error";

export interface Institute {
  id: string;
  name: string;
  city: string;
  address?: string | null;
  timezone: string;
  status: string;
}

export interface Employee {
  id: string;
  institute_id: string;
  first_name: string;
  code?: string | null;
  skills: string[];
  status: string;
}

export interface ServiceCategory {
  id: string;
  name: string;
  code: string;
  parent_id?: string | null;
}

export interface Service {
  id: string;
  category_id: string;
  name: string;
  duration_min: number;
  duration_max?: number | null;
  price_member?: number | null;
  price_passage?: number | null;
  requires_machine: boolean;
  requires_appointment: boolean;
  status: string;
}

export interface QueueTicket {
  id: string;
  institute_id: string;
  ticket_number: string;
  customer_id?: string | null;
  subscription_id?: string | null;
  status: string;
  arrival_time: string;
  estimated_start_time?: string | null;
  assigned_employee_id?: string | null;
  created_by_id?: string | null;
}

export interface ServiceSession {
  id: string;
  ticket_line_id?: string | null;
  institute_id: string;
  employee_id: string;
  service_id: string;
  start_time: string;
  planned_end_time: string;
  real_end_time?: string | null;
  duration_minutes: number;
  status: string;
}

export interface PlanningEmployeeRow {
  employee_id: string;
  employee_name: string;
  employee_status: string;
  sessions: ServiceSession[];
}

export interface PlanningDay {
  institute_id: string;
  generated_at: string;
  rows: PlanningEmployeeRow[];
}

export interface AvailabilityEmployee {
  employee_id: string;
  employee_name: string;
  employee_status: string;
  available_at?: string | null;
  wait_minutes?: number | null;
  active_session_id?: string | null;
  active_appointment_id?: string | null;
}

export interface PlanningAvailability {
  institute_id: string;
  generated_at: string;
  next_employee_id?: string | null;
  next_employee_name?: string | null;
  next_available_at?: string | null;
  wait_minutes?: number | null;
  active_sessions: number;
  waiting_tickets: number;
  employees: AvailabilityEmployee[];
}


export interface InstituteDashboardRead {
  institute_id: string;
  generated_at: string;
  employees_total: number;
  employees_available: number;
  employees_busy: number;
  employees_delayed: number;
  employees_pause: number;
  employees_absent_or_offline: number;
  tickets_waiting: number;
  tickets_assigned: number;
  tickets_in_progress: number;
  tickets_completed_today: number;
  tickets_cancelled_today: number;
  sessions_active: number;
  sessions_delayed: number;
  sessions_completed_today: number;
  average_wait_minutes?: number | null;
  next_available_employee_name?: string | null;
  next_available_minutes?: number | null;
  operational_status: "calm" | "normal" | "busy" | "alert" | string;
  alert_message?: string | null;
}


export interface Appointment {
  id: string;
  institute_id: string;
  service_id: string;
  employee_id: string;
  customer_name: string;
  phone?: string | null;
  start_time: string;
  end_time: string;
  status: string;
  notes?: string | null;
}

export interface AppointmentCreatePayload {
  institute_id: string;
  service_id: string;
  employee_id: string;
  customer_name: string;
  phone?: string | null;
  start_time: string;
  notes?: string | null;
}
