import json
import time
import uuid

from backend.db.models import TokenUsage, Trace, TraceSpan


class Tracer:
    def __init__(self, db, user_id: int, conversation_id: int):
        self.db = db
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.trace_id = uuid.uuid4().hex
        self.db.add(Trace(trace_id=self.trace_id, user_id=user_id, conversation_id=conversation_id))
        self.db.commit()
        self._open = {}

    def start(self, name: str, detail: dict | None = None):
        span_id = len(self._open) + 1 + int(time.time() * 1000) % 100000
        self._open[span_id] = {"name": name, "detail": detail or {}, "t": time.time()}
        return span_id

    def finish(self, span_id, ok: bool = True, error: str = "", extra: dict | None = None):
        item = self._open.pop(span_id, None)
        if item is None:
            return
        detail = dict(item["detail"])
        if extra:
            detail.update(extra)
        if error:
            detail["error"] = error
        latency = int((time.time() - item["t"]) * 1000)
        self.db.add(
            TraceSpan(
                trace_id=self.trace_id,
                name=item["name"],
                status="ok" if ok else "error",
                latency_ms=latency,
                detail_json=json.dumps(detail, ensure_ascii=False),
            )
        )
        self.db.commit()

    def usage(self, model: str, prompt_tokens: int, completion_tokens: int, purpose: str):
        self.db.add(
            TokenUsage(
                trace_id=self.trace_id,
                user_id=self.user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                purpose=purpose,
            )
        )
        self.db.commit()
