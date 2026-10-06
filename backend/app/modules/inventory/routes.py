from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.inventory import service
from app.modules.inventory.models import StockMovement
from app.modules.inventory.schemas import ItemCreate, ItemRead, MovementCreate, MovementRead
from app.modules.inventory.schemas import RecipeCreate, RecipeRead
from app.modules.inventory.models import StockRecipe
from app.modules.inventory import recipes

router = APIRouter(prefix="/inventory/institutes/{institute_id}", tags=["inventory"])


def operator(institute_id: str, user=Depends(require_ticket_manager)):
    actor = user.get("sub")
    if user.get("institute_id") != institute_id or not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise HTTPException(403, "Institut et identite de l'operatrice requis")
    return user


def manager(user=Depends(operator)):
    if user["role"] != "responsable_institut":
        raise HTTPException(403, "Gestion de stock reservee a la responsable")
    return user


@router.get("/items", response_model=list[ItemRead])
def items(institute_id: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0, le=100000),
          user=Depends(operator), db: Session = Depends(get_db)):
    return service.list_items(db, institute_id, limit, offset)


@router.post("/items", response_model=ItemRead)
def create(institute_id: str, payload: ItemCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return service.create_item(db, institute_id, payload, user["sub"])


@router.get("/items/{item_id}", response_model=ItemRead)
def item(institute_id: str, item_id: str, user=Depends(operator), db: Session = Depends(get_db)):
    service.lock_institute(db, institute_id)
    row = service.require_item(db, institute_id, item_id)
    return service.read_item(row, service.balance_milli(db, institute_id, item_id))


@router.get("/items/{item_id}/movements", response_model=list[MovementRead])
def history(institute_id: str, item_id: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0, le=100000),
            user=Depends(operator), db: Session = Depends(get_db)):
    row = service.require_item(db, institute_id, item_id)
    moves = db.scalars(select(StockMovement).where(StockMovement.institute_id == institute_id,
        StockMovement.item_id == item_id).order_by(StockMovement.occurred_at, StockMovement.id).limit(limit).offset(offset))
    return [service.read_movement(move, row.unit) for move in moves]


@router.post("/items/{item_id}/movements", response_model=MovementRead)
def move(institute_id: str, item_id: str, payload: MovementCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return service.move(db, institute_id, item_id, payload, user["sub"])


@router.get("/services/{service_id}/recipe", response_model=RecipeRead | None)
def recipe(institute_id: str, service_id: str, user=Depends(operator), db: Session = Depends(get_db)):
    service.lock_institute(db, institute_id)
    recipes.require_service(db, service_id)
    row = recipes.current(db, institute_id, service_id)
    return recipes.snapshot(db, row) if row else None


@router.post("/services/{service_id}/recipes", response_model=RecipeRead)
def create_recipe(institute_id: str, service_id: str, payload: RecipeCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return recipes.create(db, institute_id, service_id, payload, user["sub"])


@router.get("/recipes/{recipe_id}", response_model=RecipeRead)
def original_recipe(institute_id: str, recipe_id: str, user=Depends(operator), db: Session = Depends(get_db)):
    row = db.scalar(select(StockRecipe).where(StockRecipe.institute_id == institute_id, StockRecipe.id == recipe_id))
    if row is None:
        from app.shared.exceptions import not_found
        raise not_found("Recette introuvable")
    return recipes.snapshot(db, row)


@router.get("/services/{service_id}/recipes", response_model=list[RecipeRead])
def recipe_history(institute_id: str, service_id: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0, le=100000),
                   user=Depends(operator), db: Session = Depends(get_db)):
    recipes.require_service(db, service_id)
    rows = db.scalars(select(StockRecipe).where(StockRecipe.institute_id == institute_id,
        StockRecipe.service_id == service_id).order_by(StockRecipe.revision.desc()).limit(limit).offset(offset)).all()
    return [recipes.snapshot(db, row) for row in rows]
