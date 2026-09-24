import hashlib
import os
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.db.models import SessionToken, User

COOKIE = "session"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split(":")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
    return digest.hex() == digest_hex


def seed_admin(db: Session) -> None:
    if db.query(User).count() > 0:
        return
    settings = get_settings()
    db.add(
        User(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
    )
    db.commit()


def login(db: Session, username: str, password: str) -> str:
    user = db.query(User).filter(User.username == username).one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码不正确")
    token = secrets.token_urlsafe(32)
    db.add(
        SessionToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
    )
    db.commit()
    return token


def logout(db: Session, token: str | None) -> None:
    if not token:
        return
    db.query(SessionToken).filter(SessionToken.token == token).delete()
    db.commit()


def current_user(db: Session, request: Request) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")
    row = db.query(SessionToken).filter(SessionToken.token == token).one_or_none()
    if row is None or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="请先登录")
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
