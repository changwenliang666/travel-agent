import time


class Breaker:
    def __init__(self, redis, fail_threshold=5, window_seconds=60, cooldown_seconds=30, now=None):
        self.redis = redis
        self.fail_threshold = fail_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.now = now or time.time
        self.key = "breaker:llm"
        self.probe_key = "breaker:llm:probe"

    def _raw(self):
        data = self.redis.hgetall(self.key) or {}
        return {str(k): str(v) for k, v in data.items()}

    def state_name(self) -> str:
        now = self.now()
        raw = self._raw()
        state = raw.get("state") or "closed"
        if state == "open":
            opened = float(raw.get("opened_at") or 0)
            if now - opened >= self.cooldown_seconds:
                self.redis.hset(self.key, mapping={"state": "half_open"})
                return "half_open"
        return state

    def allow(self):
        state = self.state_name()
        if state == "closed":
            return "primary", False
        if state == "open":
            return "fallback", False
        got = self.redis.set(self.probe_key, "1", nx=True, ex=self.cooldown_seconds)
        if got:
            return "primary", True
        return "fallback", False

    def record_success(self, is_probe: bool) -> None:
        self.redis.hset(self.key, mapping={"state": "closed", "fail_count": "0", "window_started_at": "0", "opened_at": "0"})
        if is_probe:
            self.redis.delete(self.probe_key)

    def record_failure(self, is_probe: bool, counts: bool = True) -> None:
        if not counts:
            return
        now = self.now()
        if is_probe or self.state_name() == "half_open":
            self.redis.hset(self.key, mapping={"state": "open", "opened_at": str(now), "fail_count": "0"})
            self.redis.delete(self.probe_key)
            return
        raw = self._raw()
        started = float(raw.get("window_started_at") or 0)
        count = int(raw.get("fail_count") or 0)
        if started == 0 or now - started > self.window_seconds:
            started = now
            count = 0
        count += 1
        if count >= self.fail_threshold:
            self.redis.hset(self.key, mapping={"state": "open", "opened_at": str(now), "fail_count": "0", "window_started_at": "0"})
            return
        self.redis.hset(self.key, mapping={"state": "closed", "fail_count": str(count), "window_started_at": str(started)})
