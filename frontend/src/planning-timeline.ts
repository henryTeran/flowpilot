import { instituteBoundary, instituteSlot } from "./institute-calendar";
export type TimelineRange = { startHour: number; endHour: number };
export function instituteTimeline(range: TimelineRange, day: Date, zone: string) {
  const civil = instituteSlot(day, zone);
  if (!civil) return;
  const start = instituteBoundary(civil.date, range.startHour, zone), end = instituteBoundary(civil.date, range.endHour, zone);
  if (start === undefined || end === undefined || end <= start) return;
  const values: number[] = [];
  for (let instant = start; instant < end; instant += 3600000) values.push(instant);
  values.push(end);
  const labels = values.map(value => instituteSlot(new Date(value), zone)!.time);
  if (range.endHour === 24) labels[labels.length - 1] = "24:00";
  const marks = values.map((value, index) => {
    const offset = instituteSlot(new Date(value), zone)!.offset / 60000;
    const suffix = labels.filter(label => label === labels[index]).length > 1
      ? ` UTC${offset < 0 ? "-" : "+"}${String(Math.floor(Math.abs(offset) / 60)).padStart(2, "0")}:${String(Math.abs(offset) % 60).padStart(2, "0")}` : "";
    return { left: (value - start) / (end - start) * 100, label: labels[index] + suffix };
  });
  return { start, end, marks };
}
export function timelineBlock(startValue: string, endValue: string, range: TimelineRange, day: Date, minimumWidth: number, zone = "UTC", suppliedWindow?: ReturnType<typeof instituteTimeline>) {
  if (![startValue, endValue].every(value => /(?:Z|[+-]\d{2}:\d{2})$/.test(value))) return null;
  const start = new Date(startValue), end = new Date(endValue);
  if (![start.getTime(), end.getTime(), day.getTime(), range.startHour, range.endHour, minimumWidth].every(Number.isFinite) || end <= start || range.endHour <= range.startHour || minimumWidth <= 0) return null;
  const window = suppliedWindow || instituteTimeline(range, day, zone);
  if (!window) return null;
  const startMinutes = start.getTime(), endMinutes = end.getTime();
  const rangeStart = window.start, rangeEnd = window.end;
  if (endMinutes <= rangeStart || startMinutes >= rangeEnd) return null;
  const total = rangeEnd - rangeStart;
  const left = (Math.max(startMinutes, rangeStart) - rangeStart) / total * 100;
  const width = (Math.min(endMinutes, rangeEnd) - Math.max(startMinutes, rangeStart)) / total * 100;
  return { left, width: Math.min(Math.max(width, minimumWidth), 100 - left) };
}
