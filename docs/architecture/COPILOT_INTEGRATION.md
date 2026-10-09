# Copilot integration — phase 20

The Copilot uses the pinned official `ai-swiss/base@1.5.1` router and prepared process context. FlowPilot owns a closed capability registry, signed institute scope, existing service dispatch and response evidence. There is no independent language router, generated SQL or model authority.

## Customer slice (20A)

`POST /api/v1/copilot/query` accepts a nonblank bounded message and an explicit `ui_context.customer_id`. Institute, role and actor come from JWT claims. Missing selection or unsupported process returns clarification without business reads. Unknown or foreign customer references return the existing scoped not-found error.

`GET /api/v1/copilot/capabilities` exposes only authorized registered schemas and services:

| Capability | Existing authority | Permission | Projection |
| --- | --- | --- | --- |
| CLIENT_READ | customers.repository.require_customer | customer operator (reception or institute manager) | Registered identity/name/creation time; phone and internal creation fields omitted |
| CLIENT_SUMMARY | crm.profile.read | institute manager only | Observed CRM profile and original policy; explicit unavailable reason and incomplete history |

No external language provider is called and no raw customer facts are sent to BASE routing. Only the message reaches the framework. Responses contain source facts, capture/completion clocks, SHA256 integrity and no actions. SHA256 is neither a signature nor a retained business original. BASE operational correlation records signed scope, interaction ID and digests without raw messages or customer facts.

## Remaining phase gates

COPILOT_READ remains PARTIAL pending all initial customer, planning, revenue, stock and employee capabilities in Master Plan §41. CLIENT_SUMMARY is a CRM segment summary, not a comprehensive customer history. Rebooking opportunities and all other required integrations remain open. COPILOT_SUGGEST, COPILOT_PREPARE and COPILOT_EXECUTE_GUARDED remain open. This checkpoint does not establish remote model quality, user interface acceptance or production readiness.
