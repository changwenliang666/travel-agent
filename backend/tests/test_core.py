import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./test_travel.db"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "secret-pass"
os.environ["QWEN_MODEL"] = "qwen3.7-plus"
os.environ["DEEPSEEK_MODEL"] = "deepseek-chat"

import json
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.services.auth import hash_password, seed_admin
from backend.llm.breaker import Breaker
from backend.config.settings import Settings
from backend.db.models import Base, Conversation, Message, User
from backend.db.session import SessionLocal, engine
from backend.llm.gateway import LLMGateway, ModelCallError
from backend.main import app
from backend.services.memory import build_context, estimate_tokens, maybe_compress, save_prefs
from backend.tools.amap import AmapClient, ToolResult
from backend.tools.search import TavilyClient
from backend.services.trace import Tracer
from backend.services.turn import run_turn, update_prefs_after_reply


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.values = {}

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def hset(self, key, mapping=None, **kwargs):
        row = self.hashes.setdefault(key, {})
        if mapping:
            row.update({str(k): str(v) for k, v in mapping.items()})
        return 1

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, key):
        self.values.pop(key, None)
        self.hashes.pop(key, None)


class FakeResponse:
    def __init__(self, status_code=200, json_body=None, lines=None):
        self.status_code = status_code
        self._json = json_body or {}
        self._lines = lines or []

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def iter_lines(self):
        total = len(self._lines)
        self.remaining = total
        self.finished = False
        for index, line in enumerate(self._lines):
            self.remaining = total - index - 1
            if line == "RAISE":
                raise RuntimeError("stream broke")
            yield line
        self.finished = True


class _FakeStream:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeHttp:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None, params=None):
        self.calls.append({"url": url, "json": json, "params": params})
        return self.handler(url, json, params)

    def stream(self, method, url, json=None, headers=None, timeout=None, params=None):
        self.calls.append({"url": url, "json": json, "params": params})
        response = self.handler(url, json, params)
        return _FakeStream(response)

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        return self.handler(url, None, params)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_seed_admin_once(db):
    seed_admin(db)
    seed_admin(db)
    assert db.query(User).count() == 1
    assert db.query(User).one().role == "admin"


def test_login_and_reject_anonymous():
    with TestClient(app) as client:
        denied = client.get("/api/conversations/list")
        assert denied.status_code == 401
        ok = client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
        assert ok.status_code == 200
        me = client.get("/api/auth/me")
        assert me.json()["role"] == "admin"
        client.post("/api/auth/logout")
        assert client.get("/api/auth/me").status_code == 401


def test_amap_success_and_timeout():
    def handler(url, body, params):
        if "geocode" in url:
            return FakeResponse(200, {"status": "1", "geocodes": [{"location": "120,30", "adcode": "330100", "city": "杭州"}]})
        return FakeResponse(200, {"status": "1", "lives": [{"weather": "晴", "temperature": "22"}], "pois": [{"name": "西湖", "address": "杭州", "location": "120,30"}], "route": {"paths": [{"distance": "100", "duration": "80"}]}})

    client = AmapClient("k", client=FakeHttp(handler))
    assert client.geocode("杭州").ok
    assert client.weather("330100").data["text"].startswith("晴")
    assert client.poi("西湖") .ok
    assert client.route("1,2", "3,4").ok

    def timeout(url, body, params):
        raise httpx.TimeoutException("slow")

    slow = AmapClient("k", client=FakeHttp(timeout))
    result = slow.weather("1")
    assert result.ok is False
    assert "超时" in result.error


def test_tavily_caps_results():
    rows = [{"title": "t" + str(i), "url": "https://e.com/" + str(i), "content": "x" * 500} for i in range(8)]

    def handler(url, body, params):
        return FakeResponse(200, {"results": rows})

    result = TavilyClient("k", client=FakeHttp(handler)).search("杭州")
    assert result.ok
    assert len(result.data) == 5
    assert set(result.data[0].keys()) == {"title", "url", "snippet"}
    assert len(result.data[0]["snippet"]) <= 240
    assert "content" not in result.data[0]


def test_partial_tool_failure_keeps_success():
    weather = ToolResult(True, data={"text": "晴"})
    search = ToolResult(False, error="网页搜索超时")
    materials = {"weather": weather, "search": search}
    ok_items = {key: value for key, value in materials.items() if value.ok}
    assert "weather" in ok_items
    assert "search" not in ok_items


def test_breaker_states():
    now = {"t": 1000.0}
    redis = FakeRedis()
    breaker = Breaker(redis, fail_threshold=5, window_seconds=60, cooldown_seconds=30, now=lambda: now["t"])
    assert breaker.allow() == ("primary", False)
    for _ in range(4):
        breaker.record_failure(False)
    assert breaker.state_name() == "closed"
    breaker.record_failure(False)
    assert breaker.state_name() == "open"
    assert breaker.allow()[0] == "fallback"
    content = Breaker(FakeRedis(), now=lambda: now["t"])
    content.record_failure(False, counts=False)
    assert content.state_name() == "closed"
    now["t"] = 1040
    choice, probe = breaker.allow()
    other, other_probe = breaker.allow()
    assert (choice, probe) == ("primary", True)
    assert (other, other_probe) == ("fallback", False)
    breaker.record_success(True)
    assert breaker.state_name() == "closed"
    now["t"] = 1000
    redis2 = FakeRedis()
    breaker2 = Breaker(redis2, fail_threshold=5, window_seconds=60, cooldown_seconds=30, now=lambda: now["t"])
    for _ in range(5):
        breaker2.record_failure(False)
    now["t"] = 1040
    breaker2.allow()
    breaker2.record_failure(True)
    assert breaker2.state_name() == "open"


def test_llm_closed_uses_primary_and_fallback_rules():
    settings = Settings(qwen_model="qwen3.7-plus", deepseek_model="deepseek-chat", qwen_base_url="http://qwen", deepseek_base_url="http://ds")
    redis = FakeRedis()
    breaker = Breaker(redis, now=lambda: 1)

    def ok_handler(url, body, params):
        return FakeResponse(200, {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 2, "completion_tokens": 1}})

    http = FakeHttp(ok_handler)
    text = LLMGateway(settings, breaker, client=http).complete([{"role": "user", "content": "hi"}], purpose="reply")
    assert text == "ok"
    assert http.calls[0]["json"]["model"] == "qwen3.7-plus"

    calls = {"n": 0}

    def fail_then_ok(url, body, params):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse(500, {})
        return FakeResponse(200, {"choices": [{"message": {"content": "备用"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    http2 = FakeHttp(fail_then_ok)
    text = LLMGateway(settings, Breaker(FakeRedis(), now=lambda: 1), client=http2).complete([{"role": "user", "content": "hi"}], purpose="reply")
    assert text == "备用"
    assert http2.calls[1]["json"]["model"] == "deepseek-chat"

    def content_block(url, body, params):
        return FakeResponse(400, {})

    with pytest.raises(ModelCallError):
        LLMGateway(settings, Breaker(FakeRedis(), now=lambda: 1), client=FakeHttp(content_block)).complete([{"role": "user", "content": "hi"}], purpose="reply")

    def stream_break(url, body, params):
        if body["model"] == "qwen3.7-plus":
            return FakeResponse(200, lines=['data: {"choices":[{"delta":{"content":"你"}}]}', "RAISE"])
        return FakeResponse(200, {"choices": [{"message": {"content": "不该出现"}}], "usage": {}})

    with pytest.raises(ModelCallError):
        LLMGateway(settings, Breaker(FakeRedis(), now=lambda: 1), client=FakeHttp(stream_break)).complete(
            [{"role": "user", "content": "hi"}], purpose="reply", stream=True, on_delta=lambda t: None
        )


def test_llm_stream_emits_delta_before_body_finishes():
    settings = Settings(qwen_model="qwen3.7-plus", deepseek_model="deepseek-chat", qwen_base_url="http://qwen", deepseek_base_url="http://ds")
    lines = [
        'data: {"choices":[{"delta":{"content":"你"}}]}',
        'data: {"choices":[{"delta":{"content":"好"}}]}',
        "data: [DONE]",
    ]
    response = FakeResponse(200, lines=lines)
    seen = []

    def on_delta(text):
        seen.append((text, response.remaining, response.finished))

    text = LLMGateway(settings, Breaker(FakeRedis(), now=lambda: 1), client=FakeHttp(lambda url, body, params: response)).complete(
        [{"role": "user", "content": "hi"}], purpose="reply", stream=True, on_delta=on_delta
    )
    assert text == "你好"
    assert seen[0] == ("你", 2, False)
    assert seen[1][0] == "好"
    assert seen[1][1] > 0
    assert seen[1][2] is False


def test_memory_isolation_and_compress(db):
    user = User(username="u", password_hash=hash_password("p"), role="user")
    db.add(user)
    db.commit()
    a = Conversation(user_id=user.id, title="a", slots_json="{}")
    b = Conversation(user_id=user.id, title="b", slots_json="{}")
    db.add_all([a, b])
    db.commit()
    db.add(Message(conversation_id=a.id, role="user", content="只在对话A出现的句子"))
    db.commit()
    save_prefs(db, user.id, {"budget": "舒适"})
    context_b = build_context(db, user.id, b.id, 6)
    assert "只在对话A出现的句子" not in context_b
    assert "舒适" in context_b
    long = "甲" * 20000
    for _ in range(8):
        db.add(Message(conversation_id=a.id, role="user", content=long))
    db.commit()
    assert estimate_tokens(long) > 6000
    changed = maybe_compress(db, a.id, 6000, 6, lambda blob: "摘要-不含全部原文标记")
    assert changed is True
    context = build_context(db, user.id, a.id, 6)
    assert "摘要-不含全部原文标记" in context
    assert "只在对话A出现的句子" not in context
    assert context.count(long) == 6


def test_preference_update_does_not_change_reply(db):
    user = User(username="u2", password_hash=hash_password("p"), role="user")
    db.add(user)
    db.commit()
    reply = "行程已写好"

    class Boom:
        def complete(self, *args, **kwargs):
            raise RuntimeError("抽取失败")

    try:
        update_prefs_after_reply(db, Boom(), user.id, "我预算低", reply)
    except RuntimeError:
        pass
    assert reply == "行程已写好"


def test_trace_records_tool_and_usage(db):
    user = User(username="u3", password_hash=hash_password("p"), role="user")
    db.add(user)
    db.commit()
    convo = Conversation(user_id=user.id, title="t", slots_json="{}")
    db.add(convo)
    db.commit()
    tracer = Tracer(db, user.id, convo.id)
    span = tracer.start("tool.search", {"ok": True})
    tracer.finish(span, ok=True)
    tracer.usage("qwen3.7-plus", 4, 5, "reply")
    tracer.usage("qwen3.7-plus", 1, 1, "compress")
    from backend.db.models import TokenUsage, TraceSpan

    spans = db.query(TraceSpan).filter(TraceSpan.trace_id == tracer.trace_id).all()
    usage = db.query(TokenUsage).filter(TokenUsage.trace_id == tracer.trace_id).all()
    assert len(spans) == 1
    assert len(usage) == 2


class ScriptLLM:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def complete(self, messages, purpose, stream=False, on_delta=None):
        self.calls.append(purpose)
        text = self.answers.pop(0)
        if stream and on_delta:
            on_delta(text)
        return text


class ScriptTools:
    def __init__(self):
        self.calls = []

    def geocode(self, address):
        self.calls.append("geocode")
        return ToolResult(True, data={"adcode": "1", "location": "1,2"})

    def weather(self, adcode):
        self.calls.append("weather")
        return ToolResult(True, data={"text": "晴 20°C"})

    def poi(self, keywords, city=""):
        self.calls.append("poi")
        return ToolResult(True, data=[{"name": "西湖"}])

    def route(self, origin, destination):
        self.calls.append("route")
        return ToolResult(True, data={"distance": "10", "duration": "5"})

    def search(self, query):
        self.calls.append("search")
        return ToolResult(True, data=[{"title": "攻略", "url": "https://example.com", "snippet": "西湖"}])


def test_itinerary_stream_hides_plan_json():
    from backend.agent.nodes import VisibleMarkdown, split_itinerary

    chunks = ["两天安排", "<<<PLA", "N>>>", '{"destination":"杭州","days_count":2,"days":[]}']
    seen = []
    gate = VisibleMarkdown(seen.append)
    for chunk in chunks:
        gate.push(chunk)
    assert "".join(seen) == "两天安排"
    assert "{" not in "".join(seen)
    markdown, plan = split_itinerary(gate.raw)
    assert markdown == "两天安排"
    assert plan["destination"] == "杭州"

    hidden = []
    raw = '{"markdown":"说明","plan":{"destination":"九华山","days_count":3,"days":[]}}'
    VisibleMarkdown(hidden.append).push(raw)
    assert hidden == []
    markdown, plan = split_itinerary(raw)
    assert markdown == "说明"
    assert plan["destination"] == "九华山"


def test_graph_clarify_and_build_and_answer(db):
    user = User(username="u4", password_hash=hash_password("p"), role="user")
    db.add(user)
    db.commit()
    convo = Conversation(user_id=user.id, title="新对话", slots_json="{}")
    db.add(convo)
    db.commit()
    tools = ScriptTools()
    llm = ScriptLLM(['{"action":"clarify","destination":"","days":null,"question":"想去哪个城市？","revise_note":""}'])
    result = run_turn(db, FakeRedis(), user, convo, "帮我规划", lambda t: None, lambda t: None, llm=llm, amap=tools, search=tools)
    assert "城市" in result["reply"]
    assert tools.calls == []

    llm = ScriptLLM(['{"action":"clarify","destination":"杭州","days":20,"question":"","revise_note":""}'])
    result = run_turn(db, FakeRedis(), user, convo, "玩20天", lambda t: None, lambda t: None, llm=llm, amap=tools, search=tools)
    assert "14" in result["reply"]
    assert tools.calls == []

    plan = {"markdown": "两天", "plan": {"destination": "杭州", "days_count": 2, "date_start": "", "days": [{"day": 1, "title": "西湖", "weather": "晴", "items": [{"time": "上午", "name": "断桥", "note": "走走"}]}], "sources": []}}
    llm = ScriptLLM(['{"action":"build","destination":"杭州","days":2,"date_start":"","question":"","revise_note":""}', json.dumps(plan, ensure_ascii=False)])
    tools.calls.clear()
    result = run_turn(db, FakeRedis(), user, convo, "杭州两天", lambda t: None, lambda t: None, llm=llm, amap=tools, search=tools)
    assert result["plan"]["destination"] == "杭州"
    assert tools.calls == ["geocode", "weather", "search", "poi"]
    assert result["trace_id"]

    llm = ScriptLLM(['{"action":"build","destination":"杭州","days":2,"date_start":"","question":"","revise_note":"第二天改室内"}', json.dumps(plan, ensure_ascii=False)])
    tools.calls.clear()
    run_turn(db, FakeRedis(), user, convo, "第二天改室内", lambda t: None, lambda t: None, llm=llm, amap=tools, search=tools)
    assert tools.calls == []

    llm = ScriptLLM(['{"action":"answer","destination":"杭州","days":2,"date_start":"","question":"","revise_note":""}', '{"tool":"route","origin":"1,2","destination":"3,4"}', "步行约 5 秒"])
    tools.calls.clear()
    result = run_turn(db, FakeRedis(), user, convo, "这两点怎么走", lambda t: None, lambda t: None, llm=llm, amap=tools, search=tools)
    assert tools.calls == ["route"]
    assert "步行" in result["reply"]

    llm = ScriptLLM(['{"action":"answer","destination":"杭州","days":2,"date_start":"","question":"","revise_note":""}', '{"tool":"none"}', "第二天在室内"])
    tools.calls.clear()
    run_turn(db, FakeRedis(), user, convo, "第二天在哪", lambda t: None, lambda t: None, llm=llm, amap=tools, search=tools)
    assert tools.calls == []


def test_message_stream_disables_proxy_buffer(monkeypatch):
    def fake_run(*args, **kwargs):
        on_delta = args[6]
        on_delta("你")
        on_delta("好")
        return {"reply": "你好", "plan": None, "trace_id": "t", "deps": type("D", (), {"llm": None})()}

    monkeypatch.setattr("backend.api.routes.conversations.run_turn", fake_run)
    monkeypatch.setattr("backend.api.routes.conversations.update_prefs_after_reply", lambda *a, **k: None)
    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
        created = client.post("/api/conversations/create")
        response = client.post("/api/conversations/" + str(created.json()["id"]) + "/messages/send", json={"text": "你好"})
        assert response.headers["x-accel-buffering"] == "no"
        assert "event: delta" in response.text
        assert response.text.index("你") < response.text.rindex("好")


def test_conversation_isolation_and_trace_header():
    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
        created = client.post("/api/conversations/create")
        assert created.status_code == 200
        other = User(username="bob", password_hash=hash_password("bob-pass"), role="user")
        db = SessionLocal()
        db.add(other)
        db.commit()
        foreign = Conversation(user_id=other.id, title="别人的", slots_json="{}")
        db.add(foreign)
        db.commit()
        foreign_id = foreign.id
        db.close()
        denied = client.get("/api/conversations/" + str(foreign_id) + "/detail")
        assert denied.status_code == 403
        client.post("/api/auth/logout")
        client.post("/api/auth/login", json={"username": "bob", "password": "bob-pass"})
        blocked = client.get("/api/admin/usage/summary")
        assert blocked.status_code == 403


API_ROUTES = {
    ("GET", "/api/admin/traces/{trace_id}"),
    ("GET", "/api/admin/usage/summary"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/conversations/create"),
    ("GET", "/api/conversations/list"),
    ("GET", "/api/conversations/{conversation_id}/detail"),
    ("POST", "/api/conversations/{conversation_id}/messages/send"),
    ("GET", "/api/health"),
    ("GET", "/api/preferences/current"),
    ("PUT", "/api/preferences/save"),
}


def registered_api_routes():
    found = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            found.append(route)
        original = getattr(route, "original_router", None)
        if original is None:
            continue
        for child in original.routes:
            if isinstance(child, APIRoute):
                found.append(child)
    return [route for route in found if route.path.startswith("/api")]


def test_api_route_catalog_is_unique():
    routes = registered_api_routes()
    paths = [route.path for route in routes]
    assert len(paths) == len(set(paths))
    methods = {(method, route.path) for route in routes for method in route.methods if method not in {"HEAD", "OPTIONS"}}
    assert methods == API_ROUTES


def test_retired_paths_return_404():
    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
        assert client.post("/api/conversations").status_code == 404
        assert client.get("/api/conversations").status_code == 404
        assert client.get("/api/preferences").status_code == 404
        assert client.get("/api/me").status_code == 404
        assert client.get("/api/admin/usage").status_code == 404
