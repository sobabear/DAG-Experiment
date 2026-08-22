from pathlib import Path

import pytest

from impl_comparison.policy import Decision, PolicyError, decide_tool, validate_path
from impl_comparison.protocol import ExecutionPolicy


def test_validate_path_rejects_workspace_escape(tmp_path):
    with pytest.raises(PolicyError):
        validate_path(tmp_path / ".." / "outside.txt", tmp_path)


def test_policy_denies_writes_in_headless_mode_by_default(tmp_path):
    policy = ExecutionPolicy(headless=True, workspace_root=str(tmp_path))

    assert (
        decide_tool("write", read_only=False, destructive=False, policy=policy)
        == Decision.DENY
    )
    assert (
        decide_tool("read", read_only=True, destructive=False, policy=policy)
        == Decision.ALLOW
    )


def test_policy_requires_confirmation_for_interactive_destructive_tools(tmp_path):
    policy = ExecutionPolicy(headless=False, workspace_root=str(tmp_path))

    assert (
        decide_tool("shell", read_only=False, destructive=True, policy=policy)
        == Decision.DENY
    )
