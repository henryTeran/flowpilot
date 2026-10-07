export interface SkillMatrix {
  institute_id: string;
  generated_at: string;
  employee_page: { offset: number; limit: number; total: number };
  service_page: { offset: number; limit: number; total: number };
  employees: { id: string; first_name: string; status: string; skills: string[] }[];
  services: { id: string; name: string; required_skills: string[]; requirement_state: "recorded" | "none_recorded" }[];
  cells: { employee_id: string; service_id: string; meets_recorded_requirements: boolean; missing_skills: string[] }[];
}

function codes(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(code => typeof code === "string" && code.trim() === code && code.length > 0)
    && new Set(value).size === value.length;
}
const text = (value: unknown) => typeof value === "string" && value.trim().length > 0;
function page(value: any, offset: number, limit: number) {
  return value && value.offset === offset && value.limit === limit && Number.isSafeInteger(value.total) && value.total >= 0;
}
export function validSkillMatrix(value: any, institute: string, employeeOffset: number, serviceOffset: number,
                                 employeeLimit = 10, serviceLimit = 5): value is SkillMatrix {
  if (!value || value.institute_id !== institute || typeof value.generated_at !== "string"
    || !/(Z|[+-]\d{2}:\d{2})$/.test(value.generated_at) || !Number.isFinite(Date.parse(value.generated_at))
    || !page(value.employee_page, employeeOffset, employeeLimit) || !page(value.service_page, serviceOffset, serviceLimit)
    || !Array.isArray(value.employees) || !Array.isArray(value.services) || !Array.isArray(value.cells)
    || value.employees.length !== Math.min(employeeLimit, Math.max(0, value.employee_page.total - employeeOffset))
    || value.services.length !== Math.min(serviceLimit, Math.max(0, value.service_page.total - serviceOffset))
    || !value.employees.every((row: any) => row && text(row.id) && text(row.first_name) && text(row.status) && codes(row.skills))
    || !value.services.every((row: any) => row && text(row.id) && text(row.name) && codes(row.required_skills)
      && row.requirement_state === (row.required_skills.length ? "recorded" : "none_recorded"))
    || new Set(value.employees.map((row: any) => row.id)).size !== value.employees.length
    || new Set(value.services.map((row: any) => row.id)).size !== value.services.length
    || value.cells.length !== value.employees.length * value.services.length) return false;
  const pairs = new Set<string>();
  for (const cell of value.cells) {
    if (!cell || !codes(cell.missing_skills) || typeof cell.meets_recorded_requirements !== "boolean") return false;
    const employee = value.employees.find((row: any) => row.id === cell.employee_id);
    const service = value.services.find((row: any) => row.id === cell.service_id);
    const pair = JSON.stringify([cell.employee_id, cell.service_id]);
    if (!employee || !service || pairs.has(pair)) return false;
    pairs.add(pair);
    const missing = service.required_skills.filter((code: string) => !employee.skills.includes(code));
    if (JSON.stringify(missing) !== JSON.stringify(cell.missing_skills) || cell.meets_recorded_requirements !== (missing.length === 0)) return false;
  }
  return true;
}
