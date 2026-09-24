from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.schemas import LoginBody
from backend.db.session import get_db
from backend.services.auth import COOKIE, current_user, login as login_account, logout as logout_account

router = APIRouter()


@router.post("/api/auth/login")
def login_user(body: LoginBody, db: Session = Depends(get_db)):
    token = login_account(db, body.username, body.password)
    response = JSONResponse({"ok": True})
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", max_age=7 * 24 * 3600)
    return response


@router.post("/api/auth/logout")
def logout_user(request: Request, db: Session = Depends(get_db)):
    logout_account(db, request.cookies.get(COOKIE))
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE)
    return response


@router.get("/api/auth/me")
def get_current_user(request: Request, db: Session = Depends(get_db)):
    user = current_user(db, request)
    return {"id": user.id, "username": user.username, "role": user.role}
