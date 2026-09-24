import redis
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.db.models import Conversation, User


def redis_client():
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def own_conversation(db: Session, user: User, conversation_id: int) -> Conversation:
    row = db.get(Conversation, conversation_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=403, detail="不能访问这个对话")
    return row
