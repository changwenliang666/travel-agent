import httpx

from backend.tools.amap import ToolResult


class TavilyClient:
    def __init__(self, api_key: str, timeout: float = 8, client: httpx.Client | None = None):
        self.api_key = api_key
        self.timeout = timeout
        self.client = client or httpx.Client(timeout=timeout)

    def search(self, query: str) -> ToolResult:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": 5,
            "search_depth": "basic",
            "include_answer": False,
        }
        try:
            response = self.client.post("https://api.tavily.com/search", json=payload, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException:
            return ToolResult(False, error="网页搜索超时")
        except httpx.HTTPError as exc:
            return ToolResult(False, error="网页搜索失败: " + str(exc))
        items = []
        for row in (body.get("results") or [])[:5]:
            content = row.get("content") or ""
            items.append({"title": row.get("title") or "", "url": row.get("url") or "", "snippet": content[:240]})
        return ToolResult(True, data=items)
