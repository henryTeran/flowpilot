import { workDuration } from "./work-hours-utils";
export type OccupationTotals = { known_busy_duration_us: string; covered_busy_duration_us: string;
  outside_recorded_work_duration_us: string; recorded_occupation_basis_points: string | null; complete_activity: false };
export const occupationDiagnosticKeys = ["retained", "missing_start", "missing_end", "invalid_interval", "future_end", "unfinalized"] as const;
export function validOccupationTotals(value: unknown, work: string | null, knownWork: string, diagnostics: unknown, sourceCount: number): value is OccupationTotals {
  const row = value as OccupationTotals, counts = diagnostics as Record<string, number>;
  if (!row || row.complete_activity !== false || !counts || !Number.isSafeInteger(sourceCount) || sourceCount < 0
    || Object.keys(counts).length !== occupationDiagnosticKeys.length
    || !occupationDiagnosticKeys.every(k => Number.isSafeInteger(counts[k]) && counts[k] >= 0)
    || occupationDiagnosticKeys.reduce((sum, k) => sum+counts[k], 0) !== sourceCount) return false;
  const busy = workDuration(row.known_busy_duration_us), covered = workDuration(row.covered_busy_duration_us);
  const outside = workDuration(row.outside_recorded_work_duration_us), known = workDuration(knownWork), denominator = workDuration(work);
  if (busy === undefined || covered === undefined || outside === undefined || known === undefined
    || covered > known || covered > busy || covered+outside !== busy || (counts.retained ? busy === 0n : busy !== 0n)) return false;
  const uncertain = occupationDiagnosticKeys.some(k => k !== "retained" && counts[k] > 0);
  if (work === null || uncertain) return row.recorded_occupation_basis_points === null;
  if (denominator === undefined || denominator === 0n || denominator !== known) return false;
  return workDuration(row.recorded_occupation_basis_points) === covered*10000n/denominator;
}
export function formatOccupationBasisPoints(value: string) {
  const points = workDuration(value);
  if (points === undefined || points > 10000n) throw new Error("Ratio enregistré à vérifier.");
  return `${points/100n},${String(points%100n).padStart(2, "0")} %`;
}
