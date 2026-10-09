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
| PLANNING_CONFLICTS | workforce.conflicts.read | institute manager only | Selected employee/day current commitment overlaps and explicit invalid/overdue diagnostics |

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

Resource conflict detection remains open: `resource_conflicts_covered=false`. This is the employee commitment slice of PLANNING_CONFLICTS, not completion of all planning conflict coverage or the whole Copilot phase.

## Remaining phase gates

COPILOT_READ and COPILOT_SUGGEST remain PARTIAL pending all initial planning, revenue, stock and employee capabilities in Master Plan §41. CLIENT_SUMMARY is a CRM segment summary, not a comprehensive customer history. COPILOT_PREPARE and COPILOT_EXECUTE_GUARDED remain open. These checkpoints do not establish remote model quality, user interface acceptance or production readiness.
