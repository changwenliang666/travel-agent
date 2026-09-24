import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.db.models import TokenUsage, Trace, TraceSpan
from backend.db.session import get_db
from backend.services.auth import current_user, require_admin

router = APIRouter()


@router.get("/api/admin/traces/{trace_id}")
def get_admin_trace(trace_id: str, request: Request, db: Session = Depends(get_db)):
    user = current_user(db, request)
    require_admin(user)
    trace = db.query(Trace).filter(Trace.trace_id == trace_id).one_or_none()
    if trace is None:
        raise HTTPException(status_code=404, detail="没有这条 trace")
    spans = db.query(TraceSpan).filter(TraceSpan.trace_id == trace_id).all()
    usage = db.query(TokenUsage).filter(TokenUsage.trace_id == trace_id).all()
    return {
        "trace_id": trace_id,
        "spans": [{"name": item.name, "status": item.status, "latency_ms": item.latency_ms, "detail": json.loads(item.detail_json or "{}")} for item in spans],
        "usage": [{"model": item.model, "prompt_tokens": item.prompt_tokens, "completion_tokens": item.completion_tokens, "purpose": item.purpose} for item in usage],
    }


@router.get("/api/admin/usage/summary")
def get_admin_usage_summary(request: Request, db: Session = Depends(get_db), user_id: int | None = None, start: str | None = None, end: str | None = None):
    user = current_user(db, request)
    require_admin(user)
    query = db.query(TokenUsage)
    if user_id is not None:
        query = query.filter(TokenUsage.user_id == user_id)
    if start:
        query = query.filter(TokenUsage.created_at >= datetime.fromisoformat(start))
    if end:
        query = query.filter(TokenUsage.created_at <= datetime.fromisoformat(end))
    rows = query.all()
    prompt = sum(item.prompt_tokens for item in rows)
    completion = sum(item.completion_tokens for item in rows)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "calls": len(rows)}
