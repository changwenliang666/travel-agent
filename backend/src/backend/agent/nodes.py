import json

from backend.tools.amap import ToolResult


PLAN_MARK = "<<<PLAN>>>"


def parse_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("没有 JSON")
    return json.loads(text[start : end + 1])


def missing_notes(materials: dict) -> list:
    notes = []
    labels = {"weather": "天气", "search": "网页资料", "poi": "地点", "route": "路径"}
    for key, label in labels.items():
        item = materials.get(key)
        if item is not None and not item.ok:
            notes.append(label + "没能查到")
    return notes


def normalize_slots(data: dict) -> dict:
    days = data.get("days")
    if days in ("", None):
        days_value = None
    else:
        try:
            days_value = int(days)
        except (TypeError, ValueError):
            days_value = None
    return {
        "destination": (data.get("destination") or "").strip(),
        "days": days_value,
        "date_start": (data.get("date_start") or "").strip(),
        "question": (data.get("question") or "").strip(),
        "revise_note": (data.get("revise_note") or "").strip(),
        "action": data.get("action") or "clarify",
    }


def needs_clarify(slots: dict) -> bool:
    days = slots.get("days")
    if not slots.get("destination"):
        return True
    if not isinstance(days, int) or days < 1 or days > 14:
        return True
    return False


def extract_node(state, deps):
    span = deps.tracer.start("memory.load")
    context = deps.memory_context()
    deps.tracer.finish(span, ok=True)
    raw = deps.llm.complete(
        [
            {"role": "system", "content": "只返回一个 JSON 对象，不要解释。必须包含 action、destination、days、date_start、question、revise_note。destination 写用户提到的城市。例如用户说杭州玩两天，destination 是杭州，days 是 2。目的地和 1 到 14 的天数都有时 action 用 build。缺目的地或缺天数时 action 用 clarify，并在 question 里追问。已有行程且只是提问时 action 用 answer。修改行程时 action 用 build，并把修改写进 revise_note。"},
            {"role": "user", "content": context + "\n当前槽位：" + json.dumps(state.get("slots") or {}, ensure_ascii=False) + "\n已有行程：" + json.dumps(state.get("plan") or {}, ensure_ascii=False) + "\n用户说：" + state["user_text"]},
        ],
        purpose="extract",
    )
    try:
        slots = normalize_slots(parse_json(raw))
    except (ValueError, json.JSONDecodeError):
        slots = {"destination": "", "days": None, "date_start": "", "question": "我没听清，请再说一下目的地和天数。", "revise_note": "", "action": "clarify"}
    if needs_clarify(slots):
        slots["action"] = "clarify"
        if not slots["question"]:
            if not slots["destination"]:
                slots["question"] = "想去哪个城市？"
            else:
                slots["question"] = "这次玩几天？请给一个 1 到 14 的天数。"
    if slots["action"] == "clarify" and not slots["question"]:
        slots["question"] = "请补充目的地和天数。"
    return {
        "slots": slots,
        "action": slots["action"],
        "revise_note": slots["revise_note"],
        "plan": state.get("plan"),
        "user_text": state.get("user_text"),
        "prefs": state.get("prefs") or {},
    }


def clarify_node(state, deps):
    return {"reply": state["slots"].get("question") or "请补充目的地和天数。", "plan": state.get("plan")}


class VisibleMarkdown:
    """把模型输出里面向用户的 Markdown 转发出去，挡住行程 JSON。"""

    def __init__(self, on_delta):
        self.on_delta = on_delta
        self.raw = ""
        self._sent = 0
        self._suppress = None

    def push(self, delta: str):
        if not delta:
            return
        self.raw += delta
        if self._suppress is None:
            stripped = self.raw.lstrip()
            if not stripped:
                return
            self._suppress = stripped.startswith("{")
        if self._suppress or self.on_delta is None:
            return
        visible = self.raw
        cut = visible.find(PLAN_MARK)
        done = cut >= 0
        if done:
            visible = visible[:cut]
        else:
            for size in range(len(PLAN_MARK) - 1, 0, -1):
                if visible.endswith(PLAN_MARK[:size]):
                    visible = visible[:-size]
                    break
        if len(visible) > self._sent:
            self.on_delta(visible[self._sent :])
            self._sent = len(visible)


def split_itinerary(raw: str) -> tuple[str, dict]:
    text = raw or ""
    if PLAN_MARK in text:
        markdown, _, plan_raw = text.partition(PLAN_MARK)
        plan = parse_json(plan_raw) if plan_raw.strip() else {}
        return markdown.strip(), plan
    if text.lstrip().startswith("{"):
        data = parse_json(text)
        plan = data.get("plan") or {}
        return (data.get("markdown") or "").strip(), plan
    return text.strip(), {}


def same_place_and_date(old, slots) -> bool:
    if not old:
        return False
    return (old.get("destination") or "") == (slots.get("destination") or "") and (old.get("date_start") or "") == (slots.get("date_start") or "")


def build_node(state, deps):
    slots = state["slots"]
    old = state.get("plan")
    note = state.get("revise_note") or slots.get("revise_note") or ""
    skip = bool(note) and same_place_and_date(old, slots)
    materials = {}
    if skip:
        deps.on_progress("正在按修改重写行程")
    else:
        deps.on_progress("正在查天气")
        geo = deps.amap.geocode(slots["destination"])
        if geo.ok:
            materials["weather"] = deps.amap.weather(geo.data["adcode"])
        else:
            materials["weather"] = geo
        deps.tracer_tool("tool.weather", materials["weather"])
        deps.on_progress("正在搜索")
        materials["search"] = deps.search.search(slots["destination"] + " " + str(slots["days"]) + "日游")
        deps.tracer_tool("tool.search", materials["search"])
        deps.on_progress("正在找地点")
        materials["poi"] = deps.amap.poi(slots["destination"] + " 景点", slots["destination"])
        deps.tracer_tool("tool.poi", materials["poi"])
    deps.on_progress("正在写行程")
    prompt = {
        "slots": slots,
        "prefs": state.get("prefs") or {},
        "old_plan": old,
        "revise_note": note,
        "materials": {key: value.as_dict() for key, value in materials.items()},
    }
    visible = VisibleMarkdown(deps.on_delta)
    raw = deps.llm.complete(
        [
            {
                "role": "system",
                "content": "先写面向用户的 Markdown 说明，不要输出 JSON。写完后单独一行输出 <<<PLAN>>>，再输出行程 JSON：{\"destination\":\"\",\"days_count\":1,\"date_start\":\"\",\"days\":[{\"day\":1,\"title\":\"\",\"weather\":\"\",\"items\":[{\"time\":\"上午\",\"name\":\"\",\"note\":\"\"}]}],\"sources\":[{\"title\":\"\",\"url\":\"\"}]}。分隔行之前不要出现花括号 JSON。",
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        purpose="reply",
        stream=True,
        on_delta=visible.push,
    )
    try:
        markdown, plan = split_itinerary(raw)
    except (ValueError, json.JSONDecodeError):
        markdown, plan = raw, old or {"destination": slots["destination"], "days_count": slots["days"], "days": [], "sources": []}
    if not plan:
        plan = old or {"destination": slots["destination"], "days_count": slots["days"], "days": [], "sources": []}
    notes = missing_notes(materials)
    if notes:
        markdown = markdown + "\n\n" + "、".join(notes) + "。"
    sources = []
    search = materials.get("search")
    if search is not None and search.ok:
        sources = [{"title": item.get("title"), "url": item.get("url")} for item in search.data]
    if sources and not plan.get("sources"):
        plan["sources"] = sources
    return {"reply": markdown, "plan": plan}


def answer_node(state, deps):
    raw = deps.llm.complete(
        [
            {"role": "system", "content": "只返回 JSON：{\"tool\":\"none|search|poi|route\",\"query\":\"\",\"origin\":\"\",\"destination\":\"\"}。不需要外部资料时 tool 为 none。"},
            {"role": "user", "content": "行程：" + json.dumps(state.get("plan") or {}, ensure_ascii=False) + "\n问题：" + state["user_text"]},
        ],
        purpose="route",
    )
    try:
        choice = parse_json(raw)
    except (ValueError, json.JSONDecodeError):
        choice = {"tool": "none"}
    tool = choice.get("tool") or "none"
    materials = {}
    if tool == "search":
        materials["search"] = deps.search.search(choice.get("query") or state["user_text"])
        deps.tracer_tool("tool.search", materials["search"])
    elif tool == "poi":
        materials["poi"] = deps.amap.poi(choice.get("query") or state["user_text"])
        deps.tracer_tool("tool.poi", materials["poi"])
    elif tool == "route":
        materials["route"] = deps.amap.route(choice.get("origin") or "", choice.get("destination") or "")
        deps.tracer_tool("tool.route", materials["route"])
    deps.on_progress("正在回答")
    reply = deps.llm.complete(
        [
            {"role": "system", "content": "用 Markdown 回答。"},
            {"role": "user", "content": json.dumps({"question": state["user_text"], "plan": state.get("plan"), "materials": {k: v.as_dict() for k, v in materials.items()}}, ensure_ascii=False)},
        ],
        purpose="reply",
        stream=True,
        on_delta=deps.on_delta,
    )
    notes = missing_notes(materials)
    if notes:
        reply = reply + "\n\n" + "、".join(notes) + "。"
    return {"reply": reply, "plan": state.get("plan")}


def route_after_extract(state):
    action = state.get("action") or "clarify"
    if action not in ("clarify", "build", "answer"):
        return "clarify"
    return action
