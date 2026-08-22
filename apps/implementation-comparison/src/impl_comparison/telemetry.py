"""In-process metrics accumulation for one run."""

from dataclasses import dataclass
import time
import threading

from .protocol import UsageMetrics


class RunLimitExceeded(RuntimeError):
    """Raised at the point a reported turn or tool call exceeds its budget."""

    def __init__(self, kind: str, limit: int):
        super().__init__("{} limit exceeded ({})".format(kind, limit))
        self.kind = kind
        self.limit = limit


@dataclass
class RunMetrics:
    turns: int
    tool_calls: int
    wall_time_seconds: float
    usage: UsageMetrics


class MetricsAccumulator:
    def __init__(self, max_turns=None, max_tool_calls=None):
        self.turns = 0
        self.tool_calls = 0
        self.max_turns = max_turns
        self.max_tool_calls = max_tool_calls
        self.usage = UsageMetrics()
        self._started = time.monotonic()
        self._finished_at = None
        self._lock = threading.Lock()

    def record_turn(self) -> None:
        with self._lock:
            self.turns += 1
            if self.max_turns is not None and self.turns > self.max_turns:
                raise RunLimitExceeded("turn", self.max_turns)

    def record_tool_call(self) -> None:
        with self._lock:
            self.tool_calls += 1
            if (
                self.max_tool_calls is not None
                and self.tool_calls > self.max_tool_calls
            ):
                raise RunLimitExceeded("tool call", self.max_tool_calls)

    def add_usage(self, usage: UsageMetrics) -> None:
        with self._lock:
            self.usage = self.usage.add(usage)

    def merge_child(self, turns: int, tool_calls: int, usage: UsageMetrics) -> None:
        with self._lock:
            self.turns = turns
            self.tool_calls = tool_calls
            self.usage = usage

    def finish(self) -> RunMetrics:
        with self._lock:
            if self._finished_at is None:
                self._finished_at = time.monotonic()
            return RunMetrics(
                turns=self.turns,
                tool_calls=self.tool_calls,
                wall_time_seconds=max(0.0, self._finished_at - self._started),
                usage=self.usage,
            )
