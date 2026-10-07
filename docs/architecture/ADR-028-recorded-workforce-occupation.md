# ADR-028: Recorded workforce occupation over declared time

Status: scoped API implemented; native profile and acceptance remain open.

The employee/institute-day manager read combines actual completed walk-in
session instants and actual completed appointment instants. Planned slots,
planned durations, customer identity and cashier identity never supply missing
actual facts. Cancelled/planned/unstarted bookings are not occupation sources.
Missing-start appointment records are attributed to a day only through their
recorded finishing instant; completely unlocated execution facts cannot be
assigned a day from their planned slot.

One institute transaction lock covers the existing exact hours reading, source
count, diagnostics, unions, intersection and bounded source page. Source
identities retain session/appointment kind, ID, service, status and recorded
start/end. No customer names/phones are exposed. Missing starts/ends, reversed
or empty intervals, future ends and non-finalized records are explicit excluded
diagnostics. Active records with unknown ends are not closed at their planned
end; earlier open starts remain potentially relevant to later days.

Exact streaming half-open union arithmetic merges overlapping session and
appointment execution facts to avoid double counting. Its intersection with
the active completed declared-work union preserves breaks, microseconds and
institute-day clipping. Known busy time outside the recorded work union is
reported separately, never forced into the denominator. Duration strings retain
integer microseconds; the bounded source page does not limit global aggregates.
Endpoint streams use bounded chunks and constant aggregate memory without
per-source queries.

The optional ratio is explicitly occupation on recorded declared time. It is
unknown if the recorded hours denominator is absent/future or any candidate
execution source is incomplete, future, invalid or unfinalized. Otherwise
covered_us * 10000 // recorded_work_us produces integer basis points rounded
down; exact numerator/denominator remain available. complete_activity and the
hours complete_attendance flag are always false. Neither a zero recorded ratio
nor a nonzero partial ledger proves total real-world activity or attendance.

This read adds no schema and changes no planning, assignment, hours or financial
facts. SQLite/PostgreSQL fixtures verify hybrid-source overlap, microseconds,
outside-work time, unknown starts/ends and exclusions. Native integration,
physical/production acceptance, rebooking and commissions remain separate work.
