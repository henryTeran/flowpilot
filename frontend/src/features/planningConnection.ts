export type RealtimeStatus = "connected" | "connecting" | "disconnected";

interface ConnectionOptions {
  url: string;
  onStatus: (status: RealtimeStatus) => void;
  onRefresh: () => void;
  createSocket?: (url: string) => WebSocket;
  schedule?: (callback: () => void, delay: number) => number;
  cancel?: (timer: number) => void;
}

/** Network lifecycle only. Every successful connection resynchronizes REST facts. */
export function connectPlanning(options: ConnectionOptions): () => void {
  const createSocket = options.createSocket ?? (url => new WebSocket(url));
  const schedule = options.schedule ?? ((callback, delay) => window.setTimeout(callback, delay));
  const cancel = options.cancel ?? (timer => window.clearTimeout(timer));
  let disposed = false;
  let current: WebSocket | null = null;
  let retry: number | null = null;
  let heartbeat: number | null = null;
  let watchdog: number | null = null;
  let failures = 0;

  function clearHeartbeat() {
    if (heartbeat !== null) cancel(heartbeat);
    heartbeat = null;
    if (watchdog !== null) cancel(watchdog);
    watchdog = null;
  }

  function reconnect() {
    if (disposed || retry !== null) return;
    options.onStatus("disconnected");
    const delay = Math.min(30000, 1000 * 2 ** Math.min(failures++, 5));
    retry = schedule(() => { retry = null; open(); }, delay);
  }

  function open() {
    if (disposed) return;
    options.onStatus("connecting");
    let socket: WebSocket;
    try { socket = createSocket(options.url); }
    catch { reconnect(); return; }
    current = socket;
    const active = () => !disposed && current === socket;
    socket.onopen = () => {
      if (!active()) return;
      if (retry !== null) cancel(retry);
      retry = null;
      failures = 0;
      options.onStatus("connected");
      options.onRefresh();
      function ping() {
        if (!active()) return;
        watchdog = schedule(() => {
          if (!active()) return;
          socket.close();
          reconnect();
        }, 10000);
        try { if (socket.readyState === 1) socket.send("ping"); }
        catch { socket.close(); reconnect(); return; }
        heartbeat = schedule(ping, 20000);
      }
      clearHeartbeat();
      heartbeat = schedule(ping, 20000);
    };
    socket.onmessage = event => {
      if (!active()) return;
      try {
        const message = JSON.parse(String(event.data));
        if (message.event === "pong" && watchdog !== null) {
          cancel(watchdog);
          watchdog = null;
        }
        if (message.event === "planning.changed") options.onRefresh();
      } catch { /* Malformed messages never change operational facts. */ }
    };
    socket.onclose = event => {
      if (!active()) return;
      clearHeartbeat();
      current = null;
      options.onStatus("disconnected");
      if (event.code === 1008) {
        if (retry !== null) cancel(retry);
        retry = null;
        return;
      }
      reconnect();
    };
    socket.onerror = () => {
      if (!active()) return;
      clearHeartbeat();
      socket.close();
      reconnect();
    };
  }

  open();
  return () => {
    disposed = true;
    if (retry !== null) cancel(retry);
    clearHeartbeat();
    current?.close();
    current = null;
  };
}
