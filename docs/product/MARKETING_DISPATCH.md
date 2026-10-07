# Marketing dispatch preparation

The current implementation prepares one durable transport intent for an owned
customer and approved campaign revision. It performs no provider I/O and does not
mark the campaign SEND or establish recipient delivery. Trusted-worker outcome
retention is implemented; execution and delivery-event verification remain to be
implemented.

`MARKETING_ACCOUNTS_JSON` is a server-side account allowlist, empty by default.
Each entry is an exact `Account` with `institute_id`, `provider`, `account_id`,
`channel` (`email`, `sms`, `push`), `sender_id`, `mode` (`live`, `test`) and
`push_application` (required for Push, null otherwise). Duplicate account IDs
within an institute/channel invalidate the configuration. Keep credentials out
of this list. Listing an account permits preparation only; it does not configure
a transport adapter or prove provider/account ownership. Test mode facts cannot
be treated as live acceptance.

A signed institute manager can POST `/api/v1/marketing/institutes/{institute_id}/dispatch-intents`
with `campaign_id`, `expected_revision_id`, `customer_id`, `expected_contact_id`,
`account_id`, `reason` and `idempotency_key`. Actor comes from the signed session.
The service locks the institute, resolves an existing key first, then for a new
intent requires the exact current campaign and contact, an approved retained
customer, granted permission and declared channel destination at one aware clock.
Push application must match the server account. Current approval does not override
a withdrawal. There can be only one intent for a revision/customer; recovery must
use its original key rather than creating a new operation.

The receipt retains full transport terms, source originals, signed actor and a
canonical SHA-256 fingerprint. GET `dispatch-intents/original/{key}` and
`dispatch-intents/{identifier}` independently reread the owned original and its
historical campaign/contact sources. An identical request and actor can recover
the original after current sources or account configuration change. Historical
recovery does not authorize a later send: execution must recheck current sources
and account configuration before its first submission. An uncertain prior attempt
must be reconciled under the same stored operation key.

The schema migration `3fa0c198447b` adds intents, outcome originals and current
outcome pointers. Source/owner, replay and one-recipient constraints are enforced
in SQL. JSON semantics, APPROVE stage and current-source authority are enforced
by services. Any retained dispatch history blocks downgrade, including an intent
without a result. Offline downgrade cannot verify history and is refused. No
production migration or live provider acceptance is implied by repository tests.

The internal `dispatch_outcomes.append` entry point accepts trusted adapter
observations only. It validates the stored intent account/key/fingerprint, exact
current outcome predecessor, nonfuture retention and monotonic observation clocks.
An unknown result can be followed by another unknown or a terminal acceptance or
rejection; a known provider message reference cannot change. Terminal submission
outcomes cannot be replaced. Delivery events require separate evidence and cannot
be recorded as submission acceptance. Original-key recovery checks complete terms
and worker actor before consulting the current outcome or clock.

Managers can GET `dispatch-intents/{intent_id}/outcomes` with bounded `offset` and
`limit` (default 20, maximum 50), plus `outcomes/current`, `outcomes/original/{key}`
and `outcomes/{identifier}`. These routes cannot write provider results. The page
is an ordered bounded audit, not proof of the full predecessor chain outside the
page. Present predecessor cycles and incoherent predecessor transitions refuse.
