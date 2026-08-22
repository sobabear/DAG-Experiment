"""Terminal research fixtures: CLI workspaces, verifiers, and reference fixes."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ...protocol import TaskSpec, VerifierResult
from ..process import _run_subprocess

Builder = Callable[[Path, bool], None]
Verifier = Callable[[Path], VerifierResult]

_T01_VERSION = "VERSION=2.4.1"
_T02_FEATURE_FLAG = "reports-v2"
_T02_LEVEL = "INFO"
_T02_FIXED_LOG_PATH = "logs/app.log"
_T07_SECRET = "n0t-for-disk"
_T08_LINE_COUNT = 2500
_T08_PEAK_LIMIT = 8000000
_T10_EXPECTED = (
    ("check_a", "PASS"),
    ("check_b", "FAIL"),
    ("check_c", "PASS"),
)


def materialize_terminal_task(task: TaskSpec, dest: Path) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    builder = _lookup(_BUILDERS, task)
    builder(dest, False)
    return dest


def apply_terminal_reference_fix(task: TaskSpec, workspace: Path) -> None:
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    builder = _lookup(_BUILDERS, task)
    builder(workspace, True)


def verify_terminal_task(task: TaskSpec, workspace: Path) -> VerifierResult:
    workspace = Path(workspace)
    verifier = _lookup(_VERIFIERS, task)
    return verifier(workspace)


def _lookup(table: Dict[str, Callable], task: TaskSpec) -> Callable:
    if task.task_id in table:
        return table[task.task_id]
    if task.verifier_name in table:
        return table[task.verifier_name]
    raise ValueError("unknown terminal task: {}".format(task.task_id))


def _write(dest: Path, relative: str, content: str) -> None:
    path = dest / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_bytes(dest: Path, relative: str, content: bytes) -> None:
    path = dest / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _remove(dest: Path, relative: str) -> None:
    path = dest / relative
    if path.is_file():
        path.unlink()


def _result(passed: bool, reason: str = "") -> VerifierResult:
    return VerifierResult(
        passed=passed,
        score=1.0 if passed else 0.0,
        reason=reason,
    )


def _fail_proc(prefix: str, proc) -> VerifierResult:
    reason = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return _result(False, prefix + reason[-4000:])


def _workspace_contains(workspace: Path, needle: str) -> bool:
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            text = blob.decode("utf-8", errors="ignore")
        if needle in text:
            return True
    return False


def _parse_kv(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _load_json(path: Path, label: str) -> Optional[object]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# terminal-01 broken build
# ---------------------------------------------------------------------------

_T01_BUILD_BROKEN = """\
from pathlib import Path


def main():
    Path("dist").mkdir(parents=True, exist_ok=True)
    Path("dist/app.txt").write_text("app\\nVERSION=0.0.0\\n", encoding="utf-8")


if __name__ == "__main__":
    main()
"""

_T01_BUILD_FIXED = """\
from pathlib import Path


def main():
    version = Path("version.txt").read_text(encoding="utf-8").strip()
    Path("dist").mkdir(parents=True, exist_ok=True)
    Path("dist/app.txt").write_text("app\\n{}\\n".format(version), encoding="utf-8")


if __name__ == "__main__":
    main()
"""

_T01_README = """\
# Ship CLI

Run `python3 build.py` to produce `dist/app.txt`.
The build must stamp the release identifier from `version.txt`.
"""

_T01_MAKEFILE = """\
all:
	python3 build.py
"""


def _build_t01(dest: Path, fixed: bool) -> None:
    _write(dest, "build.py", _T01_BUILD_FIXED if fixed else _T01_BUILD_BROKEN)
    _write(dest, "version.txt", _T01_VERSION + "\n")
    _write(dest, "README.md", _T01_README)
    _write(dest, "settings.json", '{"artifact": "dist/app.txt"}\n')
    _write(dest, "Makefile", _T01_MAKEFILE)


def _verify_t01(workspace: Path) -> VerifierResult:
    if not (workspace / "build.py").is_file():
        return _result(False, "build.py is missing")
    proc = _run_subprocess([sys.executable, "build.py"], workspace, 20.0)
    if proc.returncode != 0:
        return _fail_proc("build failed: ", proc)
    artifact = workspace / "dist" / "app.txt"
    if not artifact.is_file():
        return _result(False, "dist/app.txt was not generated")
    text = artifact.read_text(encoding="utf-8")
    if _T01_VERSION not in text:
        return _result(False, "artifact missing required version")
    return _result(True, "build ok")


# ---------------------------------------------------------------------------
# terminal-02 log config
# ---------------------------------------------------------------------------

_T02_README = """\
# Log shipper

`app.log` shows the runtime error. Correct `log_path` in `config.json`
so logs write under `logs/app.log`. Leave unrelated flags alone.
"""

_T02_APP = """\
import json
from pathlib import Path


def load_config():
    return json.loads(Path("config.json").read_text(encoding="utf-8"))
"""


def _t02_config(fixed: bool) -> str:
    payload = {
        "log_path": _T02_FIXED_LOG_PATH if fixed else "/wrong/dir",
        "feature_flag": _T02_FEATURE_FLAG,
        "level": _T02_LEVEL,
    }
    return json.dumps(payload, indent=2) + "\n"


def _build_t02(dest: Path, fixed: bool) -> None:
    _write(dest, "config.json", _t02_config(fixed))
    _write(dest, "app.log", "ERROR path=/wrong/dir\n")
    _write(dest, "README.md", _T02_README)
    _write(dest, "app.py", _T02_APP)


def _verify_t02(workspace: Path) -> VerifierResult:
    config = _load_json(workspace / "config.json", "config.json")
    if not isinstance(config, dict):
        return _result(False, "config.json missing or invalid")
    if config.get("log_path") != _T02_FIXED_LOG_PATH:
        return _result(False, "matching error path was not corrected")
    if config.get("feature_flag") != _T02_FEATURE_FLAG:
        return _result(False, "unrelated feature_flag changed")
    if config.get("level") != _T02_LEVEL:
        return _result(False, "unrelated level changed")
    return _result(True, "config ok")


# ---------------------------------------------------------------------------
# terminal-03 file transform
# ---------------------------------------------------------------------------

_T03_INPUTS = {
    "alpha.txt": "alpha one\n",
    "bravo.txt": "bravo two\n",
    "charlie.txt": "charlie three\n",
}

_T03_TRANSFORM_BROKEN = """\
import json
from pathlib import Path


def main():
    Path("manifest.json").write_text(
        json.dumps({"count": 0, "files": []}) + "\\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
"""

_T03_TRANSFORM_FIXED = """\
import json
from pathlib import Path


def main():
    inputs = Path("inputs")
    outputs = Path("outputs")
    outputs.mkdir(parents=True, exist_ok=True)
    names = []
    for path in sorted(inputs.glob("*.txt")):
        text = path.read_text(encoding="utf-8").upper()
        (outputs / path.name).write_text(text, encoding="utf-8")
        names.append(path.name)
    Path("manifest.json").write_text(
        json.dumps({"count": len(names), "files": names}) + "\\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
"""

_T03_README = """\
# Batch transform

Uppercase every `inputs/*.txt` file into `outputs/` with the same name.
Then write `manifest.json` with `count` and `files` matching the outputs.
Run `python3 transform.py`.
"""


def _build_t03(dest: Path, fixed: bool) -> None:
    _write(dest, "transform.py", _T03_TRANSFORM_FIXED if fixed else _T03_TRANSFORM_BROKEN)
    _write(dest, "README.md", _T03_README)
    _write(dest, "settings.json", '{"mode": "uppercase"}\n')
    for name, content in _T03_INPUTS.items():
        _write(dest, "inputs/" + name, content)
    names = sorted(_T03_INPUTS)
    if fixed:
        for name, content in _T03_INPUTS.items():
            _write(dest, "outputs/" + name, content.upper())
        _write(
            dest,
            "manifest.json",
            json.dumps({"count": len(names), "files": names}) + "\n",
        )
    else:
        for name in names:
            _remove(dest, "outputs/" + name)
        _write(dest, "manifest.json", json.dumps({"count": 0, "files": []}) + "\n")


def _verify_t03(workspace: Path) -> VerifierResult:
    required = sorted(_T03_INPUTS)
    inputs_dir = workspace / "inputs"
    outputs_dir = workspace / "outputs"
    if not inputs_dir.is_dir():
        return _result(False, "inputs directory missing")
    for name in required:
        path = inputs_dir / name
        if not path.is_file():
            return _result(False, "required input missing: {}".format(name))
    if not outputs_dir.is_dir():
        return _result(False, "outputs directory missing")
    for name in required:
        raw = (inputs_dir / name).read_text(encoding="utf-8")
        out_path = outputs_dir / name
        if not out_path.is_file():
            return _result(False, "transformed file missing: {}".format(name))
        got = out_path.read_text(encoding="utf-8")
        if got != raw.upper():
            return _result(False, "output not transformed: {}".format(name))
    manifest = _load_json(workspace / "manifest.json", "manifest.json")
    if not isinstance(manifest, dict):
        return _result(False, "manifest.json missing or invalid")
    files = manifest.get("files") or []
    count = manifest.get("count")
    if count != len(required):
        return _result(False, "manifest count mismatch")
    if sorted(files) != required:
        return _result(False, "manifest files mismatch")
    return _result(True, "transform ok")


# ---------------------------------------------------------------------------
# terminal-04 test triage
# ---------------------------------------------------------------------------

_T04_INGEST_BROKEN = """\
def ingest(line):
    return line
"""

_T04_INGEST_FIXED = """\
def ingest(line):
    return line.strip()
"""

_T04_EXPORT_BROKEN = """\
def export(item):
    return item
"""

_T04_TEST_INGEST = """\
from ingest import ingest


def test_ingest_trims():
    assert ingest("  alpha  ") == "alpha"
"""

_T04_TEST_EXPORT = """\
from export import export


def test_export_prefix():
    assert export("alpha") == "out:alpha"
"""

_T04_README = """\
# Ingest CLI

`pytest` reports failures in two groups. Fix the **ingest** group only.
Leave the unrelated export failures visible; do not "green" the whole suite.
"""


def _build_t04(dest: Path, fixed: bool) -> None:
    _write(dest, "ingest.py", _T04_INGEST_FIXED if fixed else _T04_INGEST_BROKEN)
    _write(dest, "export.py", _T04_EXPORT_BROKEN)
    _write(dest, "tests/test_ingest.py", _T04_TEST_INGEST)
    _write(dest, "tests/test_export.py", _T04_TEST_EXPORT)
    _write(dest, "README.md", _T04_README)
    _write(dest, "pytest.ini", "[pytest]\n")


def _verify_t04(workspace: Path) -> VerifierResult:
    ingest_script = (
        "from ingest import ingest\n"
        "assert ingest('  alpha  ') == 'alpha'\n"
        "assert ingest('  gamma\\t') == 'gamma'\n"
        "print('ok')\n"
    )
    ingest = _run_subprocess(
        [sys.executable, "-c", ingest_script],
        workspace,
        20.0,
    )
    if ingest.returncode != 0:
        return _fail_proc("ingest behavior failed: ", ingest)
    export_test = workspace / "tests" / "test_export.py"
    if not export_test.is_file():
        return _result(False, "tests/test_export.py missing")
    export_src = export_test.read_text(encoding="utf-8")
    if 'export("alpha") == "out:alpha"' not in export_src.replace("'", '"'):
        return _result(False, "export tests lost original failing assertion")
    export_script = (
        "from export import export\n"
        "value = export('alpha')\n"
        "assert value != 'out:alpha', 'unrelated export was fixed'\n"
        "print('still-failing')\n"
    )
    export = _run_subprocess(
        [sys.executable, "-c", export_script],
        workspace,
        20.0,
    )
    if export.returncode != 0:
        return _fail_proc("unrelated export failures must remain visible: ", export)
    return _result(True, "ingest fixed; export still failing")


# ---------------------------------------------------------------------------
# terminal-05 timeout restart
# ---------------------------------------------------------------------------

_T05_WORKER_BROKEN = """\
from pathlib import Path


def main():
    Path("restart.marker").write_text("attempt=1\\n", encoding="utf-8")


if __name__ == "__main__":
    main()
"""

_T05_WORKER_FIXED = """\
from pathlib import Path


def main():
    Path("restart.marker").write_text(
        "timeout_handled=1\\nattempt=2\\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
"""

_T05_README = """\
# Worker watchdog

`worker.py` stalls on the first attempt. Handle the timeout, then restart.
Record the handled timeout and the second attempt in `restart.marker`.
A single successful run without timeout+restart is not enough.
"""


def _build_t05(dest: Path, fixed: bool) -> None:
    _write(dest, "worker.py", _T05_WORKER_FIXED if fixed else _T05_WORKER_BROKEN)
    _write(dest, "README.md", _T05_README)
    _write(dest, "config.ini", "[worker]\ntimeout_seconds = 5\n")
    _write(dest, "watchdog.py", "def should_restart(attempt):\n    return attempt == 2\n")
    if fixed:
        _write(dest, "restart.marker", "timeout_handled=1\nattempt=2\n")
    else:
        _remove(dest, "restart.marker")


def _verify_t05(workspace: Path) -> VerifierResult:
    marker = workspace / "restart.marker"
    if not marker.is_file():
        return _result(False, "restart.marker missing")
    values = _parse_kv(marker.read_text(encoding="utf-8"))
    handled = values.get("timeout_handled", "").lower()
    if handled not in ("1", "true", "yes"):
        return _result(False, "timeout was not handled")
    if values.get("attempt") != "2":
        return _result(False, "second attempt was not recorded")
    return _result(True, "restart ok")


# ---------------------------------------------------------------------------
# terminal-06 checksum artifact
# ---------------------------------------------------------------------------

_T06_PAYLOAD = b"terminal-checksum-payload-v1\n" + bytes(range(256))

_T06_COMPUTE = """\
from pathlib import Path


def digest_file(path):
    raise NotImplementedError("compute the SHA-256 hex digest")
"""

_T06_README = """\
# Artifact checksum

`data.bin` is the payload. Compute its SHA-256 hex digest and write the
stripped digest to `answer.txt`. Do not put the digest in any other file.
"""


def _build_t06(dest: Path, fixed: bool) -> None:
    if not (dest / "data.bin").is_file():
        _write_bytes(dest, "data.bin", _T06_PAYLOAD)
    _write(dest, "compute.py", _T06_COMPUTE)
    _write(dest, "README.md", _T06_README)
    _write(dest, "notes.txt", "Write the hex digest to answer.txt only.\n")
    if fixed:
        digest = hashlib.sha256((dest / "data.bin").read_bytes()).hexdigest()
        _write(dest, "answer.txt", digest + "\n")
    else:
        _remove(dest, "answer.txt")


def _verify_t06(workspace: Path) -> VerifierResult:
    payload = workspace / "data.bin"
    answer = workspace / "answer.txt"
    if not payload.is_file():
        return _result(False, "data.bin missing")
    if not answer.is_file():
        return _result(False, "answer.txt missing")
    expected = hashlib.sha256(payload.read_bytes()).hexdigest()
    got = answer.read_text(encoding="utf-8").strip()
    if got != expected:
        return _result(False, "checksum mismatch")
    return _result(True, "checksum ok")


# ---------------------------------------------------------------------------
# terminal-07 env diagnosis
# ---------------------------------------------------------------------------

_T07_RUN_BROKEN = """\
import sys

sys.stderr.write("ERROR APP_TOKEN is required\\n")
raise SystemExit(1)
"""

_T07_RUN_FIXED = """\
import os
import sys

if not os.environ.get("APP_TOKEN"):
    sys.stderr.write("ERROR APP_TOKEN is required\\n")
    raise SystemExit(1)
print("ok")
"""

_T07_README = """\
# Env doctor

`run.py` fails until the missing variable named in `app.log` is supplied
at runtime. Diagnose the missing name in `status.txt`. Never write secret
token values to disk; export via the environment at run time.
"""


def _build_t07(dest: Path, fixed: bool) -> None:
    _write(dest, "run.py", _T07_RUN_FIXED if fixed else _T07_RUN_BROKEN)
    _write(dest, "README.md", _T07_README)
    _write(dest, "NOTES.txt", "Never write the token to disk.\n")
    _write(dest, ".env.example", "APP_TOKEN=\n")
    _write(dest, "app.log", "ERROR APP_TOKEN is required\n")
    _write(dest, "settings.json", '{"required": ["APP_TOKEN"]}\n')
    if fixed:
        _write(dest, "status.txt", "diagnosed missing variable APP_TOKEN\n")
        _write(dest, "env.sh", "APP_TOKEN=${APP_TOKEN}\n")
    else:
        _remove(dest, "status.txt")
        _remove(dest, "env.sh")


def _verify_t07(workspace: Path) -> VerifierResult:
    status = workspace / "status.txt"
    if not status.is_file():
        return _result(False, "status.txt missing")
    if "APP_TOKEN" not in status.read_text(encoding="utf-8"):
        return _result(False, "missing variable not diagnosed")
    if _workspace_contains(workspace, _T07_SECRET):
        return _result(False, "secret value written to workspace")
    if not (workspace / "run.py").is_file():
        return _result(False, "run.py missing")
    proc = _run_subprocess(
        [sys.executable, "run.py"],
        workspace,
        20.0,
        extra_env={"APP_TOKEN": _T07_SECRET},
    )
    if proc.returncode != 0:
        return _fail_proc("run.py failed with token supplied: ", proc)
    if _workspace_contains(workspace, _T07_SECRET):
        return _result(False, "secret value written to workspace")
    return _result(True, "env diagnosed")


# ---------------------------------------------------------------------------
# terminal-08 stream large file
# ---------------------------------------------------------------------------

_T08_SUMMARIZE_BROKEN = """\
from pathlib import Path


def main():
    text = Path("large.log").read_text(encoding="utf-8")
    Path("summary.txt").write_text("count=0\\n", encoding="utf-8")
    Path("peak_memory.txt").write_text("999999999\\n", encoding="utf-8")
    return text


if __name__ == "__main__":
    main()
"""

_T08_SUMMARIZE_FIXED = """\
from pathlib import Path


def main():
    count = 0
    with Path("large.log").open(encoding="utf-8") as handle:
        for _line in handle:
            count += 1
    Path("summary.txt").write_text("count={}\\n".format(count), encoding="utf-8")
    Path("peak_memory.txt").write_text("4096\\n", encoding="utf-8")


if __name__ == "__main__":
    main()
"""

_T08_README = """\
# Log summarizer

`large.log` is too big to load carelessly. Stream it line-by-line, write
`summary.txt` with the line count, and record a peak-memory marker in
`peak_memory.txt` while producing complete output.
"""


def _build_t08(dest: Path, fixed: bool) -> None:
    lines = ["event-{:04d} payload\n".format(i) for i in range(_T08_LINE_COUNT)]
    _write(dest, "large.log", "".join(lines))
    _write(dest, "summarize.py", _T08_SUMMARIZE_FIXED if fixed else _T08_SUMMARIZE_BROKEN)
    _write(dest, "README.md", _T08_README)
    _write(dest, "settings.json", '{"stream": true}\n')
    if fixed:
        _write(dest, "summary.txt", "count={}\n".format(_T08_LINE_COUNT))
        _write(dest, "peak_memory.txt", "4096\n")
    else:
        _remove(dest, "summary.txt")
        _remove(dest, "peak_memory.txt")


def _verify_t08(workspace: Path) -> VerifierResult:
    log_path = workspace / "large.log"
    summary = workspace / "summary.txt"
    peak_path = workspace / "peak_memory.txt"
    if not log_path.is_file():
        return _result(False, "large.log missing")
    if not summary.is_file():
        return _result(False, "summary.txt missing")
    if not peak_path.is_file():
        return _result(False, "peak_memory.txt missing")
    actual_lines = len(log_path.read_text(encoding="utf-8").splitlines())
    if actual_lines != _T08_LINE_COUNT:
        return _result(False, "large.log line count changed")
    text = summary.read_text(encoding="utf-8")
    if "count={}".format(_T08_LINE_COUNT) not in text:
        return _result(False, "summary count incomplete")
    try:
        peak = int(peak_path.read_text(encoding="utf-8").strip().split()[0])
    except (ValueError, IndexError, OSError):
        return _result(False, "peak_memory.txt invalid")
    if peak >= _T08_PEAK_LIMIT:
        return _result(False, "peak memory above limit")
    return _result(True, "stream ok")


# ---------------------------------------------------------------------------
# terminal-09 rollback rerun
# ---------------------------------------------------------------------------

_T09_DEPLOY_BROKEN = """\
from pathlib import Path
import json


def main():
    Path("broken.flag").write_text("partial-deploy\\n", encoding="utf-8")
    Path("state.json").write_text(
        json.dumps({"status": "partial", "revision": 1}) + "\\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
"""

_T09_DEPLOY_FIXED = """\
from pathlib import Path
import json


def main():
    flag = Path("broken.flag")
    if flag.exists():
        flag.unlink()
    Path("state.json").write_text(
        json.dumps({"status": "ok", "revision": 2}) + "\\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
"""

_T09_README = """\
# Deploy rollback

The last `python3 deploy.py` run left partial state. Roll back the failed
mutation, then rerun so `state.json` reflects a successful completion.
"""


def _build_t09(dest: Path, fixed: bool) -> None:
    _write(dest, "deploy.py", _T09_DEPLOY_FIXED if fixed else _T09_DEPLOY_BROKEN)
    _write(dest, "README.md", _T09_README)
    _write(dest, "deploy.ini", "[deploy]\nrevision = 2\n")
    if fixed:
        _remove(dest, "broken.flag")
        _write(dest, "state.json", json.dumps({"status": "ok", "revision": 2}) + "\n")
    else:
        _write(dest, "broken.flag", "partial-deploy\n")
        _write(
            dest,
            "state.json",
            json.dumps({"status": "partial", "revision": 1}) + "\n",
        )


def _verify_t09(workspace: Path) -> VerifierResult:
    if (workspace / "broken.flag").exists():
        return _result(False, "failed mutation was not rolled back")
    state = _load_json(workspace / "state.json", "state.json")
    if not isinstance(state, dict):
        return _result(False, "state.json missing or invalid")
    if state.get("status") != "ok":
        return _result(False, "successful rerun state missing")
    return _result(True, "rollback ok")


# ---------------------------------------------------------------------------
# terminal-10 parallel checks
# ---------------------------------------------------------------------------

_T10_CHECK_A = 'print("PASS")\n'
_T10_CHECK_B = 'print("FAIL")\n'
_T10_CHECK_C = 'print("PASS")\n'

_T10_README = """\
# Parallel checks

Run `checks/check_a.py`, `checks/check_b.py`, and `checks/check_c.py`.
Write each outcome to `results/check_a.txt` (and b, c) and merge them
into `summary.txt` with the correct aggregate status. Do not edit the
check scripts.
"""


def _build_t10(dest: Path, fixed: bool) -> None:
    _write(dest, "checks/check_a.py", _T10_CHECK_A)
    _write(dest, "checks/check_b.py", _T10_CHECK_B)
    _write(dest, "checks/check_c.py", _T10_CHECK_C)
    _write(dest, "README.md", _T10_README)
    _write(dest, "settings.json", '{"checks": ["a", "b", "c"]}\n')
    if fixed:
        _write(dest, "results/check_a.txt", "PASS\n")
        _write(dest, "results/check_b.txt", "FAIL\n")
        _write(dest, "results/check_c.txt", "PASS\n")
        _write(dest, "summary.txt", "aggregate=FAIL\n")
    else:
        for name in ("check_a", "check_b", "check_c"):
            _remove(dest, "results/{}.txt".format(name))
        _remove(dest, "summary.txt")


def _verify_t10(workspace: Path) -> VerifierResult:
    results_dir = workspace / "results"
    statuses: List[str] = []
    for name, expected in _T10_EXPECTED:
        path = results_dir / "{}.txt".format(name)
        if not path.is_file():
            return _result(False, "{} missing".format(path.name))
        got = path.read_text(encoding="utf-8").strip()
        if got != expected:
            return _result(False, "{} expected {} got {}".format(name, expected, got))
        statuses.append(got)
    summary_path = workspace / "summary.txt"
    if not summary_path.is_file():
        return _result(False, "summary.txt missing")
    summary = summary_path.read_text(encoding="utf-8").replace(" ", "")
    expected_agg = "FAIL" if "FAIL" in statuses else "PASS"
    if "aggregate={}".format(expected_agg) not in summary:
        return _result(False, "aggregate status incorrect")
    return _result(True, "checks ok")


_BUILDERS = {
    "terminal-01-broken-build": _build_t01,
    "broken_build": _build_t01,
    "terminal-02-log-config": _build_t02,
    "log_config": _build_t02,
    "terminal-03-file-transform": _build_t03,
    "file_transform": _build_t03,
    "terminal-04-test-triage": _build_t04,
    "test_triage": _build_t04,
    "terminal-05-timeout-restart": _build_t05,
    "timeout_restart": _build_t05,
    "terminal-06-checksum-artifact": _build_t06,
    "checksum_artifact": _build_t06,
    "terminal-07-env-diagnosis": _build_t07,
    "env_diagnosis": _build_t07,
    "terminal-08-stream-large-file": _build_t08,
    "stream_large_file": _build_t08,
    "terminal-09-rollback-rerun": _build_t09,
    "rollback_rerun": _build_t09,
    "terminal-10-parallel-checks": _build_t10,
    "parallel_checks": _build_t10,
}

_VERIFIERS = {
    "terminal-01-broken-build": _verify_t01,
    "broken_build": _verify_t01,
    "terminal-02-log-config": _verify_t02,
    "log_config": _verify_t02,
    "terminal-03-file-transform": _verify_t03,
    "file_transform": _verify_t03,
    "terminal-04-test-triage": _verify_t04,
    "test_triage": _verify_t04,
    "terminal-05-timeout-restart": _verify_t05,
    "timeout_restart": _verify_t05,
    "terminal-06-checksum-artifact": _verify_t06,
    "checksum_artifact": _verify_t06,
    "terminal-07-env-diagnosis": _verify_t07,
    "env_diagnosis": _verify_t07,
    "terminal-08-stream-large-file": _verify_t08,
    "stream_large_file": _verify_t08,
    "terminal-09-rollback-rerun": _verify_t09,
    "rollback_rerun": _verify_t09,
    "terminal-10-parallel-checks": _verify_t10,
    "parallel_checks": _verify_t10,
}
