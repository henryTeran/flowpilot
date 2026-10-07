# Internal CRM recurring worker

The runner records internal processing receipts. It does not send email/SMS or
certify communication delivery authority. It is not started by API startup.
Production/physical acceptance remains open.

## Explicit launch

Run from `backend` with the API's database/security environment and dependencies.
Apply reviewed migrations separately before launching. The CLI checks the
database's Alembic revision against this checkout; it never creates or migrates
the application schema. Revision verification is a prerequisite, not a full
production-readiness audit.

Supply an existing signed institute-manager token through
`FLOWPILOT_CRM_WORKER_TOKEN`. Do not commit the token, pass it as a command-line
argument, or put it in the journal. Role, institute, actor and token validity are
checked initially and between pages. Expiry/actor changes stop the runner with
the pending journal retained. A replacement credential must retain the actor.

Choose an existing writable journal directory and explicitly choose the polling
interval in seconds. Example values below are illustrative, not installed
settings:

```powershell
python -m app.modules.crm.recurring_worker --enable --institute demo-institute-geneve --reason "Explicit internal worker operation" --interval-seconds 60 --state .\var\crm-worker.json
```

`--enable`, institute, reason, interval and state path are required. Add `--once`
to complete one scan and exit; a completed scan with failed customers exits 2.
Do not run the illustrative command against production without its normal
release/configuration acceptance. No service installation or production token
is supplied by this implementation.

## Stop and recovery

SIGINT/SIGTERM request a stop between bounded pages. An in-flight page finishes
its independent customer transactions. A forced stop can leave a page pending;
restart with the same journal and configuration. Durable customer keys recover
already committed receipts rather than process those occurrences twice.

The journal pins institute, actor, reason, interval, cycle key, cursor, failure
IDs, completion count and next due time. It contains no credential. Writes use
fsync and same-directory atomic replacement. OS file locks prevent two runners
using the same journal and release after process death. Corrupt journals or
changed owner/terms fail closed; they are not silently reset.

Each scan uses keyset pages of at most 50 registered customers. Each customer's
processor handles at most 20 freshly due events. Failure rolls back that
customer, is reported/logged without payload/credentials and permits other
customers to continue. Failed customers are attempted again on the next cycle.
Earlier IDs registered during a scan are also picked up on the next full scan.
This is a fresh scan, not an immutable whole-institute batch manifest.

The interval starts after scan completion. Later cycles get new keys; pending
pages retain their keys. Old processed occurrences remain terminal regardless
of the new cycle key. Separate journals can run concurrently; institute locks
and durable event states prevent duplicate processing, but service orchestration
and operational capacity still require deployment acceptance.
