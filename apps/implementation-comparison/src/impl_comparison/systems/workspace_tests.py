"""Run workspace pytest for DAG force-test / repair nodes."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from ..research_tasks.process import _run_subprocess


def _discover_test_files(workspace: Path) -> List[str]:
    workspace = Path(workspace)
    found: List[str] = []
    for path in sorted(workspace.glob("test_*.py")):
        if path.is_file():
            found.append(path.name)
    tests_dir = workspace / "tests"
    if tests_dir.is_dir():
        for path in sorted(tests_dir.glob("test_*.py")):
            if path.is_file():
                found.append(path.relative_to(workspace).as_posix())
    return found


def run_workspace_pytest(workspace, timeout: float = 20.0) -> str:
    workspace = Path(workspace)
    test_files = _discover_test_files(workspace)
    if not test_files:
        return "no tests"
    proc = _run_subprocess(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--rootdir",
            str(workspace),
        ]
        + test_files,
        workspace,
        timeout,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        if "FAILED" not in output:
            return "FAILED\n" + output
        return output
    return "passed"
