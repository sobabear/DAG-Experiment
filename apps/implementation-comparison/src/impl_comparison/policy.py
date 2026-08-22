"""Workspace and tool execution policy checks."""

from enum import Enum
from pathlib import Path
from typing import Union

from .protocol import ExecutionPolicy


class PolicyError(PermissionError):
    pass


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


def validate_path(path: Union[str, Path], workspace_root: Union[str, Path]) -> Path:
    root = Path(workspace_root).expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PolicyError("path is outside the workspace") from exc
    return candidate


def decide_tool(
    tool_name: str,
    read_only: bool,
    destructive: bool,
    policy: ExecutionPolicy,
) -> Decision:
    if tool_name in policy.denied_tools:
        return Decision.DENY
    if policy.allowed_tools and tool_name not in policy.allowed_tools:
        return Decision.DENY
    if tool_name == "shell" and not policy.allow_shell:
        return Decision.DENY
    if destructive and not policy.allow_destructive:
        return Decision.DENY
    if tool_name == "shell":
        return Decision.ALLOW
    if read_only:
        return Decision.ALLOW
    if policy.headless:
        return Decision.ALLOW if policy.allow_writes else Decision.DENY
    if policy.allow_writes or not policy.require_confirmation_for_writes:
        return Decision.ALLOW
    return Decision.ASK
