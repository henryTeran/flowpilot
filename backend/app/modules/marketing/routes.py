from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.marketing import models as marketing_models  # noqa: F401
from app.modules.marketing import audiences, audience_originals, templates, campaign_originals, catalogs, contacts, contact_originals, recipient_observations
router=APIRouter(prefix="/marketing/institutes/{institute_id}",tags=["marketing"])
def manager(institute_id:str,user=Depends(require_ticket_manager)):
    if user.get("institute_id")!=institute_id or user.get("role")!="responsable_institut":raise HTTPException(403,"Permission insuffisante")
    return user
@router.post("/audience-observations",response_model=audiences.Page|audiences.ContactPage)
def observe(institute_id:str,payload:audiences.Selection|audiences.ContactSelection,user=Depends(manager),db:Session=Depends(get_db)):
    return audiences.read_contacts(db,institute_id,payload) if isinstance(payload,audiences.ContactSelection) else audiences.read(db,institute_id,payload)

@router.post("/audience-captures",response_model=audience_originals.Original)
def capture(institute_id:str,payload:audience_originals.Request|audience_originals.ContactRequest,user=Depends(manager),db:Session=Depends(get_db)):
    return audience_originals.create(db,institute_id,payload,user.get("sub"))
@router.get("/audience-captures/original/{key}",response_model=audience_originals.Original|None)
def capture_original(institute_id:str,key:str,user=Depends(manager),db:Session=Depends(get_db)):
    return audience_originals.original(db,institute_id,key)
@router.get("/audience-captures/{identifier}",response_model=audience_originals.Original)
def capture_by_id(institute_id:str,identifier:str,user=Depends(manager),db:Session=Depends(get_db)):
    return audience_originals.require(db,institute_id,identifier)
@router.get("/audience-captures/{identifier}/pages/{index}",response_model=audience_originals.RetainedPage)
def capture_page(institute_id:str,identifier:str,index:int,user=Depends(manager),db:Session=Depends(get_db)):
    return audience_originals.page(db,institute_id,identifier,index)

@router.post("/templates",response_model=templates.Original)
def template_create(institute_id:str,payload:templates.Request,user=Depends(manager),db:Session=Depends(get_db)):
    return templates.create(db,institute_id,payload,user.get("sub"))
@router.get("/templates/original/{key}",response_model=templates.Original|None)
def template_original(institute_id:str,key:str,user=Depends(manager),db:Session=Depends(get_db)):
    return templates.original(db,institute_id,key)
@router.get("/templates/{identifier}",response_model=templates.Original)
def template_by_id(institute_id:str,identifier:str,user=Depends(manager),db:Session=Depends(get_db)):
    return templates.require(db,institute_id,identifier)
@router.get("/templates/{template_id}/current",response_model=templates.Original|None)
def template_current(institute_id:str,template_id:str,user=Depends(manager),db:Session=Depends(get_db)):
    return templates.current(db,institute_id,template_id)

@router.post("/campaigns",response_model=campaign_originals.Original)
def campaign_execute(institute_id:str,payload:campaign_originals.Request,user=Depends(manager),db:Session=Depends(get_db)):
    return campaign_originals.execute(db,institute_id,payload,user.get("sub"))
@router.get("/campaigns/original/{key}",response_model=campaign_originals.Original|None)
def campaign_original(institute_id:str,key:str,user=Depends(manager),db:Session=Depends(get_db)):
    return campaign_originals.original(db,institute_id,key)
@router.get("/campaigns/{identifier}",response_model=campaign_originals.Original)
def campaign_by_id(institute_id:str,identifier:str,user=Depends(manager),db:Session=Depends(get_db)):
    return campaign_originals.require(db,institute_id,identifier)
@router.get("/campaigns/{campaign_id}/current",response_model=campaign_originals.Original|None)
def campaign_current(institute_id:str,campaign_id:str,user=Depends(manager),db:Session=Depends(get_db)):
    return campaign_originals.current(db,institute_id,campaign_id)

@router.get("/campaigns/{campaign_id}/audit",response_model=campaign_originals.AuditPage)
def campaign_audit(institute_id:str,campaign_id:str,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50),user=Depends(manager),db:Session=Depends(get_db)):
    return campaign_originals.audit(db,institute_id,campaign_id,offset,limit)

@router.get("/audience-captures",response_model=catalogs.Page[audience_originals.Original])
def audience_catalog(institute_id:str,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50),user=Depends(manager),db:Session=Depends(get_db)):
    return catalogs.audiences(db,institute_id,offset,limit)
@router.get("/templates",response_model=catalogs.Page[templates.Original])
def template_catalog(institute_id:str,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50),user=Depends(manager),db:Session=Depends(get_db)):
    return catalogs.templates_current(db,institute_id,offset,limit)
@router.get("/campaigns",response_model=catalogs.Page[campaign_originals.Original])
def campaign_catalog(institute_id:str,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50),user=Depends(manager),db:Session=Depends(get_db)):
    return catalogs.campaigns_current(db,institute_id,offset,limit)

@router.post("/customers/{customer_id}/contact-declarations", response_model=contacts.Original)
def contact_create(institute_id: str, customer_id: str, payload: contacts.Request, user=Depends(manager), db: Session=Depends(get_db)):
    return contact_originals.create(db, institute_id, customer_id, payload, user.get("sub"))

@router.post("/customers/{customer_id}/contact-declarations/validate", response_model=contacts.Request)
def contact_validate(institute_id: str, customer_id: str, payload: contacts.Request, user=Depends(manager), db: Session=Depends(get_db)):
    contact_originals.owned(db, institute_id, customer_id)
    if (payload.declaration.institute_id, payload.declaration.customer_id) != (institute_id, customer_id):
        raise HTTPException(400, "La déclaration doit correspondre à la cliente sélectionnée")
    return payload

@router.get("/customers/{customer_id}/contact-declarations/original/{key}", response_model=contacts.Original | None)
def contact_original(institute_id: str, customer_id: str, key: str, user=Depends(manager), db: Session=Depends(get_db)):
    return contact_originals.original(db, institute_id, customer_id, key)

@router.get("/customers/{customer_id}/contact-declarations/current", response_model=contacts.Original | None)
def contact_current(institute_id: str, customer_id: str, user=Depends(manager), db: Session=Depends(get_db)):
    return contact_originals.current(db, institute_id, customer_id)

@router.get("/customers/{customer_id}/contact-declarations/{identifier}", response_model=contacts.Original)
def contact_by_id(institute_id: str, customer_id: str, identifier: str, user=Depends(manager), db: Session=Depends(get_db)):
    return contact_originals.require(db, institute_id, customer_id, identifier)

@router.get("/campaigns/{campaign_id}/recipient-observations", response_model=recipient_observations.Page)
def recipient_page(institute_id: str, campaign_id: str, expected_revision_id: str = Query(..., min_length=1, max_length=80),
                   offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50), user=Depends(manager), db: Session=Depends(get_db)):
    return recipient_observations.read(db, institute_id, campaign_id, expected_revision_id, offset, limit)
