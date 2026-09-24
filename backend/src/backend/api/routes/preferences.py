from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.api.schemas import PrefsBody
from backend.db.session import get_db
from backend.services.auth import current_user
from backend.services.memory import get_prefs, save_prefs

router = APIRouter()


@router.get("/api/preferences/current")
def get_current_preferences(request: Request, db: Session = Depends(get_db)):
    user = current_user(db, request)
    return get_prefs(db, user.id)


@router.put("/api/preferences/save")
def save_current_preferences(body: PrefsBody, request: Request, db: Session = Depends(get_db)):
    user = current_user(db, request)
    return save_prefs(db, user.id, body.model_dump())
