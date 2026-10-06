export function instituteTimeZone(zone?: string) {
  try {
    new Intl.DateTimeFormat("fr-CH", { timeZone: zone || "UTC" });
    return zone || "UTC";
  } catch { return "UTC"; }
}

export function formatInstituteTime(value?: string | null, zone?: string) {
  if (!value || !/(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return "—";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return date.toLocaleTimeString("fr-CH", {
    timeZone: instituteTimeZone(zone), hour: "2-digit", minute: "2-digit",
  });
}
