/** Accept only the newest refresh for the currently selected context. */
export function createRefreshGate() {
  let context = "";
  let sequence = 0;
  return {
    setContext(value: string) {
      if (value !== context) { context = value; sequence++; }
    },
    begin(value: string) {
      if (value !== context) return null;
      return { context: value, sequence: ++sequence };
    },
    current(request: { context: string; sequence: number } | null) {
      return request !== null && request.context === context && request.sequence === sequence;
    },
    invalidate() { sequence++; },
  };
}
