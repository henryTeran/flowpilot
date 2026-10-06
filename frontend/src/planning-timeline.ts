export type TimelineRange = { startHour: number; endHour: number };
function minutesOnDay(value: Date, day: Date) {
  const ordinal = (date: Date) => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86400000;
  return (ordinal(value) - ordinal(day)) * 1440 + value.getHours() * 60 + value.getMinutes();
}
export function timelineBlock(startValue: string, endValue: string, range: TimelineRange, day: Date, minimumWidth: number) {
  const start = new Date(startValue), end = new Date(endValue);
  if (![start.getTime(), end.getTime(), day.getTime(), range.startHour, range.endHour, minimumWidth].every(Number.isFinite) || end <= start || range.endHour <= range.startHour || minimumWidth <= 0) return null;
  const startMinutes = minutesOnDay(start, day), endMinutes = minutesOnDay(end, day);
  const rangeStart = range.startHour * 60, rangeEnd = range.endHour * 60;
  if (endMinutes <= rangeStart || startMinutes >= rangeEnd) return null;
  const total = rangeEnd - rangeStart;
  const left = (Math.max(startMinutes, rangeStart) - rangeStart) / total * 100;
  const width = (Math.min(endMinutes, rangeEnd) - Math.max(startMinutes, rangeStart)) / total * 100;
  return { left, width: Math.min(Math.max(width, minimumWidth), 100 - left) };
}
