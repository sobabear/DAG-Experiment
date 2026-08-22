"""Shared subprocess helpers for research-task verifiers."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

_VERIFIER_HOME = ".verifier-home"
_VERIFIER_TMP = ".verifier-tmp"


def _child_env(workspace: Path) -> Dict[str, str]:
    workspace = Path(workspace)
    env: Dict[str, str] = {
        "PYTHONPATH": str(workspace),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": str(workspace / _VERIFIER_HOME),
        "TMPDIR": str(workspace / _VERIFIER_TMP),
    }
    path = os.environ.get("PATH")
    env["PATH"] = path if path else "/usr/bin:/bin"
    for key in ("LANG", "LC_ALL"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def _prepare_workspace(workspace: Path) -> None:
    workspace = Path(workspace)
    cache = workspace / "__pycache__"
    if cache.is_dir():
        shutil.rmtree(cache)
    (workspace / _VERIFIER_HOME).mkdir(parents=True, exist_ok=True)
    (workspace / _VERIFIER_TMP).mkdir(parents=True, exist_ok=True)


def _run_subprocess(
    args: List[str],
    workspace: Path,
    timeout: float,
    extra_env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    workspace = Path(workspace)
    env = _child_env(workspace)
    if extra_env:
        env.update(extra_env)
        env["PYTHONPATH"] = str(workspace)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        _prepare_workspace(workspace)
        return subprocess.run(
            args,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            args=list(args),
            returncode=124,
            stdout="",
            stderr="timeout after {}s: {}".format(timeout, exc),
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            args=list(args),
            returncode=127,
            stdout="",
            stderr="os error: {}".format(exc),
        )
