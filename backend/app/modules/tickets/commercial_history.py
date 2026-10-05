"""Ticket-line protection independent of the current checkout beneficiary."""
from sqlalchemy import select, union
from app.modules.commerce.models import PackageRedemption
from app.modules.memberships.models import MembershipBenefit
from app.modules.loyalty.models import LoyaltyRedemption


def protected_line_ids(db, institute_id, line_ids):
    if not line_ids:
        return set()
    # Include reversed facts: reversal restores rights/prices, never erases history.
    statements = [select(model.ticket_line_id).where(model.institute_id == institute_id,
                  model.ticket_line_id.in_(line_ids))
                  for model in (PackageRedemption, MembershipBenefit, LoyaltyRedemption)]
    return set(db.scalars(union(*statements)))
