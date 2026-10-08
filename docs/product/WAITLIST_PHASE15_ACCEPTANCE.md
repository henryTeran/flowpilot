# Phase 15 — canonical acceptance audit

Authority: Master Plan section36 and Definition of Done section64, architecture
foundations, current source and tests. Audit starts from clean implementation
HEAD `26ded3b`. No application, schema or policy change is part of this checkpoint.
The full26-phase objective remains active. All three functional gates PASS at the
controlled local scope proved below. Production, physical-device, live-provider
and large-cohort/load acceptance remain separate OPEN gates.

## Requirements and evidence

The canonical section asks for matching according to nine dimensions and names
WAITLIST, WAITLIST_MATCHING and AUTO_SLOT_DETECTION. A conditional recorded-capacity
option is not a reservation, physical attendance, opening-hours proof or permission
to send. Unknown source conditions explicitly refuse options. No score, price,
customer preference, follow-up intention or operational policy is invented.

| Canonical item | Implemented behavior and authoritative evidence | Practical limit |
| --- | --- | --- |
| Waitlist | `originals.py`, `lifecycle.py`, migrations15B/C and signed routes retain explicit demand, activation, replacement and terminal cancellation. Native15G/I/J/K covers authoring, histories, original/key recovery and version conflicts. | Declaration alone is inactive; administrative activation is not current eligibility. |
| Service | Retained owned registration/catalog capture; current `sources.py` rereads active service under institute scope. Original/new-action duration and service binding are validated;15B/D tests and15I/M UI exercise this. | Retained source is historical; inactive/unavailable current service refuses. |
| Duration | `domain.py` exact elapsed-instant fit and declared/current duration equality, with15A/D cases for microseconds, repeated civil hours and changed catalog duration.15I authors catalog duration;15M exposes declared/current values. | No wall-clock duration inference or silent rewrite of customer terms. |
| Customer availability | Explicit ordered positive evidenced windows; matching intersects them with captured employee/resource fit and customer booking/session/projected-queue blockers.15A/D/F and institute-calendar/15I/M tests cover boundaries and civil-time ambiguity. | Availability is declared, not inferred from CRM behavior or physical presence. |
| Employee | Explicit owned employee restrictions and current core free windows;15A/D/F tests and15I authoring.15M shows source-bound employee alternatives with labels and identifier fallback. | Empty restriction is explicitly unrestricted; no invented preference or autonomous assignment. |
| Skills | Existing `has_required_skills`, owned current requirement/skill facts and strict source capture;15A/D tests refuse unqualified alternatives.15L contracts verify each displayed employee covers captured skills. | No new skill scoring or physical qualification certification. |
| Resources | Existing complete distinct-unit `next_resource_window`, owned current inventory/reservations and core queue allocations as virtual blockers.15A/D/F tests exercise joint fit, distinct units, missing-machine configuration and conflicts;15L checks displayed assignment coverage. | Independent alternatives do not jointly reserve units; native15M resource-free fixture does not prove a new physical multi-resource execution. |
| Constraints | Explicit confirmed/unknown human review, customer conflicts, recorded absences/bookings/sessions, overdue/unknown capacity, resource configuration and unprojectable queue refusal.15A/D/F/L tests verify uncertainty remains unavailable; native15M renders reasons and queue coverage. | Confirmation is a human declaration, not machine verification of all real-world or medical constraints. |
| History | `sources.py` captures recorded care since registration, latest clean episode and diagnostics; explicit review/observed/no-recorded rules refuse when unmet.15D SQL tests and15L/M contracts/components bind dates/references and policy. Native15M exposes no-recorded-care source context. | Unknown is not “never visited”; recorded coverage is not complete real history or follow-up intent. |
| Consents | Current retained CRM original, chosen email/SMS service-follow-up channel, grant/refusal/unknown and future-declaration refusal; explicit review/recorded-grant policy.15D/L plus native15M exercise absent, granted and refused current permission. | No care consent, marketing permission or delivery authority inferred from a slot review. |
| Auto slot detection | `detection.py` automatically derives conditional matches for the whole active cohort under an explicit horizon/policy and one locked capture before20-row paging.15E/F verify off-page corruption, count partitions and queue constraints.15M native reads25/50 roots with real paging and source invalidation. | Explicitly requested computation, not an unspecified background schedule or automatic offer/contact. Alternatives are independent, not a jointly executable plan. |
| Sensitive-action audit | Demand/action originals retain signed actor, reason, key, request, capture, source and full raw JSON/SHA. Chains bind root/target/predecessor and original recovery; complete cohort audit precedes paging. Browser15H/K persists exact intent before I/O and independently rereads key/ID/state before cleanup. | Consistency evidence is not SQL-administrator authenticity or an append-only-trigger claim. Read-only matching/detection executes no sensitive action. |
| Permissions and tenant isolation | Every route uses manager/exact-institute guards; owned customer/employee/resource/source validation and signed scope tests15B/C/D/E. Browser manager guards and token/scope/timezone/unmount/sequence invalidation hide stale proof. | Controlled signed test environment, not a new production penetration test. |
| Errors, transactions and concurrency | Strict aware bounds/DTOs, refusal of malformed current sources, optimistic predecessor and unique keys, real PostgreSQL same-key/conflicting-successor races, rollback/lost-ack recovery, raw/rehashed tamper and guarded migrations.15I/K/M show frozen correction/retry and stale-source masking. | No cross-tab locking, production failover or distributed-load extrapolation. |
| UX and responsive | Native retained declaration/lifecycle authoring/history and explicit current policy/horizon review; empty defaults, progressive proofs, error/retry, real paging, focus/scroll,44px targets and no overflow. Five specs run desktop/touch landscape tablet. | Browser profiles, not portrait/mobile/physical-device certification. |
| Observability | Retained actor/reason/capture/key/fingerprint and paged audit expose each sensitive decision and causal chain. Matching/detection expose dated source/refusal/coverage and strict no-action claims; ordinary API error handling remains in place. | Production telemetry, alerting, topology and incident acceptance stay separate. |
| Deterministic truth | Official matching delegates to existing domain kernels and exact UTC microsecond arithmetic. Browser validates proposed proof/assignment; it does not search for another slot or generate an official result. | No LLM-generated business calculation, prediction, revenue score or ranking. |

## Scope correction from earlier remaining-work notes

Earlier SMART_WAITLIST matrix rows still said native lifecycle/matching review was
missing after15K/M implemented it. They also proposed unspecified additional
employee preferences and structured constraints. Section36 requires the nine
dimensions above, not a new preference taxonomy, a clinical rules engine or a
background/contact policy inferred by the assistant. Existing explicit restriction,
known/unknown constraint evidence and captured sovereign blockers fulfill those
dimensions at the conditional recorded-source scope. New kinds of preference or
constraint require their own explicit policy; they are not fabricated to close a gate.

Automatic detection means the existing deterministic computation derives options
from the complete active cohort; the user chooses the horizon and review rules.
No background trigger, dispatch, reservation or LLM optimization is implied.
Actual booking/contact requires its separate existing authority and revalidation.

## Fresh verification

Implementation is unchanged from `26ded3b`; frontend baseline is15M **457 passed
93.91s**, zero failures/skips/cancellations, terminalexit0; production build181 modules,
terminalexit0.15M's eight final screenshots were individually inspected on this
same implementation. The fresh sweep below asserts dimensions/paging/recovery
without claiming manual inspection of every newly generated capture.

Fresh complete eight-module Phase15 backend suite: **42 passed169.49s**, zero
failures/skips, terminalexit0. SQLite and actual isolated PostgreSQL tests include
original/lifecycle retention, signed role/tenant routes, rollback/lost-ack recovery,
same-key/conflicting-successor races, raw/rehashed/off-page tamper, guarded migration
roundtrips, current history/permission/capacity/queue and whole-active detection.
Three warnings: existing crypt deprecation and two intentional unsafe-copy
Pydantic serializer warnings in invalid-source tests. Not a whole-project run.

Fresh five independent native specs: **10 passed** across desktop/touch landscape
tablet. Every case production build/test/owned cleanup passed; supervisor
`NATIVE_AUDIT_ALL_CASES_EXIT=0`, terminalexit0. Original history2 passed1.2m; demand
authoring2 passed41.0s; lifecycle history2 passed48.0s; lifecycle transitions2
passed50.1s; current matching/detection2 passed1.2m. Includes real20-row paging,
unknown/retained/source proof, committed lost acknowledgement/key recovery,
stale-version rejection/correction, explicit policies, current granted/refused
permission, corruption mask/retry, focus/44px/no overflow. API source fixtures are
not new native authoring claims; native declaration and lifecycle authoring are
covered by their dedicated specs. Existing bcrypt/NO_COLOR warnings and a Windows
connection-reset message during final browser/server teardown did not fail tests
or owned cleanup; every native case and supervisor exited0.

The dedicated `flowpilot-phase4-validation` PostgreSQL15 container and readonly
backend runner were stopped when this audit began. Restarted the dedicated test
containers; readiness first rejected connections during startup, then accepted.
Tests use `FLOWPILOT_TEST_POSTGRES_URL` and randomized owned schemas with cleanup.
Application `flowpilot_postgres` was not used or migrated. Native harnesses rebuild
the production frontend and each own a fresh marked temporary SQLite database,
removed on completion. No live provider, deployment or persistent application DB
migration is part of this audit.

## Gate decision

```text
WAITLIST = PASS
WAITLIST_MATCHING = PASS
AUTO_SLOT_DETECTION = PASS
SCOPE = CONTROLLED_LOCAL_FUNCTIONAL_ACCEPTANCE
PRODUCTION / PHYSICAL / LIVE_PROVIDER / LARGE_COHORT_LOAD = OPEN
```

The fresh results and source audit prove the nine dimensions, explicit lifecycle,
conditional detection, signed scope, meaningful audit/recovery and responsive UI
at this scope. All listed Phase15 functional requirements are implemented and
verified by the scoped evidence above.
Proceed to canonical Phase16 deterministic scheduling optimizer; no Phase16 gate
is claimed yet.

The full26-phase goal stays ACTIVE. Whole-project fresh backend validation,
production migrations/topology, provider/physical/load acceptance and later
canonical phases are not certified by this Phase15 functional audit.
