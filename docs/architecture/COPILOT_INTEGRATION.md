# Copilot integration — phase 20

The Copilot uses the pinned official `ai-swiss/base@1.5.1` router and prepared process context. FlowPilot owns a closed capability registry, signed institute scope, existing service dispatch and response evidence. There is no independent language router, generated SQL or model authority.

## Customer slice (20A)

`POST /api/v1/copilot/query` accepts a nonblank bounded message and an explicit `ui_context.customer_id`. Institute, role and actor come from JWT claims. Missing selection or unsupported process returns clarification without business reads. Unknown or foreign customer references return the existing scoped not-found error.

`GET /api/v1/copilot/capabilities` exposes only authorized registered schemas and services:

| Capability | Existing authority | Permission | Projection |
| --- | --- | --- | --- |
| CLIENT_READ | customers.repository.require_customer | customer operator (reception or institute manager) | Registered identity/name/creation time; phone and internal creation fields omitted |
| CLIENT_SUMMARY | crm.profile.read | institute manager only | Observed CRM profile and original policy; explicit unavailable reason and incomplete history |
| CLIENT_REBOOKING_OPPORTUNITIES | crm.rebooking.read → existing crm.event_sources.read | institute manager only | Recorded rebooking rule/candidate, policy original ID/digest, relevant diagnostics and active customer booking slots |
| PLANNING_READ | planning.service.get_day_planning | planning operator (reception or institute manager) | Current day session IDs/services/times and employee status, without names |
| PLANNING_GAPS | scheduling.service.availability_pool | planning operator | Current/future engine windows with original blocker IDs and unavailable reasons; optional explicit service selection |
| EMPLOYEE_CAPACITY | revenue.capacity.read | institute manager only | Explicit completed local day recorded work/activity aggregates and bounded employee evidence |
| PLANNING_CONFLICTS | workforce.conflicts.read / resources.conflicts.read | institute manager only | Selected employee OR resource/day overlaps and explicit invalid/overdue diagnostics |
| REVENUE_SUMMARY | revenue.sources.read | institute manager only | Explicit observed period recorded paid-ticket/active-line aggregates, currency-separated amounts and original quality diagnostics |
| REVENUE_OPPORTUNITIES | revenue.slot_opportunities.read | institute manager only | Explicit service/future horizon conditional queue and capacity projection, or original unavailable reason |
| REVENUE_LOSS_ANALYSIS | revenue.closures.read / revenue.walk_in_cancellations.read | institute manager only | Aggregate recorded closures, retained commercial amounts and unknown causal financial loss |
| STOCK_READ | inventory.outlook.read | inventory operator (reception or institute manager) | First50 recorded stock/threshold/pending-order quantities |
| STOCK_FORECAST | inventory.outlook.read with explicit ForecastScenario | inventory operator | Selected service volumes, pinned original recipes and exact conditional demand/shortfalls |

No external language provider is called and no raw customer facts are sent to BASE routing. Only the message reaches the framework. Responses contain source facts, capture/completion clocks, SHA256 integrity and no actions. SHA256 is neither a signature nor a retained business original. BASE operational correlation records signed scope, interaction ID and digests without raw messages or customer facts.

## Rebooking suggestions (20B)

The existing CRM event engine supplies the latest observed completed-care anchor and the explicit retained automation rule. Copilot does not infer a return interval from language or incomplete customer history. The read-only CRM adapter projects only the rebooking candidate and relevant missing/invalid source diagnostics; unrelated birthday, communication declarations and package/membership facts are omitted. The policy digest identifies the full existing original, retrievable through the authorized CRM endpoint; it is not a signature or the hash of the projected rule alone.

The institute-locked read also checks this registered customer's scoped active appointment slots using the existing active status set. A due candidate without such bookings is a review opportunity; an existing future/ongoing booking asks the manager to examine it first. This conservatively avoids suggesting an additional booking regardless of service; it does not prove the existing booking satisfies the same care need. Disabled/not-yet-due rules are explicit. Missing/invalid care sources and malformed active slots prevent an affirmative opportunity. No time, employee, service, price, consent or availability is invented. Booking, outbound contact and durable event capture remain separate guarded workflows.

## Planning and capacity reads (20C)

The common orchestrator now lives in `app.modules.copilot.query` and uses the same official BASE router for every registered process. Capability-specific input schemas and closed selection checks prevent a customer selection being reused for a planning read. Calendar days must be explicit ISO dates; capacity rejects incomplete/future days through its existing observed-window rule. Manager permission remains required for capacity; reception can consult operational planning and availability.

Planning gaps preserve the existing availability engine's current and upcoming windows, qualifications, resource/absence blockers and unknown reasons. They are not an optimization proposal or a guarantee of declared working hours or a booking that fits a requested care duration. Employee capacity measures finalized recorded activity intersected with declared work, not physical attendance or future bookable capacity. Missing hours or uncertain activity remain unknown. Whole-institute aggregates are computed by the original service even though only its bounded first employee page is returned. Source capture clocks are preserved; completion must not precede capture. No names, customer phones or appointment notes are projected by the planning adapters.

## Employee commitment conflicts (20D)

PLANNING_CONFLICTS accepts an explicitly selected employee and local institute day. It preserves the existing manager-only employee-calendar authorization and locks the institute before requiring the scoped employee. The workforce application service reads current appointment slots, planned session slots and uncancelled absences, using the existing active-status sets. It deliberately reads current appointment times rather than historical booked times. Exact intersections use existing half-open interval arithmetic; adjacency and redundant absence/absence declarations are not service conflicts. No customer name, contact, appointment notes or absence reasons are returned.

The response counts the full accepted cohort's overlaps and returns the first 50 deterministically, with both original source references and exact clipped intersection duration. A digest binds the ordered minimal valid source cohort; the response digest also covers diagnostics and capture clocks. More than 1000 active source records for the employee fails explicitly rather than silently truncating. Invalid active sources are counted across the captured employee cohort, because an invalid interval cannot be reliably assigned to a day. Open obligations whose planned end has passed preserve an overdue diagnostic; actual end is not guessed. Recorded commitment overlaps do not prove simultaneous physical activity.

The employee response retains `resource_conflicts_covered=false`: a selected employee read does not examine every physical resource. The resource variant below examines a separately selected resource. Neither response establishes complete institute conflict coverage or physical occupancy.

## Resource reservation conflicts (20E)

PLANNING_CONFLICTS now also accepts `resource_id` instead of `employee_id`, with the same explicit day and manager permission. Selecting both is refused; missing target/day clarifies without dispatch. The closed registry exposes both result schemas and the exclusive target selection. Resource reads require the selected resource in the exact signed institute and lock that institute. Only unreleased reservations belonging to the selected resource/institute are captured; each ticket or appointment owner is independently verified in the same institute. Foreign/missing owners are counted as invalid without returning their identifiers.

Reservation overlaps use the same exact half-open intersection calculation and deterministic first50/full-count presentation as employee commitments. Released reservations do not consume a source slot. Unreleased reservations whose recorded end has passed remain explicit unknown-capacity diagnostics across the selected resource cohort, matching the existing allocation timeline rule. Inactive/maintenance resource state remains visible. No resource name, customer details, inferred repair, mutation or booking authority is returned. The response describes one selected physical unit's recorded reservations, not an inventory-wide feasibility or missing-allocation audit. Existing configuration/allocation services remain authoritative for actual booking admissibility.

## Recorded revenue summary (20F)

REVENUE_SUMMARY accepts explicit aware `start` and `end` instants from UI selection. Signed institute manager permission is required before source dispatch; unrelated customer/employee/service selections are refused. The existing locked revenue source service enforces an observed positive half-open period and calculates the full paid-ticket cohort and nonremoved invoice-line aggregates. Capture clocks and the entire typed aggregate are preserved, without customer/ticket/line records or external provider calls.

CHF/EUR and unknown currency remain separate. Missing or invalid recorded amounts do not become complete revenue; the source's institute-wide undated-paid diagnostic is not assigned to the selected period. Recorded billing is not a proof of settlement, complete sales or causal financial loss.

## Commercial capacity opportunities (20G)

REVENUE_OPPORTUNITIES reuses the existing commercial slot reader and its waiting-projection engine. It requires manager authorization, a selected active service and an explicit positive future horizon. Prior queue, care duration, employee qualifications, appointment/resource blockers and original missing-configuration/unknown-capacity/outside-horizon reasons remain authoritative. Copilot does not reproduce the scheduling or resource allocation rules.

The typed source retains capture time, required skills/resources, prior queue count and conditional projected slot. Estimated financial value stays null; capacity is not reserved and no assignment is executed. Opening hours and capacity must be checked again before any subsequent domain action. This is the commercial-capacity opportunity slice, not a claim that all revenue opportunities have been exhausted; closure follow-up, retained valuations and scenario integrations remain distinct sources for later scope audit.

## Closure-based loss analysis (20H)

REVENUE_LOSS_ANALYSIS requires manager authorization and an explicit observed period. The adapter invokes both existing institute-locked source readers, which validate original booking closure transitions and retained walk-in cancellation terms across their full cohorts, including records beyond their returned pages. It projects full aggregate cancellation/no-show/unpriced counts, terminal bookings without events, retained terms/legacy counts and currency-separated recorded commercial amount groups. Customer, actor, booking/ticket/line dossiers and individual follow-up suggestions are omitted.

Each projected group preserves its original observation window and a digest of the complete reader response, including that reader's bounded default page; this is not a digest of every underlying database event or a retained/signature proof. Both readers share the transaction's institute lock but retain separate capture clocks. No timing is rewritten into an invented common capture. Financial loss remains null, causal-loss proof false and complete history false. Missing, invalid and unknown-currency amounts remain exactly as represented by the sovereign source kernels. Historical commercial terms are neither revenue realized nor money causally lost; the model supplies no causes or estimates.

## Recorded stocks and explicit scenarios (20I)

Both stock capabilities preserve existing inventory operator authorization. STOCK_READ accepts no business selection and returns the existing outlook's first50 items. STOCK_FORECAST requires an explicit scenario from UI: aware ISO start/end instants, bounded service volumes and selected original recipe IDs (including explicit null when a norm is missing). The domain enforces original recipe/service/institute scope, positive horizon up to366 days and exact integer quantities. Copilot does not infer volumes or silently choose today's recipe. Numeric epoch scenario instants are refused at the Copilot boundary.

The existing outlook reader supplies exact recorded stock, reorder thresholds, pending orders, selected-norm coverage, conditional demand and shortages. Pending orders are not physical receipts; incomplete norms remain partial with complete demand unknown. Only the existing bounded first item page is returned, not a claim to list all inventory items. This read-only forecast does not create a purchase order, receive goods, consume stock or authorize a reorder. Other observed/planned inventory projection sources and initial capability scope must still be audited before whole-phase closure.

## Remaining phase gates

COPILOT_READ and COPILOT_SUGGEST remain PARTIAL pending the complete initial capability scope audit and packaged acceptance in Master Plan §41. CLIENT_SUMMARY is a CRM segment summary, not a comprehensive customer history. COPILOT_PREPARE and COPILOT_EXECUTE_GUARDED remain open. These checkpoints do not establish remote model quality, user interface acceptance or production readiness.
