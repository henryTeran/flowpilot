import { certificationDate, certificationInstant as instant } from "./certification-utils";
export type CommunicationDeclaration = { channel: "email" | "sms"; purpose: "service_follow_up" | "marketing";
  permission: "unknown" | "granted" | "refused"; evidence: string | null };
export type LifecycleDeclaration = { institute_id: string; customer_id: string; birthday: { month: number; day: number } | null;
  birthday_evidence: string | null; communications: CommunicationDeclaration[] };
export type LifecycleTerms = { declaration: LifecycleDeclaration; previous_id: string | null; reason: string; idempotency_key: string };
export type LifecycleOriginal = LifecycleTerms & { id: string; institute_id: string; customer_id: string; actor_id: string; created_at: string };
export type BirthdayPolicy = { institute_id: string; timezone: string; leap_day: "february_28" | "march_1" | "leap_year_only" };
export type BirthdayPolicyTerms = { policy: BirthdayPolicy; previous_policy_id: string | null; reason: string; idempotency_key: string };
export type BirthdayPolicyOriginal = BirthdayPolicyTerms & { id: string; institute_id: string; actor_id: string; created_at: string };
const text = (v: unknown,max=80): v is string => typeof v === "string" && !!v && v.trim() === v && v.length <= max;
const evidence = (v: unknown): v is string => text(v,240) && v.length >= 3;
export function validLifecycleDeclaration(v: unknown,institute: string,customer: string): v is LifecycleDeclaration {
  const d = v as LifecycleDeclaration;
  if (!d || !text(d.institute_id) || !text(d.customer_id) || d.institute_id !== institute || d.customer_id !== customer
    || !Array.isArray(d.communications) || d.communications.length !== 4) return false;
  if (d.birthday === null) { if (d.birthday_evidence !== null) return false; }
  else if (!d.birthday || !Number.isInteger(d.birthday.month) || !Number.isInteger(d.birthday.day)
    || !certificationDate(`2000-${String(d.birthday.month).padStart(2,"0")}-${String(d.birthday.day).padStart(2,"0")}`) || !evidence(d.birthday_evidence)) return false;
  const dimensions = new Set<string>();
  for (const c of d.communications) {
    if (!c || !["email","sms"].includes(c.channel) || !["service_follow_up","marketing"].includes(c.purpose)
      || !["unknown","granted","refused"].includes(c.permission)
      || (c.permission === "unknown" ? c.evidence !== null : !evidence(c.evidence))) return false;
    dimensions.add(`${c.channel}:${c.purpose}`);
  }
  return dimensions.size === 4;
}
export function validLifecycleTerms(v: unknown,institute: string,customer: string): v is LifecycleTerms {
  const t = v as LifecycleTerms;
  return !!t && validLifecycleDeclaration(t.declaration,institute,customer) && (t.previous_id === null || text(t.previous_id))
    && evidence(t.reason) && text(t.idempotency_key,120);
}
export function validLifecycleOriginal(v: unknown,institute: string,customer: string): v is LifecycleOriginal {
  const r = v as LifecycleOriginal;
  return validLifecycleTerms(r,institute,customer) && text(r.id) && r.institute_id === institute && r.customer_id === customer
    && r.previous_id !== r.id && text(r.actor_id,160) && instant(r.created_at) !== undefined;
}
export function sameLifecycleDeclaration(a: LifecycleDeclaration,b: LifecycleDeclaration): boolean {
  return validLifecycleDeclaration(a,a?.institute_id,a?.customer_id) && validLifecycleDeclaration(b,a.institute_id,a.customer_id)
    && (a.birthday === null ? b.birthday === null : b.birthday?.month === a.birthday.month && b.birthday.day === a.birthday.day)
    && a.birthday_evidence === b.birthday_evidence && a.communications.every((c,i) => {
      const other = b.communications[i]; return c.channel === other.channel && c.purpose === other.purpose && c.permission === other.permission && c.evidence === other.evidence;
    });
}
export function matchesLifecycleReceipt(r: LifecycleOriginal,t: LifecycleTerms,actor: string): boolean {
  return validLifecycleOriginal(r,r?.institute_id,r?.customer_id) && validLifecycleTerms(t,r.institute_id,r.customer_id)
    && r.actor_id === actor && sameLifecycleDeclaration(r.declaration,t.declaration) && r.previous_id === t.previous_id
    && r.reason === t.reason && r.idempotency_key === t.idempotency_key;
}
export function sameLifecycleOriginal(a: LifecycleOriginal,b: LifecycleOriginal): boolean {
  return validLifecycleOriginal(a,a?.institute_id,a?.customer_id) && validLifecycleOriginal(b,a.institute_id,a.customer_id)
    && a.id === b.id && matchesLifecycleReceipt(a,b,b.actor_id) && instant(a.created_at) === instant(b.created_at);
}
export function validBirthdayPolicy(v: unknown,institute: string): v is BirthdayPolicy {
  const p = v as BirthdayPolicy;
  if (!p || !text(p.institute_id) || p.institute_id !== institute || !text(p.timezone,64)
    || !["february_28","march_1","leap_year_only"].includes(p.leap_day)) return false;
  // Intl also accepts numeric-offset zones in some runtimes; the API requires a named ZoneInfo zone.
  if (/^[+-]/.test(p.timezone)) return false;
  try { new Intl.DateTimeFormat("en-US",{ timeZone: p.timezone }).format(new Date(0)); return true; } catch { return false; }
}
export function validBirthdayPolicyTerms(v: unknown,institute: string): v is BirthdayPolicyTerms {
  const t = v as BirthdayPolicyTerms;
  return !!t && validBirthdayPolicy(t.policy,institute) && (t.previous_policy_id === null || text(t.previous_policy_id))
    && evidence(t.reason) && text(t.idempotency_key,120);
}
export function validBirthdayPolicyOriginal(v: unknown,institute: string): v is BirthdayPolicyOriginal {
  const r = v as BirthdayPolicyOriginal;
  return validBirthdayPolicyTerms(r,institute) && text(r.id) && r.institute_id === institute && r.previous_policy_id !== r.id
    && text(r.actor_id,160) && instant(r.created_at) !== undefined;
}
export function sameBirthdayPolicy(a: BirthdayPolicy,b: BirthdayPolicy): boolean {
  return validBirthdayPolicy(a,a?.institute_id) && validBirthdayPolicy(b,a.institute_id) && a.timezone === b.timezone && a.leap_day === b.leap_day;
}
export function matchesBirthdayPolicyReceipt(r: BirthdayPolicyOriginal,t: BirthdayPolicyTerms,actor: string): boolean {
  return validBirthdayPolicyOriginal(r,r?.institute_id) && validBirthdayPolicyTerms(t,r.institute_id) && r.actor_id === actor
    && sameBirthdayPolicy(r.policy,t.policy) && r.previous_policy_id === t.previous_policy_id && r.reason === t.reason && r.idempotency_key === t.idempotency_key;
}
export function sameBirthdayPolicyOriginal(a: BirthdayPolicyOriginal,b: BirthdayPolicyOriginal): boolean {
  return validBirthdayPolicyOriginal(a,a?.institute_id) && validBirthdayPolicyOriginal(b,a.institute_id)
    && a.id === b.id && matchesBirthdayPolicyReceipt(a,b,b.actor_id) && instant(a.created_at) === instant(b.created_at);
}
type CustomerFact = { institute_id: string; customer_id: string; created_at: string };
export type BirthdayObservation = { basis: "declared_birthday_local_calendar"; declaration: LifecycleDeclaration; policy: BirthdayPolicy;
  customer: CustomerFact; capture: { institute_id: string; customer_id: string; captured_at: string }; local_date: string;
  anniversary_on: string | null; due: boolean; reason: "birthday_unknown" | "absent_in_calendar_year" | "not_today" | "birthday_today";
  occurrence_start: string | null; occurrence_end: string | null; external_message_sent: false; delivery_authorized: false };
export type LifecycleRead = { institute_id: string; customer_id: string; captured_at: string; customer: CustomerFact;
  original: LifecycleOriginal | null; calendar_original: BirthdayPolicyOriginal | null; birthday: BirthdayObservation | null;
  unavailable_reason: "declaration_absent" | "calendar_absent" | "future_declaration" | "future_calendar" | "future_registration" | null;
  external_message_sent: false; delivery_authorized: false };
function civilDate(ms: number,formatter: Intl.DateTimeFormat): string | undefined {
  const parts = Object.fromEntries(formatter.formatToParts(new Date(ms)).map(p => [p.type,p.value]));
  if (parts.era !== "AD") return;
  const date = `${parts.year.padStart(4,"0")}-${parts.month}-${parts.day}`;
  return certificationDate(date) ? date : undefined;
}
function civilBounds(date: string,formatter: Intl.DateTimeFormat): [bigint,bigint] | undefined {
  const centre = Date.parse(date+"T00:00:00Z"), next = new Date(centre+86400000).toISOString().slice(0,10);
  if (!certificationDate(next)) return;
  function boundary(target: string): bigint | undefined {
    let lo = Math.max(-62135596800000,centre-172800000), hi = Math.min(253402300799999,centre+259200000);
    const first = civilDate(lo,formatter), last = civilDate(hi,formatter);
    if (first === undefined || last === undefined || last < target) return;
    // At the minimum supported instant, do not silently truncate a local day that began in year zero.
    if (first >= target) return first === target && formatter.resolvedOptions().timeZone === "UTC" ? BigInt(lo)*1000n : undefined;
    while (hi-lo > 1) {
      const mid = lo+Math.floor((hi-lo)/2), value = civilDate(mid,formatter);
      if (value === undefined) return;
      if (value >= target) hi = mid; else lo = mid;
    }
    return BigInt(hi)*1000n;
  }
  const start = boundary(date), end = boundary(next);
  return start !== undefined && end !== undefined && start < end ? [start,end] : undefined;
}
export function validLifecycleRead(v: unknown,institute: string,customer: string): v is LifecycleRead {
  const r = v as LifecycleRead, captured = instant(r?.captured_at), registered = instant(r?.customer?.created_at);
  if (!r || r.institute_id !== institute || r.customer_id !== customer || captured === undefined || registered === undefined
    || r.customer.institute_id !== institute || r.customer.customer_id !== customer || r.external_message_sent !== false || r.delivery_authorized !== false
    || r.original !== null && !validLifecycleOriginal(r.original,institute,customer)
    || r.calendar_original !== null && !validBirthdayPolicyOriginal(r.calendar_original,institute)) return false;
  const original = r.original, calendar = r.calendar_original;
  const unavailable = original === null ? "declaration_absent" : calendar === null ? "calendar_absent"
    : instant(original.created_at)! > captured ? "future_declaration" : instant(calendar.created_at)! > captured ? "future_calendar"
    : registered > captured ? "future_registration" : null;
  if (r.unavailable_reason !== unavailable) return false;
  if (unavailable) return r.birthday === null;
  const b = r.birthday;
  if (!b || !original || !calendar || b.basis !== "declared_birthday_local_calendar" || b.external_message_sent !== false || b.delivery_authorized !== false
    || !sameLifecycleDeclaration(b.declaration,original.declaration) || !sameBirthdayPolicy(b.policy,calendar.policy)
    || !b.customer || b.customer.institute_id !== institute || b.customer.customer_id !== customer || instant(b.customer.created_at) !== registered
    || !b.capture || b.capture.institute_id !== institute || b.capture.customer_id !== customer || instant(b.capture.captured_at) !== captured) return false;
  try {
    const formatter = new Intl.DateTimeFormat("en-US-u-ca-gregory-nu-latn",{ timeZone: calendar.policy.timezone,year: "numeric",month: "2-digit",day: "2-digit",era: "short" });
    const ms = captured/1000n-(captured < 0n && captured%1000n !== 0n ? 1n : 0n), today = civilDate(Number(ms),formatter);
    if (today === undefined || b.local_date !== today) return false;
    const declared = original.declaration.birthday, year = today.slice(0,4);
    let anniversary: string | null = null, reason: BirthdayObservation["reason"] = "birthday_unknown";
    if (declared) {
      anniversary = `${year}-${String(declared.month).padStart(2,"0")}-${String(declared.day).padStart(2,"0")}`;
      if (!certificationDate(anniversary)) anniversary = calendar.policy.leap_day === "february_28" ? `${year}-02-28`
        : calendar.policy.leap_day === "march_1" ? `${year}-03-01` : null;
      reason = anniversary === null ? "absent_in_calendar_year" : anniversary === today ? "birthday_today" : "not_today";
    }
    if (b.anniversary_on !== anniversary || b.reason !== reason || b.due !== (reason === "birthday_today")) return false;
    if (anniversary === null) return b.occurrence_start === null && b.occurrence_end === null;
    const bounds = civilBounds(anniversary,formatter);
    return !!bounds && instant(b.occurrence_start) === bounds[0] && instant(b.occurrence_end) === bounds[1];
  } catch { return false; }
}
