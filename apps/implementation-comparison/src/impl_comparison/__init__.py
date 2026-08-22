"""Shared protocol and harness for implementation-comparison runs."""

from .protocol import (
    ExecutionPolicy,
    LLMRequest,
    LLMResponse,
    ModelConfig,
    RunLimits,
    RunRequest,
    RunResult,
    TaskSpec,
    ToolCall,
    ToolResult,
    UsageMetrics,
    VerifierResult,
)

__all__ = [
    "ExecutionPolicy",
    "LLMRequest",
    "LLMResponse",
    "ModelConfig",
    "RunLimits",
    "RunRequest",
    "RunResult",
    "TaskSpec",
    "ToolCall",
    "ToolResult",
    "UsageMetrics",
    "VerifierResult",
]
