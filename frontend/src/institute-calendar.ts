import { instituteTimeZone } from "./institute-time";

const hour = 3600000;
const formatters = new Map<string, Intl.DateTimeFormat>();
function formatterFor(zone?: string) {
  const key = zone || "UTC";
  let formatter = formatters.get(key);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("en-GB", { timeZone: instituteTimeZone(zone),
      calendar: "iso8601", numberingSystem: "latn", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
    // Reuse explicit-zone formatters for timeline rows without unbounded storage.
    if (formatters.size >= 8) formatters.delete(formatters.keys().next().value!);
    formatters.set(key, formatter);
  }
  return formatter;
}
export function instituteSlot(value: string | Date, zone?: string) {
  if (typeof value === "string" && !/(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return;
  const instant = new Date(value);
  if (!Number.isFinite(instant.getTime())) return;
  const formatter = formatterFor(zone);
  const p = Object.fromEntries(formatter.formatToParts(instant).map(p => [p.type, p.value]));
  const date = `${p.year.padStart(4, "0")}-${p.month}-${p.day}`, time = `${p.hour}:${p.minute}`;
  const wall = Date.parse(`${date}T${time}:${p.second}Z`);
  return { instant: instant.toISOString(), date, time, hour: Number(p.hour), minute: Number(p.minute), wall,
    offset: wall - Math.floor(instant.getTime() / 1000) * 1000 };
}

function wallProjections(date: string, time: string, zone?: string) {
  if (!/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(date) || !/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) return [];
  const target = Date.parse(`${date}T${time}:00Z`);
  if (!Number.isFinite(target) || new Date(target).toISOString().slice(0, 16) !== `${date}T${time}`) return [];
  const offsets = new Set<number>();
  for (let delta = -36; delta <= 36; delta += 6) {
    const sample = instituteSlot(new Date(target + delta * hour), zone);
    if (sample) offsets.add(sample.offset);
  }
  return [...offsets].map(offset => target - offset).filter(Number.isFinite).sort((a, b) => a - b);
}

// Zero matches is invalid/skipped; two matches require an explicit occurrence.
export function instituteInstants(date: string, time: string, zone?: string): string[] {
  return wallProjections(date, time, zone).filter(value => {
    const slot = instituteSlot(new Date(value), zone);
    return slot?.date === date && slot.time === time;
  }).map(value => new Date(value).toISOString());
}

export function nextInstituteSlot(zone?: string, now = Date.now()) {
  return instituteSlot(new Date(Math.ceil((now + 10 * 60000) / (15 * 60000)) * 15 * 60000), zone)!;
}

// Display boundaries include both folds; a skipped hour advances to its first
// existing instant. This never resolves an appointment mutation implicitly.
export function instituteBoundary(date: string, clockHour: number, zone?: string) {
  if (clockHour === 24) {
    const next = new Date(Date.parse(`${date}T00:00:00Z`) + 24 * hour);
    if (!Number.isFinite(next.getTime())) return;
    date = next.toISOString().slice(0, 10); clockHour = 0;
  }
  const time = `${String(clockHour).padStart(2, "0")}:00`;
  const exact = instituteInstants(date, time, zone);
  if (exact.length) return Date.parse(exact[0]);
  const target = Date.parse(`${date}T${time}:00Z`);
  return wallProjections(date, time, zone).filter(value => {
    const slot = instituteSlot(new Date(value), zone);
    return slot?.date === date && slot.wall >= target;
  }).sort((a, b) => a - b)[0];
}
