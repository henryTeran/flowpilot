# Commerce — Phase 8

The detailed Master Plan sections define Phase 8 as Commerce and Phase 12 as CRM.
The shorter initial sequence labels Phase 8 Client 360; implementation follows the
detailed numbered requirements. Browser/tablet Phase 7 gates remain open separately.

## Package checkpoint 8A

`commerce` owns institute-scoped package plans, customer entitlements and redemption
history. Manager-only plan creation and issuance require an exact token institute;
operators may read and consume within their institute. Plans define a named cure,
one service, session count and validity in days. Issuance snapshots these terms and
records its actor/time. Required institute-scoped replay keys recover one attribution
or redemption; different intent with the same key rejects.

Customer references use the existing ticket `customer_id` contract. This checkpoint
does not create or claim a CRM profile. A redemption requires a matching customer
reference/service, a performed ticket line, and a ticket awaiting checkout/payment.
It covers the full line quantity; partial line coverage is not implemented. A line
can be covered once across all packages. Session balance, original line prices,
zeroed covered line, recalculated ticket total and history commit together under the
institute lock. Checkout line edits and payment share that lock. Expiry is exclusive:
at `expires_at` the balance is unusable; remaining sessions/history are preserved.
Replay returns the existing redemption even after payment or expiry.

Plans and package grants do not issue invoices or claim settled payment. Manager
issuance is an explicit entitlement action; the package sale/payment flow remains
to implement with the commercial UI and PaymentProvider phase. Package consumption
removes the covered session's checkout charge; it does not reassign performing or
cashier employees. There are no LLM business decisions.

Covered lines cannot be removed and covered tickets cannot be cancelled until a
commercial reversal workflow exists. Demo reset refuses to erase redemption-linked
tickets rather than delete commercial history. API/UI reversal, customer selection
and booking customer-reference binding are next package tasks. PACKAGES is still
IN_PROGRESS; memberships, gift cards and loyalty remain pending.

Migration `b9d234a764cf` adds positive terms, nonnegative bounded balances, expiry,
foreign keys, scoped replay uniqueness and one-redemption-per-line constraints.
SQLite/PostgreSQL upgrade/downgrade/model-parity checks pass; PostgreSQL upgrade/check
passes. HTTP tests cover roles/tenant, validity, customer match, expired rejection,
replay, unchanged state after failure following flush, price coverage and payment
recovery. A PostgreSQL two-checkout race proves only one last-session debit.
The race preloads both session balances before acquiring the institute lock;
explicit refresh prevents stale ORM identity-map values from authorizing a second
debit. Final package suite in the PostgreSQL runner: three passed. Full local backend
run: 195 passed, 19 PostgreSQL cases skipped; final local package/checkout/revision
regressions: 12 passed, one skipped. Browser/UI package validation is still pending.
