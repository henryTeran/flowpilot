"""Explicit customer declarations and calendar facts; no outbound delivery authority."""
from calendar import isleap
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field, StringConstraints, model_validator
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm.segments import RegisteredCustomerFact

Evidence = Annotated[str, StringConstraints(strip_whitespace=True,min_length=3,max_length=240)]


class BirthdayMonthDay(Fact):
    month: Annotated[int, Field(strict=True,ge=1,le=12)]
    day: Annotated[int, Field(strict=True,ge=1,le=31)]

    @model_validator(mode="after")
    def calendar_date(self):
        date(2000,self.month,self.day)  # Leap-year calendar permits explicitly declared February 29.
        return self


class CommunicationDeclaration(Fact):
    channel: Literal["email","sms"]
    purpose: Literal["service_follow_up","marketing"]
    permission: Literal["unknown","granted","refused"]
    evidence: Evidence | None

    @model_validator(mode="after")
    def explicit_evidence(self):
        if (self.permission == "unknown") != (self.evidence is None):
            raise ValueError("A recorded permission/refusal requires evidence; unknown must remain unevidenced")
        return self


class LifecycleDeclaration(Fact):
    institute_id: Identifier
    customer_id: Identifier
    birthday: BirthdayMonthDay | None
    birthday_evidence: Evidence | None
    communications: tuple[CommunicationDeclaration,...]

    @model_validator(mode="after")
    def complete_dimensions(self):
        if (self.birthday is None) != (self.birthday_evidence is None):
            raise ValueError("A birthday declaration requires evidence; absent birthday remains unknown")
        expected = {(channel,purpose) for channel in ("email","sms") for purpose in ("service_follow_up","marketing")}
        actual = [(r.channel,r.purpose) for r in self.communications]
        if len(actual) != 4 or set(actual) != expected:
            raise ValueError("Declare each communication channel/purpose exactly once")
        return self


class BirthdayCalendarPolicy(Fact):
    institute_id: Identifier
    timezone: Annotated[str, StringConstraints(min_length=1,max_length=64)]
    leap_day: Literal["february_28","march_1","leap_year_only"]

    @model_validator(mode="after")
    def named_zone(self):
        if self.timezone != self.timezone.strip():
            raise ValueError("An exact named timezone is required")
        try: ZoneInfo(self.timezone)
        except (ValueError,ZoneInfoNotFoundError) as error:
            raise ValueError("A known named timezone is required") from error
        return self


class BirthdayCapture(Fact):
    institute_id: Identifier
    customer_id: Identifier
    captured_at: AwareDatetime


class BirthdayObservation(Fact):
    basis: Literal["declared_birthday_local_calendar"] = "declared_birthday_local_calendar"
    declaration: LifecycleDeclaration
    policy: BirthdayCalendarPolicy
    customer: RegisteredCustomerFact
    capture: BirthdayCapture
    local_date: date
    anniversary_on: date | None
    due: bool
    reason: Literal["birthday_unknown","absent_in_calendar_year","not_today","birthday_today"]
    occurrence_start: AwareDatetime | None
    occurrence_end: AwareDatetime | None
    external_message_sent: Literal[False] = False
    delivery_authorized: Literal[False] = False


def observe_birthday(declaration: LifecycleDeclaration,policy: BirthdayCalendarPolicy,
                     customer: RegisteredCustomerFact,capture: BirthdayCapture) -> BirthdayObservation:
    try:
        captured_utc = capture.captured_at.astimezone(timezone.utc)
        registered_utc = customer.created_at.astimezone(timezone.utc)
    except (OverflowError,ValueError) as error:
        raise ValueError("Birthday source clocks lie outside the UTC calendar") from error
    if (declaration.institute_id != capture.institute_id or policy.institute_id != capture.institute_id
        or customer.institute_id != capture.institute_id or declaration.customer_id != capture.customer_id
        or customer.customer_id != capture.customer_id or registered_utc > captured_utc):
        raise ValueError("Registered customer, declaration, policy and capture scope/chronology must agree")
    zone = ZoneInfo(policy.timezone)
    try: today = capture.captured_at.astimezone(zone).date()
    except (OverflowError,ValueError) as error:
        raise ValueError("Birthday capture lies outside the named-zone calendar") from error
    birthday = declaration.birthday; anniversary = start = end = None
    reason = "birthday_unknown"
    if birthday:
        month,day = birthday.month,birthday.day
        if month == 2 and day == 29 and not isleap(today.year):
            if policy.leap_day == "february_28": month,day = 2,28
            elif policy.leap_day == "march_1": month,day = 3,1
            else: month = 0
        if month:
            anniversary = date(today.year,month,day)
            reason = "birthday_today" if anniversary == today else "not_today"
            # Civil midnight bounds, not a guessed fixed 24-hour duration.
            try:
                start = datetime.combine(anniversary,time(),zone).astimezone(timezone.utc)
                end = datetime.combine(anniversary+timedelta(days=1),time(),zone).astimezone(timezone.utc)
            except (OverflowError,ValueError) as error:
                raise ValueError("Birthday occurrence lies outside the supported calendar") from error
            if start >= end:
                raise ValueError("Birthday civil day has no representable positive occurrence")
        else: reason = "absent_in_calendar_year"
    return BirthdayObservation(declaration=declaration,policy=policy,customer=customer,capture=capture,
        local_date=today,anniversary_on=anniversary,due=reason=="birthday_today",reason=reason,
        occurrence_start=start,occurrence_end=end)
