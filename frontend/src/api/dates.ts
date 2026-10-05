// Database timestamps are UTC; SQLite may serialize them without an offset.
export function readUtcDate(value: string) {
  return new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`);
}
