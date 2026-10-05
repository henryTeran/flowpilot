# ADR-007 — Loyalty points and explicitly configured benefits

Status: Accepted for point history, tiers, earning and transactional rewards; UI verification pending.
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
  checkout prices. Actual rewards need defined eligibility/cost,
  transactional application/reversal and immutable history before their gate passes.
- Require registered scoped customers. Reception may read; only the responsible
  manager may configure tiers/correct points. Preserve anonymous fast intake.
- Configure earning with immutable, ordered institute policy revisions: explicit
  CHF/EUR currency, positive decimal points per currency unit, enabled flag,
  signed manager and reason. No default rate; replaying an old policy does not
  reactivate it. Currency configuration cannot change once a policy exists.
- Within the locked checkout transaction, award registered scoped customers once
  from the sum of actual line totals after package/member pricing. Gift funding
  does not reduce that basis. Round down to whole points and retain policy, rate,
  currency, basis, actor and paid time, including zero-point outcomes. Failed
  history writes roll back ticket closure and tender facts together.
- Preserve anonymous/opaque intake and historical paid replays without retroactive
  earnings. Enabled earning requires signed institute context and confirmed ticket
  currency. Rate changes serialize with closure; earning is cashier confirmation,
  not proof of provider settlement.
- Configure immutable rewards with explicit service, currency, positive fixed
  reduction, positive point cost and independent minimum balance threshold.
  Manager creation is scoped and replay-safe; no reward is inferred from tier
  descriptions. Reward creation serializes with currency configuration and freezes
  its unit. The apply endpoint
  spends cost per unit for the full performed line quantity; the
  minimum balance is checked before spending. The fixed reduction is per unit,
  capped at zero price, and both original and resulting prices are snapshotted.
- Serialize spending with manager point corrections, other coverage, gift tender
  allocation and checkout. Require registered scoped beneficiary, service and
  confirmed matching currency. Active package/member/reward coverage cannot
  stack; active gift funding freezes new reward application and reversal.
- Before payment, manager reversal credits the exact original spend and restores
  the saved prices in one transaction. Preserve debit and credit entries plus
  reversal actor/reason/time. Same-intent apply/reversal returns its original
  fact even after later changes; an old reversal cannot undo newer coverage.
  Failed history writes roll back both points and pricing. Active rewards block
  beneficiary changes and cancellation; any reward history blocks line removal
  and demo reset. Paid rewards cannot be reversed through the prepaid endpoint.
- Refuse nonempty ledger, tier, earning, policy, reward or redemption downgrades before DDL. Demo reset
  cannot erase tickets linked to earning history.

## Verification and remaining work

HTTP checks cover role/institute boundaries, strict integer inputs, replay, changed
intent, tier transitions, failed-flush rollback and history. PostgreSQL races cover
duplicate credit, competing corrections, duplicate closure, policy/closure and
currency/policy races, duplicate spending/reversal and correction/spending
races without overdraft; SQLite/PostgreSQL migration parity and
round-trips are checked on disposable databases. This is a loyalty foundation,
not the complete LOYALTY gate. Customer balance/tier, point and redemption history are visible in Offres.
The customer snapshot endpoint reads balance and both histories under the institute
lock in one transaction, preventing mixed readings during concurrent closure or
correction. The overview uses this response, checks beneficiary/shape and clears facts during refresh and rejects obsolete institute/customer/token
responses, including same-component context changes. Manager tier configuration preserves a whitelisted pending intent in actor/institute
scoped session storage before sending. Lost responses reuse the original key after
remount; definite client rejection restores editable fields. Institute/token changes
replace the form and invalidate late callbacks. Reception can read tiers.
Earning/reward configuration, manual correction and checkout action UI plus
browser/tablet end-to-end verification remain required; production readiness is not inferred.
