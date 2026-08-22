"""Provider-neutral data contracts shared by the comparison harness."""

from dataclasses import asdict, dataclass, field, fields
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type, TypeVar


T = TypeVar("T", bound="Serializable")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


class Serializable:
    def to_dict(self) -> Dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls: Type[T], data: Mapping[str, Any]) -> T:
        names = {item.name for item in fields(cls)}
        values = {key: value for key, value in data.items() if key in names}
        for item in fields(cls):
            if item.name in values and item.type in (Tuple[str, ...], tuple):
                values[item.name] = tuple(values[item.name])
        return cls(**values)


_VALID_TASK_AREAS = frozenset({"se", "terminal", "qna"})


@dataclass
class TaskSpec(Serializable):
    task_id: str
    prompt: str
    description: str = ""
    repository: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    benchmark: str = ""
    workspace_snapshot: Any = ""
    verifier: str = ""
    timeout: float = 300.0
    area: str = ""
    verifier_name: str = ""

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.area and self.area not in _VALID_TASK_AREAS:
            raise ValueError(
                "area must be one of {} or empty".format(
                    ", ".join(sorted(_VALID_TASK_AREAS))
                )
            )


@dataclass
class ModelConfig(Serializable):
    provider: str
    model: str
    endpoint: Optional[str] = None
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.model.strip():
            raise ValueError("provider and model must not be empty")
        if self.temperature < 0:
            raise ValueError("temperature must be non-negative")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")


@dataclass
class ExecutionPolicy(Serializable):
    headless: bool = False
    allow_writes: bool = False
    allow_destructive: bool = False
    allow_shell: bool = False
    require_confirmation_for_writes: bool = True
    workspace_root: Optional[str] = None
    allowed_tools: Tuple[str, ...] = ()
    denied_tools: Tuple[str, ...] = ()


@dataclass
class RunLimits(Serializable):
    max_turns: int = 20
    max_tool_calls: int = 50
    timeout_seconds: float = 300.0
    max_output_chars: int = 20000

    def __post_init__(self) -> None:
        if self.max_turns <= 0 or self.max_tool_calls < 0:
            raise ValueError("run limits must be positive or zero")
        if self.timeout_seconds <= 0 or self.max_output_chars <= 0:
            raise ValueError("timeout and output limits must be positive")


@dataclass
class UsageMetrics(Serializable):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0

    def __post_init__(self) -> None:
        if min(
            self.input_tokens,
            self.output_tokens,
            self.cached_tokens,
            self.cost_usd,
            self.requests,
        ) < 0:
            raise ValueError("usage values must be non-negative")

    def add(self, other: "UsageMetrics") -> "UsageMetrics":
        return UsageMetrics(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
            requests=self.requests + other.requests,
        )


@dataclass
class LLMRequest(Serializable):
    messages: List[Dict[str, Any]]
    model: ModelConfig
    tools: List[Dict[str, Any]] = field(default_factory=list)
    system_prompt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LLMRequest":
        values = dict(data)
        values["model"] = ModelConfig.from_dict(values["model"])
        return cls(**values)


@dataclass
class ToolCall(Serializable):
    call_id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    arguments_fragment: str = ""
    fragment_index: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.call_id.strip():
            raise ValueError("tool calls require an id and name")
        if not self.name.strip() and not (
            self.arguments_fragment or self.fragment_index is not None
        ):
            raise ValueError("tool calls require an id and name")


@dataclass
class ToolResult(Serializable):
    call_id: str
    tool_name: str
    output: Any = ""
    success: bool = True
    error: Optional[str] = None


@dataclass
class LLMResponse(Serializable):
    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = "stop"
    usage: UsageMetrics = field(default_factory=UsageMetrics)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LLMResponse":
        values = dict(data)
        values["tool_calls"] = [
            item if isinstance(item, ToolCall) else ToolCall.from_dict(item)
            for item in values.get("tool_calls", [])
        ]
        usage = values.get("usage", {})
        values["usage"] = usage if isinstance(usage, UsageMetrics) else UsageMetrics.from_dict(usage)
        return cls(**values)


@dataclass
class RunRequest(Serializable):
    task: TaskSpec
    model: ModelConfig
    policy: ExecutionPolicy
    limits: RunLimits = field(default_factory=RunLimits)
    attempt_id: str = ""
    attempt: str = ""
    system_name: str = ""
    workspace: Path = Path(".")

    def __post_init__(self) -> None:
        if self.attempt and not self.attempt_id:
            self.attempt_id = self.attempt
        elif self.attempt_id and not self.attempt:
            self.attempt = self.attempt_id

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RunRequest":
        values = dict(data)
        values["task"] = TaskSpec.from_dict(values["task"])
        values["model"] = ModelConfig.from_dict(values["model"])
        values["policy"] = ExecutionPolicy.from_dict(values["policy"])
        values["workspace"] = Path(values["workspace"])
        values["limits"] = RunLimits.from_dict(values["limits"])
        return cls(**values)


@dataclass
class VerifierResult(Serializable):
    passed: bool
    score: float = 0.0
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("verifier score must be between zero and one")


@dataclass
class RunResult(Serializable):
    run_id: str
    status: str
    final_text: str
    transcript_path: Path
    event_path: Path
    verifier_result: VerifierResult
    turns: int
    usage: UsageMetrics
    wall_time: float
    artifact_dir: Path = Path(".")
    tool_calls: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.verifier_result.passed

    @property
    def verifier(self) -> VerifierResult:
        return self.verifier_result

    @property
    def events_path(self) -> Path:
        return self.event_path

    @property
    def wall_time_seconds(self) -> float:
        return self.wall_time

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RunResult":
        values = dict(data)
        values["verifier_result"] = VerifierResult.from_dict(values["verifier_result"])
        values["usage"] = UsageMetrics.from_dict(values["usage"])
        values["transcript_path"] = Path(values["transcript_path"])
        values["event_path"] = Path(values["event_path"])
        values["artifact_dir"] = Path(values["artifact_dir"])
        return cls(**values)
