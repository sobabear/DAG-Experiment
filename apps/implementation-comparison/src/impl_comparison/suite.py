"""Fallback SE / Terminal / Q&A suite. Not the public Artificial Analysis benches."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

from .protocol import TaskSpec, VerifierResult

SUITE_ID = "fallback-se-terminal-qna"
SUITE_DISCLAIMER = (
    "자체 스위트 · Artificial Analysis Index와 수치 직접 비교 불가"
)

FALLBACK_TASKS: List[TaskSpec] = [
    TaskSpec(
        task_id="se-add",
        benchmark="deepswe",
        prompt=(
            "The function add.py is wrong. Make add(a, b) return a + b. "
            "Keep test_add.py passing."
        ),
        description="Fix a one-line arithmetic bug (SE analog of DeepSWE).",
        verifier="pytest tests/test_add.py",
        timeout=60.0,
    ),
    TaskSpec(
        task_id="terminal-hash",
        benchmark="terminal_bench_v2",
        prompt=(
            "Run `python3 compute.py` in this workspace and write its stdout "
            "(the sha256 hex digest only) to answer.txt."
        ),
        description="Agentic terminal use analog of Terminal-Bench v2.",
        verifier="answer.txt matches sha256(data.txt)",
        timeout=60.0,
    ),
    TaskSpec(
        task_id="qna-token",
        benchmark="swe_atlas_qna",
        prompt=(
            "Read the repository notes and write the project token to answer.txt. "
            "Output only the token."
        ),
        description="Technical Q&A analog of SWE-Atlas-QnA.",
        verifier="answer.txt == ALPHA-42",
        timeout=60.0,
    ),
]


def materialize_task(task: TaskSpec, dest: Path) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if task.task_id == "se-add":
        (dest / "add.py").write_text(
            "def add(a, b):\n    return a - b\n", encoding="utf-8"
        )
        (dest / "test_add.py").write_text(
            "from add import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            encoding="utf-8",
        )
    elif task.task_id == "terminal-hash":
        (dest / "data.txt").write_text("payload-xyz\n", encoding="utf-8")
        (dest / "compute.py").write_text(
            "import hashlib\n"
            "import pathlib\n"
            "print(hashlib.sha256(pathlib.Path('data.txt').read_bytes()).hexdigest())\n",
            encoding="utf-8",
        )
    elif task.task_id == "qna-token":
        (dest / "NOTES.md").write_text(
            "Project notes.\nThe project token is ALPHA-42.\n",
            encoding="utf-8",
        )
    else:
        raise ValueError("unknown task: {}".format(task.task_id))
    return dest


def verify_task(task: TaskSpec, workspace: Path) -> VerifierResult:
    workspace = Path(workspace)
    if task.task_id == "se-add":
        env = dict(__import__("os").environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        cache = workspace / "__pycache__"
        if cache.is_dir():
            shutil.rmtree(cache)
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from add import add; assert add(2, 3) == 5",
            ],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        passed = proc.returncode == 0
        return VerifierResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=(proc.stdout or "") + (proc.stderr or ""),
        )
    if task.task_id == "terminal-hash":
        expected = hashlib.sha256((workspace / "data.txt").read_bytes()).hexdigest()
        answer = _read_answer(workspace)
        passed = answer == expected
        return VerifierResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="expected {} got {}".format(expected, answer or "<missing>"),
        )
    if task.task_id == "qna-token":
        answer = _read_answer(workspace)
        passed = answer == "ALPHA-42"
        return VerifierResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="expected ALPHA-42 got {}".format(answer or "<missing>"),
        )
    raise ValueError("unknown task: {}".format(task.task_id))


def verify_run(request, system_result, artifact_dir) -> VerifierResult:
    return verify_task(request.task, request.workspace)


def iter_tasks() -> Iterable[TaskSpec]:
    return list(FALLBACK_TASKS)


def _read_answer(workspace: Path) -> str:
    path = workspace / "answer.txt"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()
