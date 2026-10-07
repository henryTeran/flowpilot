from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.marketing import audiences
router=APIRouter(prefix="/marketing/institutes/{institute_id}",tags=["marketing"])
def manager(institute_id:str,user=Depends(require_ticket_manager)):
    if user.get("institute_id")!=institute_id or user.get("role")!="responsable_institut":raise HTTPException(403,"Permission insuffisante")
    return user
@router.post("/audience-observations",response_model=audiences.Page)
def observe(institute_id:str,payload:audiences.Selection,user=Depends(manager),db:Session=Depends(get_db)):
    return audiences.read(db,institute_id,payload)
