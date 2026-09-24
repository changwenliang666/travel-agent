import json

import httpx

from backend.llm.breaker import Breaker
from backend.config.settings import Settings


class ModelCallError(Exception):
    def __init__(self, message: str, status_code: int = 0, started: bool = False, counts: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.started = started
        self.counts = counts


class LLMGateway:
    def __init__(self, settings: Settings, breaker: Breaker, client: httpx.Client | None = None, tracer=None):
        self.settings = settings
        self.breaker = breaker
        self.client = client or httpx.Client()
        self.tracer = tracer

    def _target(self, choice: str):
        if choice == "primary":
            return self.settings.qwen_model, self.settings.qwen_base_url, self.settings.qwen_api_key
        return self.settings.deepseek_model, self.settings.deepseek_base_url, self.settings.deepseek_api_key

    def complete(self, messages, purpose: str, stream: bool = False, on_delta=None) -> str:
        choice, is_probe = self.breaker.allow()
        try:
            text, usage = self._once(choice, messages, purpose, stream, on_delta, is_probe)
            self.breaker.record_success(is_probe)
            return text
        except ModelCallError as exc:
            if exc.counts:
                self.breaker.record_failure(is_probe, counts=True)
            if exc.started:
                raise
            if choice == "primary" and exc.counts:
                text, usage = self._once("fallback", messages, purpose, stream, on_delta, False)
                return text
            raise

    def _once(self, choice, messages, purpose, stream, on_delta, is_probe):
        model, base, key = self._target(choice)
        span = None
        if self.tracer is not None:
            span = self.tracer.start("llm.call", {"model": model, "purpose": purpose, "breaker": self.breaker.state_name()})
        payload = {"model": model, "messages": messages, "stream": stream}
        if stream:
            payload["stream_options"] = {"include_usage": True}
        timeout = httpx.Timeout(connect=self.settings.model_connect_timeout, read=self.settings.model_first_token_timeout, write=self.settings.model_connect_timeout, pool=self.settings.model_connect_timeout)
        url = base.rstrip("/") + "/chat/completions"
        headers = {"Authorization": "Bearer " + key}
        if stream:
            try:
                with self.client.stream("POST", url, json=payload, headers=headers, timeout=timeout) as response:
                    if response.status_code >= 400:
                        self._fail_status(response, span)
                    text, usage = self._read_stream(response, on_delta, span)
            except ModelCallError:
                raise
            except httpx.TimeoutException as exc:
                if self.tracer is not None:
                    self.tracer.finish(span, ok=False, error="timeout")
                raise ModelCallError("模型超时", started=False, counts=True) from exc
            except httpx.HTTPError as exc:
                if self.tracer is not None:
                    self.tracer.finish(span, ok=False, error=str(exc))
                raise ModelCallError("模型连接失败", started=False, counts=True) from exc
        else:
            try:
                response = self.client.post(url, json=payload, headers=headers, timeout=timeout)
            except httpx.TimeoutException as exc:
                if self.tracer is not None:
                    self.tracer.finish(span, ok=False, error="timeout")
                raise ModelCallError("模型超时", started=False, counts=True) from exc
            except httpx.HTTPError as exc:
                if self.tracer is not None:
                    self.tracer.finish(span, ok=False, error=str(exc))
                raise ModelCallError("模型连接失败", started=False, counts=True) from exc
            if response.status_code >= 400:
                self._fail_status(response, span)
            body = response.json()
            text = body["choices"][0]["message"]["content"]
            usage = body.get("usage") or {}
        if self.tracer is not None:
            self.tracer.usage(model, usage.get("prompt_tokens") or 0, usage.get("completion_tokens") or 0, purpose)
            self.tracer.finish(span, ok=True, extra={"prompt_tokens": usage.get("prompt_tokens") or 0, "completion_tokens": usage.get("completion_tokens") or 0})
        return text, usage

    def _fail_status(self, response, span):
        counts = response.status_code not in (400, 403)
        if self.tracer is not None:
            self.tracer.finish(span, ok=False, error=str(response.status_code))
        raise ModelCallError("模型返回错误", status_code=response.status_code, started=False, counts=counts)

    def _read_stream(self, response, on_delta, span):
        parts = []
        usage = {}
        started = False
        try:
            for line in response.iter_lines():
                if not line or not str(line).startswith("data:"):
                    continue
                data = str(line)[5:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if event.get("usage"):
                    usage = event["usage"]
                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = (choices[0].get("delta") or {}).get("content") or ""
                if delta:
                    started = True
                    parts.append(delta)
                    if on_delta is not None:
                        on_delta(delta)
        except Exception as exc:
            if self.tracer is not None:
                self.tracer.finish(span, ok=False, error=str(exc))
            raise ModelCallError("流式输出中断", started=started, counts=True) from exc
        return "".join(parts), usage
