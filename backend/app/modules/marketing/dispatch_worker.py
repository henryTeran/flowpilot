"""One durable dispatch decision; adapters and invocation are trusted internal inputs.

The first decision is serialized under the institute lock and committed before I/O.
Every existing uncertain outcome takes reconciliation only, even after a crash before
submission. Provider I/O never holds the institute transaction open. The decision
clock is a linearization point, not a promise to retract bytes after that decision.
"""
from dataclasses import dataclass, field
from typing import Literal
from sqlalchemy import select, func
from app.modules.crm.metrics import Fact
from app.modules.crm.segments import RegisteredCustomerFact
from app.modules.marketing import dispatch_intents, dispatch_outcomes, provider, campaign_originals, contact_originals, contacts
from app.modules.marketing.models import DispatchOutcome
from app.shared.exceptions import business_error
from app.shared.ids import new_id
from app.shared.time import utcnow, explicit_utc_instant

@dataclass(frozen=True)
class Binding:
    account: provider.Account
    adapter: provider.MarketingProvider = field(repr=False)

class Execution(Fact):
    operation: Literal["submit_observed", "reconcile_observed", "terminal", "uncertain"]
    outcome: dispatch_outcomes.Original

def fresh_decision(db, institute, intent, at):
    saved = intent.submission.eligibility
    campaign = campaign_originals.current(db, institute, intent.request.campaign_id)
    contact = contact_originals.current(db, institute, intent.request.customer_id)
    customer = contact_originals.owned(db, institute, intent.request.customer_id)
    registered = RegisteredCustomerFact(institute_id=institute, customer_id=intent.request.customer_id, created_at=explicit_utc_instant(customer.created_at))
    if (campaign is None or campaign.revision.state != "SEND"
            or campaign.revision.previous_id != saved.campaign.id
            or campaign.revision.content != saved.campaign.content
            or campaign.revision.created_at > at
            or campaign_originals.require(db, institute, saved.campaign.id).revision != saved.campaign
            or contact != saved.original or registered != saved.customer):
        raise business_error("Dispatch sources changed after preparation")
    if not contacts.evaluate(registered, saved.campaign, contact, at).eligible_by_current_declaration:
        raise business_error("Current recipient does not permit first dispatch decision")

def run(session_factory, institute, intent_id, actor, resolve):
    """Resolve must be a local, trusted configured-account adapter lookup, without I/O.

    No public endpoint invokes this function. Credentials and bounded adapter I/O
    belong to deployment configuration. Unknown never authorizes automatic resubmit.
    """
    if not isinstance(actor, str) or not actor or actor != actor.strip() or len(actor) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in actor):
        raise business_error("Exact trusted worker actor required")
    with session_factory() as db:
        intent = dispatch_intents.require(db, institute, intent_id)
        previous = dispatch_outcomes.current(db, institute, intent_id)
        if previous is not None and previous.request.result.status != "unknown":
            return Execution(operation="terminal", outcome=previous)
        account = dispatch_intents.configured(institute, intent.submission.account.channel, intent.submission.account.account_id)
        if account != intent.submission.account: raise business_error("Configured account changed after preparation")
        binding = resolve(account)
        if not isinstance(binding, Binding) or provider.Account.model_validate(binding.account.model_dump()) != account or not isinstance(binding.adapter, provider.MarketingProvider):
            raise business_error("Adapter does not bind the exact configured account")
        first = previous is None
        if first:
            count = db.scalar(select(func.count()).select_from(DispatchOutcome).where(DispatchOutcome.institute_id == institute, DispatchOutcome.intent_id == intent_id))
            if count: raise business_error("Retained outcomes have no current pointer; submission refused")
            at = utcnow(); fresh_decision(db, institute, intent, at)
            marker = provider.Result(account=account, idempotency_key=intent.submission.idempotency_key, request_fingerprint=intent.request_fingerprint,
                status="unknown", provider_message_id=None, observed_at=at)
            previous = dispatch_outcomes.append(db, institute, dispatch_outcomes.Request(intent_id=intent_id, expected_previous_id=None, result=marker,
                reason="Durable first submission decision; outcome remains unknown", idempotency_key="first-decision:" + intent_id), actor)
        else:
            # Release the read transaction/owned lock before any provider call.
            db.commit()
    try:
        result = binding.adapter.submit(intent.submission) if first else binding.adapter.reconcile(intent.submission)
        result = provider.validate_result(intent.submission, result)
    except Exception:
        # Includes timeouts, malformed responses and mismatched provider references.
        # The durable unknown is retained; exception text may contain credentials.
        return Execution(operation="uncertain", outcome=previous)
    with session_factory() as db:
        current = dispatch_outcomes.current(db, institute, intent_id)
        if current is None: raise business_error("Dispatch decision disappeared after provider I/O")
        if current.request.result.status != "unknown":
            comparable = lambda r: r.model_dump(exclude={"observed_at"})
            if comparable(current.request.result) != comparable(result): raise business_error("Provider result conflicts with retained terminal observation")
            return Execution(operation="terminal", outcome=current)
        retained = dispatch_outcomes.append(db, institute, dispatch_outcomes.Request(intent_id=intent_id, expected_previous_id=current.id, result=result,
            reason="Trusted adapter submission observation" if first else "Trusted adapter reconciliation observation", idempotency_key=new_id("outcome_observation")), actor)
        return Execution(operation="submit_observed" if first else "reconcile_observed", outcome=retained)
