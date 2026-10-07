from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.marketing import models as marketing_models  # noqa: F401
from app.modules.marketing import audiences, audience_originals, templates
router=APIRouter(prefix="/marketing/institutes/{institute_id}",tags=["marketing"])
def manager(institute_id:str,user=Depends(require_ticket_manager)):
    if user.get("institute_id")!=institute_id or user.get("role")!="responsable_institut":raise HTTPException(403,"Permission insuffisante")
    return user
@router.post("/audience-observations",response_model=audiences.Page)
def observe(institute_id:str,payload:audiences.Selection,user=Depends(manager),db:Session=Depends(get_db)):
    return audiences.read(db,institute_id,payload)

@router.post("/audience-captures",response_model=audience_originals.Original)
def capture(institute_id:str,payload:audience_originals.Request,user=Depends(manager),db:Session=Depends(get_db)):
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
