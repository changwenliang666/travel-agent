import json
import queue
import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.api.deps import own_conversation, redis_client
from backend.api.schemas import MessageBody
from backend.db.models import Conversation, Message, TripPlan, User
from backend.db.session import SessionLocal, get_db
from backend.llm.gateway import ModelCallError
from backend.services.auth import current_user
from backend.services.turn import run_turn, update_prefs_after_reply

router = APIRouter()


def sse(event: str, data) -> str:
    return "event: " + event + "\ndata: " + json.dumps(data, ensure_ascii=False) + "\n\n"


@router.post("/api/conversations/create")
def create_conversation(request: Request, db: Session = Depends(get_db)):
    user = current_user(db, request)
    row = Conversation(user_id=user.id, title="新对话", slots_json="{}")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "title": row.title}


@router.get("/api/conversations/list")
def list_conversations(request: Request, db: Session = Depends(get_db)):
    user = current_user(db, request)
    rows = db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.id.desc()).all()
    return [{"id": row.id, "title": row.title} for row in rows]


@router.get("/api/conversations/{conversation_id}/detail")
def get_conversation_detail(conversation_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(db, request)
    row = own_conversation(db, user, conversation_id)
    messages = db.query(Message).filter(Message.conversation_id == row.id).order_by(Message.id.asc()).all()
    plan_row = db.query(TripPlan).filter(TripPlan.conversation_id == row.id).one_or_none()
    plan = json.loads(plan_row.plan_json) if plan_row else None
    return {
        "id": row.id,
        "title": row.title,
        "messages": [{"role": item.role, "content": item.content} for item in messages],
        "plan": plan,
    }


@router.post("/api/conversations/{conversation_id}/messages/send")
def send_conversation_message(conversation_id: int, body: MessageBody, request: Request, db: Session = Depends(get_db)):
    user = current_user(db, request)
    own_conversation(db, user, conversation_id)
    events = queue.Queue()

    def on_progress(text: str):
        if text:
            events.put(("progress", {"text": text}))

    def on_delta(text: str):
        events.put(("delta", {"text": text}))

    def worker():
        session = SessionLocal()
        try:
            account = session.get(User, user.id)
            conversation = session.get(Conversation, conversation_id)
            result = run_turn(session, redis_client(), account, conversation, body.text, on_progress, on_delta)
            events.put(("plan", result.get("plan")))
            events.put(("done", {"trace_id": result["trace_id"], "reply": result["reply"]}))
            try:
                update_prefs_after_reply(session, result["deps"].llm, account.id, body.text, result["reply"])
            except Exception:
                pass
        except ModelCallError as exc:
            events.put(("error", {"message": str(exc)}))
        except Exception as exc:
            events.put(("error", {"message": "处理失败: " + str(exc)}))
        finally:
            session.close()
            events.put(("end", None))

    threading.Thread(target=worker, daemon=True).start()

    def generate():
        while True:
            kind, payload = events.get()
            if kind == "end":
                break
            yield sse(kind, payload)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
