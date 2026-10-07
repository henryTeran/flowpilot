# Opt-in marketing API transports

`transports.bind` creates a worker binding for an exact configured live Account and
a typed Credential supplied by a trusted server resolver. It does not activate a
daemon, install credentials or change account configuration. Built-in adapters
refuse test-mode accounts; tests inject simulated wire responses for live-mode
contract coverage without making external API calls. No live acceptance claimed.

The HTTPS client uses fixed provider hosts, certificate and hostname verification,
TLS 1.2 minimum, no redirects/proxies/automatic retries, a default 10-second caller
deadline (maximum 30) and 64 KiB request/response bounds. Expired calls close the
socket and guard against a late POST after slow connection/DNS completion. A DNS
thread may remain until the resolver returns; bytes already sent cannot be retracted.
DNS behavior/resource bounds still require deployed acceptance. Response JSON refuses
duplicate keys, nonstandard numbers, non-object and oversized payloads. Credentials
and response bodies are excluded from repr; transport failures expose generic text.

## Resend email

Use provider `resend`, channel `email`, a server credential label as account_id and
the exact verified From value as sender_id. Credential contains the API key. POST
`https://api.resend.com/emails` sends one exact recipient, approved subject and plain
text body. A deterministic scoped key is included; Resend retains idempotency keys
for 24 hours. The worker never uses another POST as reconciliation. Acceptance
requires a valid returned email UUID. A trusted existing reference permits GET with
exact ID/from/to/subject/text comparison; otherwise outcome stays unknown.

Sources checked 2026-10-07: [send](https://resend.com/docs/api-reference/emails/send-email),
[retrieve](https://resend.com/docs/api-reference/emails/retrieve-email),
[errors](https://resend.com/docs/api-reference/errors).

## Twilio SMS

Use provider `twilio`, channel `sms`, the exact AC account SID as account_id and
configured From sender_id. Credential contains that account's Auth Token. HTTP Basic
authentication and the account-scoped Messages endpoint send exact From/To/Body as
form fields. Acceptance requires a valid SM SID and matching account/sender/destination/
literal body in the response. A trusted existing SID permits GET of that scoped
message; mismatch or absence remains unknown. No SMS resubmission during recovery.

Sources: [Message resource](https://www.twilio.com/docs/messaging/api/message-resource),
[response contracts](https://www.twilio.com/docs/usage/twilios-response).

## Firebase Cloud Messaging

Use provider `fcm`, channel `push`, project ID as account_id and sender_id, plus the
declared application binding. Credential contains an OAuth access token; acquisition,
expiry checks and refresh belong to trusted deployment infrastructure outside the
worker's local resolver. POST messages:send contains the explicit device token and
literal approved notification body. Acceptance requires a same-project message name.
No read-by-operation reconciliation endpoint is implemented: unknown remains unknown,
and any known reference must retain the exact project. No automatic retry.

Sources: [send](https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages/send),
[message](https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages),
[errors](https://firebase.google.com/docs/cloud-messaging/error-codes?hl=en).

Only recognized vendor refusal envelopes become rejected observations. Redirects,
conflicts, rate limits, server errors, unrecognized envelopes and unmatched success
references remain unknown. Acceptance means submission acceptance, never confirmed
delivery. GET reconciliation uses a reference already authoritatively bound to the
stored intent by trusted server evidence; matching recipient/body alone cannot create
that binding. Authenticated callbacks/evidence and operator uncertainty resolution
remain required, particularly when the initial provider reference was lost.
