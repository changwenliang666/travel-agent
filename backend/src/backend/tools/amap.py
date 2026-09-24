import httpx


class ToolResult:
    def __init__(self, ok: bool, data=None, error: str = ""):
        self.ok = ok
        self.data = data
        self.error = error

    def as_dict(self):
        return {"ok": self.ok, "data": self.data, "error": self.error}


class AmapClient:
    def __init__(self, key: str, timeout: float = 8, client: httpx.Client | None = None):
        self.key = key
        self.timeout = timeout
        self.client = client or httpx.Client(timeout=timeout)
        self.base = "https://restapi.amap.com"

    def _get(self, path: str, params: dict) -> ToolResult:
        params = dict(params)
        params["key"] = self.key
        try:
            response = self.client.get(self.base + path, params=params, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException:
            return ToolResult(False, error="高德请求超时")
        except httpx.HTTPError as exc:
            return ToolResult(False, error="高德请求失败: " + str(exc))
        if str(body.get("status")) != "1":
            return ToolResult(False, error=body.get("info") or "高德返回失败")
        return ToolResult(True, data=body)

    def geocode(self, address: str) -> ToolResult:
        result = self._get("/v3/geocode/geo", {"address": address})
        if not result.ok:
            return result
        codes = result.data.get("geocodes") or []
        if not codes:
            return ToolResult(False, error="没有解析到地理位置")
        item = codes[0]
        return ToolResult(True, data={"location": item.get("location"), "adcode": item.get("adcode"), "city": item.get("city") or address})

    def weather(self, adcode: str) -> ToolResult:
        result = self._get("/v3/weather/weatherInfo", {"city": adcode})
        if not result.ok:
            return result
        lives = result.data.get("lives") or []
        if not lives:
            return ToolResult(False, error="没有天气数据")
        live = lives[0]
        text = live.get("weather", "") + " " + live.get("temperature", "") + "°C"
        return ToolResult(True, data={"text": text.strip()})

    def poi(self, keywords: str, city: str = "") -> ToolResult:
        result = self._get("/v3/place/text", {"keywords": keywords, "city": city, "offset": 5})
        if not result.ok:
            return result
        places = []
        for item in (result.data.get("pois") or [])[:5]:
            places.append({"name": item.get("name"), "address": item.get("address"), "location": item.get("location")})
        return ToolResult(True, data=places)

    def route(self, origin: str, destination: str) -> ToolResult:
        result = self._get("/v3/direction/walking", {"origin": origin, "destination": destination})
        if not result.ok:
            return result
        paths = (result.data.get("route") or {}).get("paths") or []
        if not paths:
            return ToolResult(False, error="没有路径")
        return ToolResult(True, data={"distance": paths[0].get("distance"), "duration": paths[0].get("duration")})
