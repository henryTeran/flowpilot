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

Customer references use the existing ticket `customer_id` contract, extended by
the minimal identity checkpoint below. The full Phase 12 CRM lifecycle is not
claimed. A redemption requires a matching customer
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

Lines with commercial history cannot be removed. Tickets with active coverage
cannot be cancelled; after reversal cancellation is permitted and history remains.
Demo reset refuses to erase redemption-linked tickets rather than delete commercial
history. Package application/reversal controls in the operator UI remain package
tasks. PACKAGES is IN_PROGRESS; memberships, gift cards and loyalty
remain pending.

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

## Reversal checkpoint 8B

The manager-only `POST /package-redemptions/{id}/reverse` restores the consumed
session count and the exact recorded line price before payment. It requires a
nonempty reason and stores reversal actor/time/reason on the original consumption;
original consumption facts are retained. Repeating the same reversal returns its
current state, without another credit or price change; a changed reason rejects.
Expiry remains unchanged, so reversing an expired package restores recorded balance
without making sessions usable. Paid/cancelled tickets reject a new reversal.
Refund/settlement after payment remains PaymentProvider work in Phase 9.

Consumption replay after reversal returns the reversed record. Reapplying coverage
requires a new intent/key and creates a new historical consumption. A partial unique
index permits one active coverage per line while retaining prior reversed rows.
Replaying an earlier reversal cannot affect a newer application. Price, total,
balance, event and reversal facts share one institute-locked transaction; failure
after flush rolls everything back.

Migration c0e345b875d0 passes SQLite/PostgreSQL round-trip/model parity and PostgreSQL
upgrade/check. Downgrade with reversal facts refuses before schema changes rather
than reinterpret reversed history as active consumption; this guard is exercised
against SQLite and a disposable PostgreSQL schema. Full backend: 198 passed, 21
PostgreSQL cases skipped locally. Combined package/reversal/migration PostgreSQL
bundle: 10 passed; final reversal suite: 5 passed, including cached-state duplicate
reversals and reversal versus payment. Actual operator UI remains to implement.

## Customer-selection checkpoint 8C

Commercial beneficiary selection needs a persistent identity before the larger
Phase 12 CRM lifecycle. The `customers` module provides exact-tenant operator
creation, search and detail reads: display name, optional phone and creation actor/
time. Required replay keys recover a creation after a lost response; changed facts
reject. Names/phones are not unique and never automatically merge people. Search
normalizes accents/case and phone formatting, escapes wildcard input and limits
results. Empty searches do not enumerate the customer list.

The walk-in Cliente step and booking form now share a customer picker with search,
explicit selection and replay-safe creation. Names are shown instead of technical
IDs. Anonymous arrival retains the existing direct service-selection path. The
selected ID enters ticket creation and its replay fingerprint; changing institutes
disposes the previous picker. Late search results cannot replace newer results.
Bookings validate registered customer scope on creation/modification and propagate
the selected identity into the completed booking's checkout ticket. Human booking
names/phones remain visit snapshots rather than edits to the identity record.

Legacy opaque ticket/package references remain readable and usable. Newly registered
references are validated against the selected institute; unknown reserved customer
IDs and foreign registered IDs reject. No historical names are merged or assigned
identities by migration. Legacy booking replay fingerprints remain stable when no
customer ID is supplied. Migration d1f456c986e1 passes SQLite/PostgreSQL round-trip/
model parity and PostgreSQL upgrade/check; downgrade refuses populated identities.

Backend full run: 200 passed, 21 PostgreSQL cases skipped; final identity checks:
two passed. Identity/migration/reversal PostgreSQL-runner bundle: nine passed.
Frontend: 25 tests and production build passed, including stale search protection,
lost-response creation retry and named walk-in identity submission. HTTP coverage
also completes a selected-customer booking and consumes its cure at checkout.
These are component/protocol checks; browser/tablet gates and the package wallet UI
remain open. Consent, customer lifecycle, marketing and full CRM are later work.

## Checkout-wallet checkpoint 8D

Checkout now loads the selected customer's package balances/history and identity,
displays their name rather than an internal identifier, and offers full-line session
coverage when the backend balance/service and performed-line facts permit it.
Application retains its replay key across uncertain responses. Managers see the
pre-payment reversal action; this is a presentation hint from token claims, while
the API remains the authoritative permission check. Historical consumption rows
protect line deletion; active coverage prevents ticket cancellation.

Writes disable payment while outstanding. After a lost response the wallet reloads
history and the App reloads operational prices; payment stays blocked if this
reconciliation fails and an explicit refresh can recover it. Refresh returns a
success flag rather than allowing a swallowed error to unlock checkout. Disposed
contexts and superseded reads cannot apply wallet state. Remote ticket refreshes
also refresh package eligibility. Customer registration alone no longer labels a
customer as loyal: loyalty remains a separate pending feature.

Frontend validation: 26 tests and production build pass, including lost consumption
response, uncertain-payment blocking, explicit recovery and pre-payment reversal.
This is JSDOM/component evidence; actual browser/tablet UX remains unverified.
Package-plan configuration/issuance UI, anonymous-ticket customer attachment and
the package sale/settlement flow remain open. PACKAGES is not yet fully closed.

## Checkout-identity checkpoint 8E

An anonymous arrival can now select or register a customer in checkout, then use
that customer's package wallet. `PATCH /tickets/{id}/customer` accepts a registered
customer in the authenticated operator's exact institute, or null for an anonymous
passage. It requires ready-for-checkout/in-checkout status and acquires the same
institute lock as consumption and payment. Changing the beneficiary is refused
while any package coverage is active; reversal allows correction before payment.
The original arrival fingerprint stays unchanged, so an arrival retry returns the
current ticket rather than creating a second arrival. Actual care, employee, prices
and historical redemption records remain unchanged. A transactional queue event
and the existing request audit identify the change without logging contact details.

Checkout disables payment and line changes during identity writes. A lost response
triggers a full operational refresh; failed refresh keeps payment blocked until an
explicit retry succeeds. Ticket/institute disposal and token changes prevent old
completions from updating the new checkout. Historical line protections already
observed by the panel survive a customer correction; server ledger guards remain
authoritative after a fresh mount.

Validation: HTTP scope/status/coverage/reversal/replay/rollback checks and real
PostgreSQL beneficiary-versus-consumption and beneficiary-versus-payment races.
JSDOM verifies anonymous selection, lost-response blocking and explicit recovery.
Actual browser/tablet gates remain open. Package management/issuance UI and the
sale/settlement flow still remain; this checkpoint does not close PACKAGES.

## Package-management checkpoint 8F

The institute's Offres screen lists cure terms and customer balances. Managers can
configure a cure's service, number of sessions and validity in days, select/register
a customer, and grant the cure. Reception can consult customer packages but cannot
configure or grant them. Token claims only control presentation: existing exact
institute/manager API checks remain authoritative. Terms are immutable here; a new
configuration creates a new plan, while issued packages retain their term snapshots.
Grant success clears the selected plan, requiring deliberate reselection for another
grant. The screen explicitly distinguishes granted rights from an encashed sale.

New configuration submissions carry stable replay keys, as grants already do.
Migration e2a567da97f2 adds institute-scoped plan replay keys and immutable creation
fingerprints. Repeated identical configuration returns the original plan even if
its service has since become inactive; a changed intent with that key is refused.
Existing plans and older API callers without keys remain compatible. The institute
lock serializes concurrent same-key creation. Downgrade refuses to discard keyed
creation recovery; the empty/legacy migration round-trip remains supported.

Validation: full backend suite 202 passed/24 opt-in cases skipped; final local replay
test passed. Actual PostgreSQL replay/package/migration bundle: seven passed, including
same-intent creation race, keyed downgrade refusal and migration/model parity/round-trip.
Frontend: 28 tests and production build pass, with configuration/grant lost-response
retry and reception presentation restrictions checked in JSDOM. No real browser/tablet
proof is claimed. The detailed Phase 8 PACKAGES functional scope (cures, sessions,
consumption, expiration) now passes at these server/component scopes. Memberships,
gift cards and loyalty remain pending; paid sale/external settlement is Phase 9 work.

## Membership-lifecycle checkpoint 8G

The memberships module now owns institute-scoped plans, registered-customer rights
and renewal history. Plans specify a name and validity in days; issued rights
snapshot those terms. Manager-only configuration, attribution and renewal require
exact institute scope and mandatory replay keys. Reception can read scoped plans,
customer memberships and renewal history. Granting rights does not record payment
or enable automatic billing; sale/settlement remains Phase 9 work.

Active rights use a half-open UTC validity interval. Renewal before expiration adds
the snapshotted duration to the existing expiry; renewal at/after expiration starts
a new period at the operation time, preserving any gap in the renewal facts.
History stores previous/new validity, time and signed actor. Same-key renewal returns
the original immutable event rather than extending again. Same-key attribution
returns the current membership; changed beneficiary/plan intent is rejected.

All writes use the existing institute lock. New rights cannot overlap another live
membership for the customer; an expired membership cannot be restarted if a replacement
is already live. Concurrent identical attribution/renewal produces one fact; distinct
renewal intents extend in sequence using fresh database state. A failed renewal flush
rolls back both the validity window and its history. Migration f3b678eba803 refuses
downgrade when membership records exist, while empty SQLite/PostgreSQL round-trip
and model parity remain supported.

This is the lifecycle API foundation. Existing service.price_member values have not
yet been applied from these rights; checkout benefit/reversal/coverage integration
and manager/customer interface remain next. MEMBERSHIPS is not closed.
