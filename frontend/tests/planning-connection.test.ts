import test from "node:test";
import assert from "node:assert/strict";
import { connectPlanning } from "../src/features/planningConnection";
import { createRefreshGate } from "../src/features/refreshGate";

test("operational refresh rejects prior tenant, older responses and disposed requests", () => {
  const gate = createRefreshGate();
  gate.setContext("one");
  const first = gate.begin("one");
  const second = gate.begin("one");
  assert.equal(gate.current(first), false);
  assert.equal(gate.current(second), true);
  gate.setContext("two");
  assert.equal(gate.current(second), false);
  assert.equal(gate.begin("one"), null);
  const latest = gate.begin("two");
  assert.equal(gate.current(latest), true);
  gate.invalidate();
  assert.equal(gate.current(latest), false);
});

class FakeSocket {
  readyState = 0;
  onopen: any;
  onclose: any;
  onerror: any;
  onmessage: any;
  sent: string[] = [];
  open() { this.readyState = 1; this.onopen?.({}); }
  close(code = 1006) { this.readyState = 3; this.onclose?.({ code }); }
  send(value: string) { this.sent.push(value); }
  message(value: any) { this.onmessage?.({ data: JSON.stringify(value) }); }
}

function harness() {
  const timers = new Map<number, { callback: () => void; delay: number }>();
  const sockets: FakeSocket[] = [];
  const statuses: string[] = [];
  let identifier = 0;
  let refreshes = 0;
  const stop = connectPlanning({ url: "ws://test/institutes/one/planning", onStatus: value => statuses.push(value),
    onRefresh: () => refreshes++, createSocket: () => {
      const socket = new FakeSocket(); sockets.push(socket); return socket as unknown as WebSocket;
    }, schedule: (callback, delay) => { const id = ++identifier; timers.set(id, { callback, delay }); return id; },
    cancel: id => { timers.delete(id); } });
  const run = (delay: number) => {
    const entry = [...timers].find(([, timer]) => timer.delay === delay);
    assert.ok(entry, `Expected timer ${delay}`);
    timers.delete(entry[0]); entry[1].callback();
  };
  return { timers, sockets, statuses, stop, run, refreshes: () => refreshes };
}

test("reconnect backs off, resynchronizes on open and ignores obsolete socket events", () => {
  const h = harness();
  h.sockets[0].close(); h.run(1000);
  h.sockets[1].close(); h.run(2000);
  h.sockets[2].open();
  assert.equal(h.refreshes(), 1);
  h.sockets[0].message({ event: "planning.changed" });
  assert.equal(h.refreshes(), 1);
  h.sockets[2].message({ event: "planning.changed" });
  assert.equal(h.refreshes(), 2);
  h.sockets[2].close(); h.run(1000);
  h.sockets[3].open();
  assert.equal(h.refreshes(), 3);
  h.stop();
  assert.equal(h.timers.size, 0);
});

test("heartbeat pong is not a refresh and silence triggers reconnection", () => {
  const h = harness(); h.sockets[0].open(); h.run(20000);
  assert.deepEqual(h.sockets[0].sent, ["ping"]);
  h.sockets[0].message({ event: "pong" });
  assert.equal(h.refreshes(), 1);
  assert.ok(![...h.timers.values()].some(timer => timer.delay === 10000));
  h.run(20000); h.run(10000); h.run(1000);
  assert.equal(h.sockets.length, 2);
  h.stop();
});

test("policy closure stops retries and cleanup prevents later reconnect or refresh", () => {
  const h = harness(); h.sockets[0].close(1008);
  assert.equal(h.timers.size, 0);
  h.stop(); h.sockets[0].open(); h.sockets[0].message({ event: "planning.changed" });
  assert.equal(h.refreshes(), 0);
  assert.equal(h.timers.size, 0);
});
