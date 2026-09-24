import json
from datetime import datetime

from backend.db.models import MemorySummary, Message, Preference

DEFAULT_PREFS = {"home_city": "", "pace": "", "budget": "", "diet": "", "early_start": False}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 2)


def get_prefs(db, user_id: int) -> dict:
    row = db.get(Preference, user_id)
    if row is None:
        return dict(DEFAULT_PREFS)
    data = json.loads(row.prefs_json or "{}")
    merged = dict(DEFAULT_PREFS)
    merged.update(data)
    return merged


def save_prefs(db, user_id: int, prefs: dict) -> dict:
    merged = dict(DEFAULT_PREFS)
    merged.update(prefs)
    row = db.get(Preference, user_id)
    if row is None:
        row = Preference(user_id=user_id, prefs_json=json.dumps(merged, ensure_ascii=False))
        db.add(row)
    else:
        row.prefs_json = json.dumps(merged, ensure_ascii=False)
    db.commit()
    return merged


def recent_messages(db, conversation_id: int, limit: int):
    rows = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.id.desc()).limit(limit).all()
    rows.reverse()
    return rows


def summary_text(db, conversation_id: int) -> str:
    row = db.get(MemorySummary, conversation_id)
    if row is None:
        return ""
    return row.summary or ""


def build_context(db, user_id: int, conversation_id: int, recent_turns: int) -> str:
    prefs = get_prefs(db, user_id)
    summary = summary_text(db, conversation_id)
    rows = recent_messages(db, conversation_id, recent_turns)
    lines = ["用户偏好：" + json.dumps(prefs, ensure_ascii=False)]
    if summary:
        lines.append("较早对话摘要：" + summary)
    for row in rows:
        lines.append(row.role + "：" + row.content)
    return "\n".join(lines)


def maybe_compress(db, conversation_id: int, limit: int, recent_turns: int, summarize):
    rows = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.id.asc()).all()
    if len(rows) <= recent_turns:
        return False
    older = rows[:-recent_turns]
    blob = "\n".join(row.role + "：" + row.content for row in older)
    if estimate_tokens(blob) <= limit:
        return False
    text = summarize(blob)
    row = db.get(MemorySummary, conversation_id)
    if row is None:
        db.add(MemorySummary(conversation_id=conversation_id, summary=text, updated_at=datetime.utcnow()))
    else:
        row.summary = text
        row.updated_at = datetime.utcnow()
    db.commit()
    return True
