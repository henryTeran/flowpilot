import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CompactQueuePanel } from "../src/components/CompactQueuePanel";
import type { QueueTicket } from "../src/types";

test("a selected ticket outside the compact six stays actionable without expanding the queue", () => {
  const tickets = Array.from({ length: 8 }, (_, index) => ({ id: `t-${index}`, institute_id: "inst", ticket_number: `ONLY-${index}`, status: "waiting", arrival_time: `2026-10-06T10:0${index}:00Z`, lines: [] })) as QueueTicket[];
  const html = renderToStaticMarkup(<CompactQueuePanel tickets={tickets} services={[]} employees={[]} selectedTicketId="t-7" ticketServiceMap={{}} onTicketSelect={() => {}} onOpenTickets={() => {}} onFinishActiveEmployeeSession={() => {}} onChangeEmployeeStatus={() => {}} onStartCheckout={() => {}} />);
  assert.match(html, /ONLY-7/);
  assert.equal((html.match(/class="compact-ticket(?: selected| )?"/g) || []).length, 6);
  assert.match(html, /class="compact-ticket selected"/);
});
