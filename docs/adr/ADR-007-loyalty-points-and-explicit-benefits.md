# ADR-007 — Loyalty points and explicitly configured benefits

Status: Accepted for the point-history/tier foundation; earning and reward application pending.
Date: 2026-10-06

## Context

Master Plan section 29 requires loyalty points, levels, benefits and history.
Registered customer identity and membership rights already exist; neither a
subscription marker nor membership status establishes a loyalty balance. No
earning conversion, threshold or monetary reward was specified by the source plan.

## Decision

- Keep loyalty in its own modular-monolith domain. Points are non-monetary units;
  they do not imply a currency conversion, external settlement or service discount.
- Store append-only institute/customer point entries with a signed actor, reason,
  occurrence time and mandatory replay key. Manager corrections may credit or
  debit points; they are labeled corrections, not automatically earned purchases.
- Compute balance from the scoped ledger under the institute transaction lock.
  Corrections cannot overdraw; same-intent recovery returns the original entry
  after later changes without crediting again. Changed customer/amount/reason fails.
- Configure immutable balance-based tiers explicitly, with distinct nonnegative
  thresholds, names and benefit descriptions. The highest reached threshold wins;
  no default VIP/loyal label or inherited membership eligibility is introduced.
- Benefit descriptions are informational in this foundation. They do not modify
  checkout prices. Actual earning needs an explicitly configured earning policy
  and snapshotted checkout facts; actual rewards need defined eligibility/cost,
  transactional application/reversal and immutable history before their gate passes.
- Require registered scoped customers. Reception may read; only the responsible
  manager may configure tiers/correct points. Preserve anonymous fast intake.
- Refuse nonempty ledger or tier downgrades before DDL.

## Verification and remaining work

HTTP checks cover role/institute boundaries, strict integer inputs, replay, changed
intent, tier transitions, failed-flush rollback and history. PostgreSQL races cover
duplicate credit and competing corrections; SQLite/PostgreSQL migration parity and
round-trips are checked on disposable databases. This is a loyalty foundation,
not the complete LOYALTY gate. Earning, reward application, UI and end-to-end
verification remain required; production readiness is not inferred.
