from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError
from app.modules.marketing.campaigns import AudienceFact, CampaignContent, CampaignRevision, create, transition
NOW=datetime(2026,10,7,12,tzinfo=timezone.utc)
def content(origin="ai",channel="email"):
 return CampaignContent(institute_id="i",channel=channel,origin=origin,subject="Explicit subject" if channel=="email" else None,body="Explicit body",template_original_id=None,audience=AudienceFact(id="audience",institute_id="i",captured_at=NOW,customer_ids=("c",)))
@pytest.mark.parametrize("origin",["human","ai"])
@pytest.mark.parametrize("channel",["email","sms","push"])
def test_every_origin_channel_requires_exact_review_approval_chain(origin,channel):
 draft=create("r0","campaign",content(origin,channel),"manager","Explicit draft",NOW)
 review=transition(draft,"r0","r1","review","reviewer","Explicit review",NOW,None)
 approved=transition(review,"r1","r2","approve","approver","Explicit approval",NOW,None)
 sent=transition(approved,"r2","r3","send","dispatcher","Explicit dispatch request",NOW,None)
 assert [r.state for r in (draft,review,approved,sent)]==["DRAFT","REVIEW","APPROVE","SEND"]
 assert sent.previous_id==approved.id and sent.reviewed_digest==sent.approved_digest
 assert not sent.delivery_authorized and not sent.external_message_sent
 with pytest.raises(ValueError):transition(draft,"r0","skip","send","actor","Cannot skip",NOW,None)
 with pytest.raises(ValueError):transition(sent,"r3","edit","edit","actor","Cannot edit sent",NOW,content())
def test_edit_content_or_audience_invalidates_review_and_approval():
 d=create("d","campaign",content(),"actor","Explicit draft",NOW)
 r=transition(d,"d","r","review","actor","Explicit review",NOW,None)
 a=transition(r,"r","a","approve","actor","Explicit approval",NOW,None)
 for c in [content().model_copy(update={"body":"Changed body"}),content().model_copy(update={"audience":AudienceFact(id="new",institute_id="i",captured_at=NOW,customer_ids=("other",))})]:
  edit=transition(a,"a","e","edit","actor","Explicit edit",NOW,c)
  assert edit.state=="DRAFT" and edit.reviewed_digest is edit.approved_digest is None
  with pytest.raises(ValueError):transition(edit,"e","s","send","actor","Requires review",NOW,None)
 with pytest.raises(ValueError):transition(r,"r","s","approve","actor","Content injection",NOW,content())
def test_scope_stale_revision_clock_and_mutated_approval_refused():
 d=create("d","campaign",content(),"actor","Explicit draft",NOW)
 for expected,identifier,at in [("stale","r",NOW),("d","d",NOW),("d","r",NOW-timedelta(microseconds=1))]:
  with pytest.raises(ValueError):transition(d,expected,identifier,"review","actor","Explicit review",at,None)
 with pytest.raises(ValidationError):CampaignContent(**{**content().model_dump(),"institute_id":"foreign"})
 with pytest.raises(ValidationError):AudienceFact(id="a",institute_id="i",captured_at=NOW,customer_ids=("c","c"))
 with pytest.raises(ValidationError):AudienceFact(id="a",institute_id="i",captured_at=NOW,customer_ids=())
 r=transition(d,"d","r","review","actor","Explicit review",NOW,None)
 with pytest.raises(ValidationError):transition(r.model_copy(update={"content":content().model_copy(update={"body":"Tampered"})}),"r","a","approve","actor","Explicit approval",NOW,None)

def test_edit_revalidates_nested_facts_and_future_audience_cannot_be_reviewed():
 d=create("d","campaign",content(),"actor","Explicit draft",NOW)
 bad=content().model_copy(update={"audience":content().audience.model_copy(update={"institute_id":"foreign"})})
 with pytest.raises(ValidationError):transition(d,"d","e","edit","actor","Explicit edit",NOW,bad)
 future=content().model_copy(update={"audience":content().audience.model_copy(update={"captured_at":NOW+timedelta(microseconds=1)})})
 with pytest.raises(ValidationError):create("d","campaign",future,"actor","Explicit draft",NOW)
 with pytest.raises(ValidationError):AudienceFact(id="a",institute_id="i",captured_at=NOW,customer_ids=(" c",))
