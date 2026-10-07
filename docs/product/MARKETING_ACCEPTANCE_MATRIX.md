# Phase 13 functional acceptance

Authority: `FLOWPILOT_MASTER_PLAN.md` section34, eight deliverables and four gates.
Review date: 2026-10-07. This closes local functional acceptance, not production,
physical-device, live-provider delivery or real settlement acceptance.

| Required deliverable | Authoritative implementation and evidence | Result |
| --- | --- | --- |
| Segmentation | CRM owned policy/profile facts; marketing `audiences.py`, signed bounded observations and six explicit segments. `test_marketing_audiences_13b.py` verifies scoped registered customers, current policy/permission and nonfuture shared capture. | PASS |
| Audiences | `audience_originals.py` and contact-backed captures, one locked capture across all pages, retained member/source originals, exact counts and original-key replay. Legacy lifecycle and registered SMS/email/push declarations have explicit distinct permission bases. `13e`, `13aa` and native audience/contact workflows cover owned selection and corruption/refusal. | PASS |
| Campaigns | `campaign_originals.py`, source-bound immutable drafts/edits, signed actor/request replay and current/audit readers. Native creator/editor/SEND actions recover lost acknowledgements. `13i`, `13an`, `13ao`, `13ap`; frontend campaign/creator/actions contracts. | PASS |
| Templates | `templates.py`, strict three-channel literal content, human/declared AI origin, retained source references, review/approval digests, edit reset and key/ID/audit recovery. `13h` and native template workflow. | PASS |
| SMS | Registered explicit destination/grant, approved retained message and account scope, trusted worker unknown-before-I/O marker, optional fixed-host Twilio transport, known-reference reconciliation without blind resend. `13w/y/z`, `13ag/ak/al/am` test ownership, freshness, credentials and fake-wire behavior. | PASS locally; live acceptance OPEN |
| Email | Same source/permission/worker controls; literal subject/body and fixed-host Resend transport with scoped idempotency and known-reference reconciliation. Account/intent/outcome originals retain complete terms. `13ag/ai/aj/ak/al/am/aq/av`. | PASS locally; live acceptance OPEN |
| Push | Explicit registered application/token/grant, account application match, approved literal payload and optional FCM transport. Unknown outcome remains unknown where reconciliation is unavailable. `13w/y/aa/ag/al/am` and native contact/preparation channel checks. | PASS locally; live acceptance OPEN |
| Conversion tracking | `conversion_sources/originals/catalogs/tickets.py`, owned paid-ticket/accepted-intent/SEND binding, atomic link/retraction head, full historical fingerprints/source proof, separate live/test/currency diagnostics and complete current-link summary. Native selection/writer/current/audit/report; actual backend desktop/tablet lost-ack/recover/retract/audit/summary/current-catalog scenario. `13aw/ax/ay/az/ba/be`. | PASS locally |

AI-origin campaigns follow the same DRAFT -> REVIEW -> APPROVE -> SEND lifecycle.
Review/approval bind the exact retained content/audience digest; edits reset them.
SEND is an explicit retained manager declaration, not delivery. Origin is declared;
these gates do not attest that a model generated a particular literal message.
No LLM computes official segment, billing, permission or conversion truth.

## Fresh combined verification

- All31 `backend/tests/test_marketing_*.py` modules: **135 passed655.27s**, zero
  failures/skips, terminal exit0, SQLite plus actual isolated PostgreSQL. Includes
  all marketing migration modules, retained keys/heads/source scope/concurrency,
  transports/registry/invocation and conversion contracts/services. Existing crypt
  deprecation and deliberate unsafe-bool serializer warning only. This is full
  marketing scope, not a fresh full-project backend run.
- Full frontend: **364 passed72017.0781ms**, zero failures/skips, terminal exit0.
  After final low-impact history reference folding/copy cleanup, focused current
  catalog/history/report6 passed4555.4096ms and production build runs in the native harness.
- Current-catalog actual backend native scenario: initial2 passed1.0m; final2
  passed1.1m (desktop16.5s/tablet17.1s), terminal exit0, disposable fixture cleaned.
  It records one actual signed conversion POST despite acknowledgement loss/reload,
  then a distinct retraction with exact predecessor/full attribution retained.
  Summary/current catalog count one before retraction and zero after, while audit
  preserves two originals123.45CHF. Native earlier audience/template/contact/campaign
  channel/SEND/preparation/history acceptance is recorded in `MARKETING_GATE_AUDIT.md`.
  Native providers are fake/seeded recorded billing; this is not live delivery.

## Functional gates

| Canonical gate | Result | Basis |
| --- | --- | --- |
| SEGMENTATION | PASS | Owned policy/source-backed observed segments and complete retained audiences; no inferred contact permission. |
| CAMPAIGN_DRAFT | PASS | Native literal human/declared AI drafts/templates with owned retained audience/source terms and edit reset. |
| CAMPAIGN_APPROVAL | PASS | Signed immutable REVIEW/APPROVE/SEND chain, full digests, fresh source checks before first worker decision, explicit permissions and original replay. |
| CAMPAIGN_AUDIT | PASS | Owned immutable original key/ID/current/bounded history, source/actor/clock/fingerprint/predecessor proof, atomic outcomes and conversions, native lost-ack recovery and retraction. |

## Separate acceptance still open

Production migrations/configuration/credentials and operator execution of live
providers have not been activated. Real deliveries, authenticated external evidence,
device/settlement acceptance and large-history/load behavior are not claimed. Provider
acceptance never becomes delivery or causal lift. Conversion rate/ROAS remain null;
explicit declared links are not all sales or complete campaign history. Verification
refuses conversion chains above1000 events; bounded pages do not bound every source
proof read. Arbitrary administrator SQL is not made cryptographically authentic.

The full26-phase objective remains ACTIVE. Phase14 Revenue Guardian is next;
remaining production/physical acceptance is tracked separately and is not silently
converted into a functional pass for the whole application.
