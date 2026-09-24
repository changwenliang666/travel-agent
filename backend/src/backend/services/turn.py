import json
from datetime import datetime

from backend.llm.breaker import Breaker
from backend.config.settings import get_settings
from backend.db.models import Conversation, Message, TripPlan
from backend.agent.graph import make_graph
from backend.llm.gateway import LLMGateway, ModelCallError
from backend.services.memory import build_context, get_prefs, maybe_compress, save_prefs
from backend.tools.amap import AmapClient
from backend.tools.search import TavilyClient
from backend.services.trace import Tracer


class Deps:
    def __init__(self, db, user_id, conversation_id, tracer, llm, amap, search, on_progress, on_delta):
        self.db = db
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.tracer = tracer
        self.llm = llm
        self.amap = amap
        self.search = search
        self.on_progress = on_progress
        self.on_delta = on_delta
        self.tool_calls = []

    def memory_context(self):
        settings = get_settings()
        return build_context(self.db, self.user_id, self.conversation_id, settings.recent_turns)

    def tracer_tool(self, name, result):
        self.tool_calls.append(name)
        span = self.tracer.start(name, {"ok": result.ok})
        self.tracer.finish(span, ok=result.ok, error=result.error)


def run_turn(db, redis, user, conversation, user_text, on_progress, on_delta, llm=None, amap=None, search=None):
    settings = get_settings()
    tracer = Tracer(db, user.id, conversation.id)
    if llm is None:
        breaker = Breaker(
            redis,
            fail_threshold=settings.breaker_fail_threshold,
            window_seconds=settings.breaker_window_seconds,
            cooldown_seconds=settings.breaker_cooldown_seconds,
        )
        llm = LLMGateway(settings, breaker, tracer=tracer)
    if amap is None:
        amap = AmapClient(settings.amap_key, timeout=settings.tool_timeout_seconds)
    if search is None:
        search = TavilyClient(settings.tavily_api_key, timeout=settings.tool_timeout_seconds)
    deps = Deps(db, user.id, conversation.id, tracer, llm, amap, search, on_progress, on_delta)
    compressed = maybe_compress(
        db,
        conversation.id,
        settings.context_token_limit,
        settings.recent_turns,
        lambda blob: llm.complete([{"role": "user", "content": "把下面的对话收成简短摘要：\n" + blob}], purpose="compress"),
    )
    if compressed:
        span = tracer.start("memory.compress")
        tracer.finish(span, ok=True)
    plan = None
    row = db.query(TripPlan).filter(TripPlan.conversation_id == conversation.id).one_or_none()
    if row is not None:
        plan = json.loads(row.plan_json or "{}")
    slots = json.loads(conversation.slots_json or "{}")
    graph = make_graph(deps)
    try:
        result = graph.invoke(
            {
                "user_text": user_text,
                "slots": slots,
                "plan": plan,
                "prefs": get_prefs(db, user.id),
                "revise_note": "",
                "action": "",
                "reply": "",
            }
        )
    except ModelCallError as exc:
        on_progress("")
        raise exc
    reply = result.get("reply") or ""
    new_plan = result.get("plan")
    new_slots = result.get("slots") or slots
    conversation.slots_json = json.dumps(new_slots, ensure_ascii=False)
    if conversation.title == "新对话":
        conversation.title = user_text[:24] or "新对话"
    db.add(Message(conversation_id=conversation.id, role="user", content=user_text))
    db.add(Message(conversation_id=conversation.id, role="assistant", content=reply))
    if new_plan:
        if row is None:
            db.add(TripPlan(conversation_id=conversation.id, plan_json=json.dumps(new_plan, ensure_ascii=False), updated_at=datetime.utcnow()))
        else:
            row.plan_json = json.dumps(new_plan, ensure_ascii=False)
            row.updated_at = datetime.utcnow()
    db.commit()
    return {"reply": reply, "plan": new_plan, "trace_id": tracer.trace_id, "deps": deps}


def update_prefs_after_reply(db, llm, user_id, user_text, reply):
    raw = llm.complete(
        [
            {"role": "system", "content": "只返回 JSON 偏好字段 home_city,pace,budget,diet,early_start。没有就用空字符串。"},
            {"role": "user", "content": user_text + "\n" + reply},
        ],
        purpose="prefs",
    )
    from backend.agent.nodes import parse_json

    data = parse_json(raw)
    current = get_prefs(db, user_id)
    for key in ("home_city", "pace", "budget", "diet", "early_start"):
        if key in data and data[key] not in ("", None):
            current[key] = data[key]
    save_prefs(db, user_id, current)
