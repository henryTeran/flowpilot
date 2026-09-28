# ADR-005 — Walk-in First Hybrid Flow

Status: Accepted
Date: 2026-09-28

## Context

Original field requirements show that institutes mainly operate with walk-in clients while some services still require appointments.

The operational core is therefore not appointment-first, but hybrid: queue visibility, waiting-time estimation, live capacity and resource coordination must work even when clients arrive without prior booking.

## Decision

FlowPilot adopts a hybrid operational architecture with walk-in queue and appointments as first-class flows sharing a common Flow & Capacity Engine.

Walk-in tickets may remain anonymous.

Waiting time and availability are calculated deterministically by FlowPilot.

Appointments may reserve collaborators and required resources.

Realtime changes such as start, finish, pause and extension must update capacity and waiting-time projections.

## Consequences

Queue, Booking and Resources become inputs of the shared operational engine.

Client 360 is not required for basic walk-in operations.

The LLM does not calculate official availability or waiting time.

FlowPilot keeps a shadow/integration capability for progressive adoption alongside existing systems.
