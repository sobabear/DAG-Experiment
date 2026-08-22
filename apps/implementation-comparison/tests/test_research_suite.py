import ast
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

import pytest

from impl_comparison.research_suite import (
    apply_reference_fix,
    materialize_task,
    research_tasks,
    verify_task,
)

VALID_AREAS = {"se", "terminal", "qna"}

EXPECTED_TASK_IDS = [
    "se-01-multifile-bug",
    "se-02-api-migration",
    "se-03-schema-migration",
    "se-04-race-condition",
    "se-05-cache-invalidation",
    "se-06-retry-timeout",
    "se-07-auth-path-security",
    "se-08-hidden-edge-case",
    "se-09-coupling-refactor",
    "se-10-performance-bottleneck",
    "terminal-01-broken-build",
    "terminal-02-log-config",
    "terminal-03-file-transform",
    "terminal-04-test-triage",
    "terminal-05-timeout-restart",
    "terminal-06-checksum-artifact",
    "terminal-07-env-diagnosis",
    "terminal-08-stream-large-file",
    "terminal-09-rollback-rerun",
    "terminal-10-parallel-checks",
    "qna-01-call-graph",
    "qna-02-config-impact",
    "qna-03-root-cause",
    "qna-04-change-impact",
    "qna-05-security-path",
    "qna-06-test-gap",
    "qna-07-performance-location",
    "qna-08-state-flow",
    "qna-09-recovery-path",
    "qna-10-architecture-tradeoff",
]

EXPECTED_TIMEOUTS = {
    "se": 90.0,
    "terminal": 120.0,
    "qna": 60.0,
}

EXPECTED_BENCHMARKS = {
    "se": "deepswe",
    "terminal": "terminal_bench_v2",
    "qna": "swe_atlas_qna",
}

_COUNTED_SUFFIXES = {".py", ".json", ".toml", ".cfg", ".ini", ".txt", ".md"}


TERMINAL_TASK_IDS = EXPECTED_TASK_IDS[10:20]
QNA_TASK_IDS = EXPECTED_TASK_IDS[20:30]

TERMINAL_PRIMARY_ARTIFACTS = {
    "terminal-01-broken-build": "build.py",
    "terminal-02-log-config": "config.json",
    "terminal-03-file-transform": "manifest.json",
    "terminal-04-test-triage": "ingest.py",
    "terminal-05-timeout-restart": "restart.marker",
    "terminal-06-checksum-artifact": "answer.txt",
    "terminal-07-env-diagnosis": "status.txt",
    "terminal-08-stream-large-file": "summary.txt",
    "terminal-09-rollback-rerun": "state.json",
    "terminal-10-parallel-checks": "results/check_a.txt",
}

_OPERATIONAL_TERMS = (
    "command",
    "shell",
    "log",
    "file",
    "build",
    "test",
    "checksum",
    "env",
    "stream",
    "rollback",
    "roll back",
    "parallel",
    "timeout",
    "restart",
    "rerun",
    "config",
    "transform",
    "process",
    "check",
    "artifact",
)


def _se_tasks():
    return [task for task in research_tasks() if task.area == "se"]


def _terminal_tasks():
    return [task for task in research_tasks() if task.area == "terminal"]


def _qna_tasks():
    return [task for task in research_tasks() if task.area == "qna"]


def _task(task_id):
    return next(task for task in research_tasks() if task.task_id == task_id)


def _parse_labeled_answer(text):
    pairs = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key:
            pairs.append((key, value))
    return pairs


def _format_labeled_answer(pairs):
    return "".join("{}: {}\n".format(key, value) for key, value in pairs)


def _looks_like_path(value):
    lowered = value.replace("\\", "/").lower()
    if "/" in lowered:
        return True
    return lowered.endswith((".py", ".md", ".json", ".txt", ".cfg", ".ini", ".toml"))


def _is_answer_path_field(key):
    if key in {"attack_input", "retry_path", "rollback_path", "hot_path"}:
        return False
    return key.endswith("_path") or key.endswith("_file")


def _rewrite_answer(path, updates):
    pairs = _parse_labeled_answer(path.read_text(encoding="utf-8"))
    rewritten = []
    for key, value in pairs:
        rewritten.append((key, updates.get(key, value)))
    path.write_text(_format_labeled_answer(rewritten), encoding="utf-8")


def _imported_module_names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name.split(".")[0])
    return names


def _linked_python_component_size(root):
    files = [
        path
        for path in Path(root).rglob("*.py")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    by_stem = {}
    for path in files:
        by_stem.setdefault(path.stem, []).append(path)
    adj = {path: set() for path in files}
    for path in files:
        for name in _imported_module_names(path):
            for other in by_stem.get(name, []):
                if other != path:
                    adj[path].add(other)
                    adj[other].add(path)
    seen = set()
    best = 0
    for start in files:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        size = 0
        while stack:
            node = stack.pop()
            size += 1
            for neighbor in adj[node]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        if size > best:
            best = size
    return files, best


def _hidden_gold_identifiers(pairs):
    names = []
    for key, value in pairs:
        if _looks_like_path(value):
            continue
        if value.isidentifier() and "_" in value:
            names.append(value)
    return names


def _counted_files(root):
    files = []
    for path in Path(root).rglob("*"):
        if "__pycache__" in path.parts:
            continue
        if path.is_file() and path.suffix.lower() in _COUNTED_SUFFIXES:
            files.append(path)
    return files


def test_research_suite_has_exactly_thirty_unique_tasks():
    tasks = research_tasks()
    assert len(tasks) == 30
    assert len({task.task_id for task in tasks}) == 30
    assert Counter(task.area for task in tasks) == {
        "se": 10,
        "terminal": 10,
        "qna": 10,
    }


def test_research_tasks_have_required_fields():
    tasks = research_tasks()
    for task in tasks:
        assert task.prompt.strip(), f"{task.task_id} has empty prompt"
        assert task.timeout > 0, f"{task.task_id} has invalid timeout"
        assert task.area in VALID_AREAS, f"{task.task_id} has invalid area: {task.area}"
        assert task.verifier_name.strip(), (
            f"{task.task_id} has empty verifier_name"
        )


def test_research_task_ids_match_canonical_order():
    assert [task.task_id for task in research_tasks()] == EXPECTED_TASK_IDS


def test_research_tasks_use_area_timeouts_and_benchmarks():
    for task in research_tasks():
        assert task.timeout == EXPECTED_TIMEOUTS[task.area], task.task_id
        assert task.benchmark == EXPECTED_BENCHMARKS[task.area], task.task_id


def test_verify_task_signature_ignores_claimed_text():
    params = inspect.signature(verify_task).parameters
    assert list(params) == ["task", "workspace"]
    assert "final_text" not in params
    assert "kwargs" not in params


def test_se_fixtures_materialize_at_least_three_files(tmp_path):
    se_tasks = _se_tasks()
    assert len(se_tasks) == 10
    for task in se_tasks:
        dest_a = tmp_path / task.task_id / "a"
        dest_b = tmp_path / task.task_id / "b"
        out_a = materialize_task(task, dest_a)
        out_b = materialize_task(task, dest_b)
        assert Path(out_a).resolve() == dest_a.resolve()
        assert Path(out_b).resolve() == dest_b.resolve()
        files_a = _counted_files(dest_a)
        files_b = _counted_files(dest_b)
        assert len(files_a) >= 3, task.task_id
        assert len(files_b) >= 3, task.task_id
        marker = dest_a / "isolation-marker.txt"
        marker.write_text("only-a", encoding="utf-8")
        assert not (dest_b / "isolation-marker.txt").is_file()
        py_files = [path for path in files_a if path.suffix == ".py"]
        assert py_files, task.task_id
        original = py_files[0].read_text(encoding="utf-8")
        py_files[0].write_text(original + "\n# mutated\n", encoding="utf-8")
        relative = py_files[0].relative_to(dest_a)
        assert "# mutated" not in (dest_b / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("task_id", EXPECTED_TASK_IDS[:10])
def test_se_broken_fixture_fails_verifier(task_id, tmp_path):
    task = _task(task_id)
    workspace = materialize_task(task, tmp_path / task_id)
    result = verify_task(task, workspace)
    assert result.passed is False, (task_id, result.reason)


@pytest.mark.parametrize("task_id", EXPECTED_TASK_IDS[:10])
def test_se_corrected_fixture_passes_verifier(task_id, tmp_path):
    task = _task(task_id)
    workspace = materialize_task(task, tmp_path / task_id)
    apply_reference_fix(task, workspace)
    result = verify_task(task, workspace)
    assert result.passed is True, (task_id, result.reason)


def test_se_verifiers_ignore_claimed_success_text(tmp_path):
    for task in _se_tasks():
        workspace = materialize_task(task, tmp_path / task.task_id)
        (workspace / "answer.txt").write_text("ALL TESTS PASSED", encoding="utf-8")
        (workspace / "SUCCESS").write_text("I did it", encoding="utf-8")
        (workspace / "I_PASSED.txt").write_text("passed=True", encoding="utf-8")
        result = verify_task(task, workspace)
        assert result.passed is False, task.task_id


def test_se01_service_only_fix_does_not_satisfy_hidden_cli(tmp_path):
    task = _task("se-01-multifile-bug")
    workspace = materialize_task(task, tmp_path)
    (workspace / "service.py").write_text(
        "def parse_request(line):\n"
        "    tokens = []\n"
        "    current = []\n"
        "    in_quote = False\n"
        "    for ch in line:\n"
        "        if ch == '\"':\n"
        "            in_quote = not in_quote\n"
        "        elif ch == ' ' and not in_quote:\n"
        "            if current:\n"
        "                tokens.append(''.join(current))\n"
        "                current = []\n"
        "        else:\n"
        "            current.append(ch)\n"
        "    if current:\n"
        "        tokens.append(''.join(current))\n"
        "    return tokens\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False


def test_se02_shim_without_migrating_callers_fails(tmp_path):
    task = _task("se-02-api-migration")
    workspace = materialize_task(task, tmp_path)
    users = (workspace / "users.py").read_text(encoding="utf-8")
    if "def fetch_user" not in users:
        (workspace / "users.py").write_text(
            users + "\n\ndef fetch_user(user_id):\n    return get_user(user_id)\n",
            encoding="utf-8",
        )
    result = verify_task(task, workspace)
    assert result.passed is False


def test_se08_visible_tests_do_not_disclose_hidden_cases(tmp_path):
    task = _task("se-08-hidden-edge-case")
    workspace = materialize_task(task, tmp_path)
    visible = []
    for path in workspace.rglob("test_*.py"):
        visible.append(path.read_text(encoding="utf-8").lower())
    blob = "\n".join(visible)
    for needle in ("unicode", "empty", "negative", "max_label", "64"):
        assert needle not in blob, needle


def test_se09_keeping_global_dict_fails_even_if_outputs_match(tmp_path):
    task = _task("se-09-coupling-refactor")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    extra = (workspace / "alpha.py").read_text(encoding="utf-8")
    (workspace / "alpha.py").write_text(
        extra + "\nGLOBAL = {}\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False


def test_se_prompts_do_not_contain_reference_fix(tmp_path):
    for task in _se_tasks():
        prompt = task.prompt.lower()
        assert "apply_reference_fix" not in prompt
        assert "hidden verifier" not in prompt
        workspace = materialize_task(task, tmp_path / task.task_id)
        readme = workspace / "README.md"
        if readme.is_file():
            text = readme.read_text(encoding="utf-8").lower()
            assert "apply_reference_fix" not in text
        tree = []
        for path in workspace.rglob("*.py"):
            tree.append(ast.parse(path.read_text(encoding="utf-8")))
        assert tree


def test_se05_broken_update_leaves_primary_stale(tmp_path):
    """Broken update must keep serving the old name from the key cache."""
    task = _task("se-05-cache-invalidation")
    workspace = materialize_task(task, tmp_path)
    import os
    import subprocess
    import sys

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(workspace)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from catalog import Catalog\n"
            "c = Catalog()\n"
            "c.add('p1', 'alpha')\n"
            "c.update('p1', 'beta')\n"
            "print(c.get('p1'))\n",
        ],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "alpha"


def test_se05_derived_only_patch_fails_verifier(tmp_path):
    task = _task("se-05-cache-invalidation")
    workspace = materialize_task(task, tmp_path)
    (workspace / "catalog.py").write_text(
        "class Catalog(object):\n"
        "    def __init__(self):\n"
        "        self._items = {}\n"
        "        self._primary = {}\n"
        "        self._by_name = {}\n"
        "\n"
        "    def add(self, item_id, name):\n"
        "        self._items[item_id] = name\n"
        "        self._primary[item_id] = name\n"
        "        self._by_name[name] = item_id\n"
        "\n"
        "    def update(self, item_id, name):\n"
        "        old = self._items.get(item_id)\n"
        "        self._items[item_id] = name\n"
        "        if old is not None:\n"
        "            self._by_name.pop(old, None)\n"
        "        self._by_name[name] = item_id\n"
        "\n"
        "    def get(self, item_id):\n"
        "        if item_id in self._primary:\n"
        "            return self._primary[item_id]\n"
        "        return self._items.get(item_id)\n"
        "\n"
        "    def find_id(self, name):\n"
        "        return self._by_name.get(name)\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False


def test_se09_unused_shared_import_with_duplicated_bodies_fails(tmp_path):
    task = _task("se-09-coupling-refactor")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "alpha.py").write_text(
        "from shared import label\n"
        "\n"
        "\n"
        "def public_a(n):\n"
        "    return \"item-{}\".format(n)\n",
        encoding="utf-8",
    )
    (workspace / "beta.py").write_text(
        "from shared import label\n"
        "\n"
        "\n"
        "def public_b(n):\n"
        "    return \"item-{}\".format(n * 2)\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False


def test_se01_hardcoded_quoted_sample_fails_verifier(tmp_path):
    task = _task("se-01-multifile-bug")
    workspace = materialize_task(task, tmp_path)
    (workspace / "parser.py").write_text(
        "def parse(line):\n"
        "    if line == 'cmd \"hello world\" extra':\n"
        "        return ['cmd', 'hello world', 'extra']\n"
        "    return [part for part in line.split() if part]\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False


def test_se10_returning_needles_fails_verifier(tmp_path):
    task = _task("se-10-performance-bottleneck")
    workspace = materialize_task(task, tmp_path)
    (workspace / "search.py").write_text(
        "def find_matching(haystack, needles):\n"
        "    return list(needles)\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False


def test_assert_script_timeout_returns_failed_result(tmp_path):
    from impl_comparison.research_tasks.se.tasks import _assert_script

    result = _assert_script(tmp_path, "import time\ntime.sleep(5)\n", timeout=0.2)
    assert result.passed is False
    assert "timeout" in result.reason.lower()


def test_child_env_omits_planted_host_secrets(monkeypatch, tmp_path):
    host_home = tmp_path / "host-home"
    host_tmp = tmp_path / "host-tmp"
    host_home.mkdir()
    host_tmp.mkdir()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("IMPL_COMPARISON_SECRET_PROBE", "leak-me")
    monkeypatch.setenv("HOME", str(host_home))
    monkeypatch.setenv("TMPDIR", str(host_tmp))
    from impl_comparison.research_tasks.process import _child_env

    env = _child_env(tmp_path)
    assert "OPENAI_API_KEY" not in env
    assert "IMPL_COMPARISON_SECRET_PROBE" not in env
    assert env["PYTHONPATH"] == str(tmp_path)
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "PATH" in env
    assert env["HOME"].startswith(str(tmp_path))
    assert env["TMPDIR"].startswith(str(tmp_path))
    assert Path(env["HOME"]) != host_home
    assert Path(env["TMPDIR"]) != host_tmp
    assert Path(env["HOME"]).name == ".verifier-home"
    assert Path(env["TMPDIR"]).name == ".verifier-tmp"


def test_child_home_secret_write_stays_in_workspace(monkeypatch, tmp_path):
    import sys

    host_home = tmp_path / "host-home"
    host_home.mkdir()
    monkeypatch.setenv("HOME", str(host_home))
    monkeypatch.setenv("IMPL_COMPARISON_SECRET_PROBE", "leak-me")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    from impl_comparison.research_tasks.process import _run_subprocess

    proc = _run_subprocess(
        [
            sys.executable,
            "-c",
            "from pathlib import Path\n"
            "target = Path.home() / 'leak.txt'\n"
            "target.write_text('leak-me')\n"
            "print(str(target.resolve()))\n",
        ],
        workspace,
        10.0,
    )
    assert proc.returncode == 0, proc.stderr
    written = Path(proc.stdout.strip())
    assert written.is_file()
    assert written.read_text() == "leak-me"
    try:
        written.resolve().relative_to(workspace.resolve())
    except ValueError:
        raise AssertionError("child HOME write escaped workspace: {}".format(written))
    assert not (host_home / "leak.txt").exists()


def test_verifier_child_does_not_inherit_secret_probe(monkeypatch, tmp_path):
    monkeypatch.setenv("IMPL_COMPARISON_SECRET_PROBE", "pass-if-leaked")
    from impl_comparison.research_tasks.se.tasks import _assert_script

    result = _assert_script(
        tmp_path,
        "import os\n"
        "assert os.environ.get('IMPL_COMPARISON_SECRET_PROBE') == 'pass-if-leaked'\n"
        "print('ok')\n",
    )
    assert result.passed is False


def test_se03_pre_migrated_records_and_noop_migrate_fails(tmp_path):
    task = _task("se-03-schema-migration")
    workspace = materialize_task(task, tmp_path)
    (workspace / "records.json").write_text(
        json.dumps(
            {
                "records": [
                    {"id": "r1", "full_name": "Ada"},
                    {"id": "r2", "full_name": "Bob"},
                    {"id": "r3", "full_name": "Cyd"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (workspace / "migrate.py").write_text(
        "def migrate(path):\n    return None\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False


@pytest.mark.parametrize("task_id", TERMINAL_TASK_IDS)
def test_terminal_task_prompt_is_command_oriented_and_timeout_bounded(task_id):
    task = _task(task_id)
    prompt = task.prompt.strip()
    assert prompt, task_id
    assert task.timeout <= 120, task_id
    lowered = prompt.lower()
    assert any(term in lowered for term in _OPERATIONAL_TERMS), task_id


def test_terminal_fixtures_materialize_at_least_three_files(tmp_path):
    terminal_tasks = _terminal_tasks()
    assert len(terminal_tasks) == 10
    for task in terminal_tasks:
        dest_a = tmp_path / task.task_id / "a"
        dest_b = tmp_path / task.task_id / "b"
        out_a = materialize_task(task, dest_a)
        out_b = materialize_task(task, dest_b)
        assert Path(out_a).resolve() == dest_a.resolve()
        assert Path(out_b).resolve() == dest_b.resolve()
        files_a = _counted_files(dest_a)
        files_b = _counted_files(dest_b)
        assert len(files_a) >= 3, task.task_id
        assert len(files_b) >= 3, task.task_id
        marker = dest_a / "isolation-marker.txt"
        marker.write_text("only-a", encoding="utf-8")
        assert not (dest_b / "isolation-marker.txt").is_file()
        py_files = [path for path in files_a if path.suffix == ".py"]
        assert py_files, task.task_id
        original = py_files[0].read_text(encoding="utf-8")
        py_files[0].write_text(original + "\n# mutated\n", encoding="utf-8")
        relative = py_files[0].relative_to(dest_a)
        assert "# mutated" not in (dest_b / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("task_id", TERMINAL_TASK_IDS)
def test_terminal_broken_fixture_fails_verifier(task_id, tmp_path):
    task = _task(task_id)
    workspace = materialize_task(task, tmp_path / task_id)
    result = verify_task(task, workspace)
    assert result.passed is False, (task_id, result.reason)


@pytest.mark.parametrize("task_id", TERMINAL_TASK_IDS)
def test_terminal_corrected_fixture_passes_verifier(task_id, tmp_path):
    task = _task(task_id)
    workspace = materialize_task(task, tmp_path / task_id)
    apply_reference_fix(task, workspace)
    result = verify_task(task, workspace)
    assert result.passed is True, (task_id, result.reason)


@pytest.mark.parametrize(
    "task_id,relative",
    list(TERMINAL_PRIMARY_ARTIFACTS.items()),
)
def test_terminal_missing_or_invalid_primary_artifact_fails(
    task_id, relative, tmp_path
):
    task = _task(task_id)
    workspace = materialize_task(task, tmp_path / task_id)
    apply_reference_fix(task, workspace)
    target = workspace / relative
    assert target.is_file(), (task_id, relative)
    target.write_text("CORRUPTED-ARTIFACT\n", encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False, (task_id, result.reason)


def test_terminal_verifiers_ignore_claimed_success_text(tmp_path):
    for task in _terminal_tasks():
        workspace = materialize_task(task, tmp_path / task.task_id)
        if task.task_id != "terminal-06-checksum-artifact":
            (workspace / "answer.txt").write_text(
                "ALL TESTS PASSED", encoding="utf-8"
            )
        (workspace / "SUCCESS").write_text("I did it", encoding="utf-8")
        (workspace / "I_PASSED.txt").write_text("passed=True", encoding="utf-8")
        result = verify_task(task, workspace)
        assert result.passed is False, task.task_id


def test_terminal06_wrong_hash_fails_and_boast_file_does_not_pass(tmp_path):
    task = _task("terminal-06-checksum-artifact")
    workspace = materialize_task(task, tmp_path)
    (workspace / "answer.txt").write_text("0" * 64, encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False
    payload = (workspace / "data.bin").read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    (workspace / "answer.txt").unlink()
    (workspace / "SUCCESS.txt").write_text(digest + "\n", encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False


def test_terminal05_incomplete_restart_marker_fails(tmp_path):
    task = _task("terminal-05-timeout-restart")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "restart.marker").write_text("attempt=1\n", encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False


def test_terminal05_missing_second_attempt_fails(tmp_path):
    task = _task("terminal-05-timeout-restart")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "restart.marker").write_text(
        "timeout_handled=1\n", encoding="utf-8"
    )
    result = verify_task(task, workspace)
    assert result.passed is False


def test_terminal08_peak_memory_above_limit_fails(tmp_path):
    task = _task("terminal-08-stream-large-file")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "peak_memory.txt").write_text("999999999\n", encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False


def test_terminal08_missing_peak_memory_marker_fails(tmp_path):
    task = _task("terminal-08-stream-large-file")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    marker = workspace / "peak_memory.txt"
    assert marker.is_file()
    marker.unlink()
    result = verify_task(task, workspace)
    assert result.passed is False


def test_terminal08_shrinking_log_to_match_small_count_fails(tmp_path):
    task = _task("terminal-08-stream-large-file")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "large.log").write_text("event-0000 payload\n", encoding="utf-8")
    (workspace / "summary.txt").write_text("count=1\n", encoding="utf-8")
    (workspace / "peak_memory.txt").write_text("1\n", encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False, result.reason


def test_terminal09_success_state_without_rollback_fails(tmp_path):
    task = _task("terminal-09-rollback-rerun")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "broken.flag").write_text("failed-mutation\n", encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False


def test_terminal02_changing_unrelated_config_fails(tmp_path):
    task = _task("terminal-02-log-config")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    config = json.loads((workspace / "config.json").read_text(encoding="utf-8"))
    config["feature_flag"] = "tampered"
    (workspace / "config.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    result = verify_task(task, workspace)
    assert result.passed is False


def test_terminal03_deleting_inputs_and_shrinking_manifest_fails(tmp_path):
    task = _task("terminal-03-file-transform")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    for name in ("bravo.txt", "charlie.txt"):
        (workspace / "inputs" / name).unlink()
        output = workspace / "outputs" / name
        if output.is_file():
            output.unlink()
    (workspace / "manifest.json").write_text(
        json.dumps({"count": 1, "files": ["alpha.txt"]}) + "\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False, result.reason


def test_terminal04_stubbed_ingest_tests_with_broken_ingest_fails(tmp_path):
    task = _task("terminal-04-test-triage")
    workspace = materialize_task(task, tmp_path)
    (workspace / "tests" / "test_ingest.py").write_text(
        "def test_ingest_trims():\n    assert True\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False, result.reason


def test_terminal04_deleted_export_tests_after_ingest_fix_fails(tmp_path):
    task = _task("terminal-04-test-triage")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "tests" / "test_export.py").unlink()
    result = verify_task(task, workspace)
    assert result.passed is False, result.reason


def test_terminal04_replaced_export_tests_with_assert_false_fails(tmp_path):
    task = _task("terminal-04-test-triage")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "tests" / "test_export.py").write_text(
        "def test_export_prefix():\n    assert False\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False, result.reason


def test_terminal04_fixing_unrelated_group_fails(tmp_path):
    task = _task("terminal-04-test-triage")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "export.py").write_text(
        "def export(item):\n    return 'out:' + item\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False


def test_terminal07_writing_secret_value_fails(tmp_path):
    task = _task("terminal-07-env-diagnosis")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "TOKEN").write_text("n0t-for-disk\n", encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False


def test_terminal07_writing_secret_to_path_home_fails(monkeypatch, tmp_path):
    host_home = tmp_path / "host-home"
    host_home.mkdir()
    monkeypatch.setenv("HOME", str(host_home))
    task = _task("terminal-07-env-diagnosis")
    workspace = materialize_task(task, tmp_path / "ws")
    apply_reference_fix(task, workspace)
    (workspace / "run.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "token = os.environ.get('APP_TOKEN', '')\n"
        "if not token:\n"
        "    raise SystemExit(1)\n"
        "(Path.home() / 'token.txt').write_text(token + '\\n')\n"
        "print('ok')\n",
        encoding="utf-8",
    )
    result = verify_task(task, workspace)
    assert result.passed is False, result.reason
    assert not (host_home / "token.txt").is_file()


def test_terminal10_two_of_three_results_fails(tmp_path):
    task = _task("terminal-10-parallel-checks")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "results" / "check_c.txt").unlink()
    result = verify_task(task, workspace)
    assert result.passed is False


def test_terminal10_wrong_aggregate_status_fails(tmp_path):
    task = _task("terminal-10-parallel-checks")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    (workspace / "summary.txt").write_text("aggregate=PASS\n", encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False


@pytest.mark.parametrize("task_id", QNA_TASK_IDS)
def test_qna_task_prompt_requires_answer_and_timeout_bounded(task_id):
    task = _task(task_id)
    prompt = task.prompt.strip()
    assert prompt, task_id
    assert task.timeout <= 60, task_id
    assert "answer.txt" in prompt.lower(), task_id
    assert "answer_format.md" in prompt.lower(), task_id


def test_qna_fixtures_materialize_linked_sources_and_schema(tmp_path):
    qna_tasks = _qna_tasks()
    assert len(qna_tasks) == 10
    for task in qna_tasks:
        dest_a = tmp_path / task.task_id / "a"
        dest_b = tmp_path / task.task_id / "b"
        out_a = materialize_task(task, dest_a)
        out_b = materialize_task(task, dest_b)
        assert Path(out_a).resolve() == dest_a.resolve()
        assert Path(out_b).resolve() == dest_b.resolve()
        assert not (dest_a / "answer.txt").is_file(), task.task_id
        assert (dest_a / "ANSWER_FORMAT.md").is_file(), task.task_id
        assert (dest_b / "ANSWER_FORMAT.md").is_file(), task.task_id
        files_a, linked_a = _linked_python_component_size(dest_a)
        files_b, linked_b = _linked_python_component_size(dest_b)
        assert len(files_a) >= 5, task.task_id
        assert len(files_b) >= 5, task.task_id
        assert linked_a >= 5, (task.task_id, linked_a, [path.name for path in files_a])
        assert linked_b >= 5, (task.task_id, linked_b)
        marker = dest_a / "isolation-marker.txt"
        marker.write_text("only-a", encoding="utf-8")
        assert not (dest_b / "isolation-marker.txt").is_file()
        original = files_a[0].read_text(encoding="utf-8")
        files_a[0].write_text(original + "\n# mutated\n", encoding="utf-8")
        relative = files_a[0].relative_to(dest_a)
        assert "# mutated" not in (dest_b / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("task_id", QNA_TASK_IDS)
def test_qna_broken_fixture_fails_verifier(task_id, tmp_path):
    task = _task(task_id)
    workspace = materialize_task(task, tmp_path / task_id)
    result = verify_task(task, workspace)
    assert result.passed is False, (task_id, result.reason)


@pytest.mark.parametrize("task_id", QNA_TASK_IDS)
def test_qna_corrected_fixture_passes_verifier(task_id, tmp_path):
    task = _task(task_id)
    workspace = materialize_task(task, tmp_path / task_id)
    apply_reference_fix(task, workspace)
    result = verify_task(task, workspace)
    assert result.passed is True, (task_id, result.reason)


@pytest.mark.parametrize("task_id", QNA_TASK_IDS)
def test_qna_missing_required_key_fails(task_id, tmp_path):
    task = _task(task_id)
    workspace = materialize_task(task, tmp_path / task_id)
    apply_reference_fix(task, workspace)
    answer_path = workspace / "answer.txt"
    pairs = _parse_labeled_answer(answer_path.read_text(encoding="utf-8"))
    assert pairs, task_id
    dropped = pairs[1:] if len(pairs) > 1 else []
    answer_path.write_text(_format_labeled_answer(dropped), encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False, (task_id, result.reason)


@pytest.mark.parametrize("task_id", QNA_TASK_IDS)
def test_qna_fabricated_path_fails(task_id, tmp_path):
    task = _task(task_id)
    workspace = materialize_task(task, tmp_path / task_id)
    apply_reference_fix(task, workspace)
    answer_path = workspace / "answer.txt"
    pairs = _parse_labeled_answer(answer_path.read_text(encoding="utf-8"))
    rewritten = []
    replaced = False
    for key, value in pairs:
        if (not replaced) and _is_answer_path_field(key):
            rewritten.append((key, "ghost.py"))
            replaced = True
        else:
            rewritten.append((key, value))
    if not replaced:
        rewritten.append(("source_path", "ghost.py"))
    answer_path.write_text(_format_labeled_answer(rewritten), encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False, (task_id, result.reason)


@pytest.mark.parametrize("task_id", QNA_TASK_IDS)
def test_qna_unsupported_api_fails(task_id, tmp_path):
    task = _task(task_id)
    workspace = materialize_task(task, tmp_path / task_id)
    apply_reference_fix(task, workspace)
    answer_path = workspace / "answer.txt"
    pairs = _parse_labeled_answer(answer_path.read_text(encoding="utf-8"))
    rewritten = []
    replaced = False
    for key, value in pairs:
        if replaced:
            rewritten.append((key, value))
            continue
        if key == "recommendation":
            rewritten.append((key, "micro-kernels"))
            replaced = True
            continue
        if _looks_like_path(value):
            rewritten.append((key, value))
            continue
        if value.isidentifier() or key in {
            "caller",
            "intermediate",
            "sink",
            "parser",
            "consumer",
            "fix_function",
            "vulnerable_boundary",
            "mitigation",
            "hot_path",
            "persistence_point",
            "failure_boundary",
            "retry_path",
            "rollback_path",
            "proposed_test",
        }:
            rewritten.append((key, "not_a_real_api"))
            replaced = True
        else:
            rewritten.append((key, value))
    assert replaced, task_id
    answer_path.write_text(_format_labeled_answer(rewritten), encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False, (task_id, result.reason)


def test_qna_verifiers_ignore_claimed_success_text(tmp_path):
    for task in _qna_tasks():
        workspace = materialize_task(task, tmp_path / task.task_id)
        (workspace / "SUCCESS").write_text("I did it", encoding="utf-8")
        (workspace / "I_PASSED.txt").write_text("passed=True", encoding="utf-8")
        result = verify_task(task, workspace)
        assert result.passed is False, task.task_id


def test_qna_success_file_is_not_a_valid_answer(tmp_path):
    task = _task("qna-01-call-graph")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    gold = (workspace / "answer.txt").read_text(encoding="utf-8")
    (workspace / "answer.txt").unlink()
    (workspace / "SUCCESS.txt").write_text(gold, encoding="utf-8")
    result = verify_task(task, workspace)
    assert result.passed is False


def test_qna06_proposed_test_must_mention_branch_as_a_test(tmp_path):
    task = _task("qna-06-test-gap")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    pairs = _parse_labeled_answer(
        (workspace / "answer.txt").read_text(encoding="utf-8")
    )
    rewritten = []
    for key, value in pairs:
        if key == "proposed_test":
            rewritten.append((key, "empty_label"))
        else:
            rewritten.append((key, value))
    (workspace / "answer.txt").write_text(
        _format_labeled_answer(rewritten), encoding="utf-8"
    )
    result = verify_task(task, workspace)
    assert result.passed is False, result.reason


def test_qna10_invented_architecture_is_rejected(tmp_path):
    task = _task("qna-10-architecture-tradeoff")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    pairs = _parse_labeled_answer(
        (workspace / "answer.txt").read_text(encoding="utf-8")
    )
    rewritten = []
    for key, value in pairs:
        if key == "recommendation":
            rewritten.append((key, "micro-kernels"))
        else:
            rewritten.append((key, value))
    (workspace / "answer.txt").write_text(
        _format_labeled_answer(rewritten), encoding="utf-8"
    )
    result = verify_task(task, workspace)
    assert result.passed is False, result.reason


def test_qna05_attack_input_is_traversal_payload_not_guard_token(tmp_path):
    task = _task("qna-05-security-path")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    answer_path = workspace / "answer.txt"
    pairs = dict(_parse_labeled_answer(answer_path.read_text(encoding="utf-8")))
    attack = pairs["attack_input"]
    assert ".." in attack.replace("\\", "/")
    assert attack != "dotdot_outside"
    result = verify_task(task, workspace)
    assert result.passed is True, result.reason
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in workspace.rglob("*")
        if path.is_file() and path.suffix in {".py", ".md"}
    )
    assert attack in sources
    _rewrite_answer(answer_path, {"attack_input": "dotdot_outside"})
    result = verify_task(task, workspace)
    assert result.passed is False, result.reason
    apply_reference_fix(task, workspace)
    _rewrite_answer(answer_path, {"boundary_path": "ghost.py"})
    result = verify_task(task, workspace)
    assert result.passed is False, result.reason


def test_qna05_readme_does_not_claim_serve_as_blob_reader(tmp_path):
    task = _task("qna-05-security-path")
    workspace = materialize_task(task, tmp_path)
    readme = (workspace / "README.md").read_text(encoding="utf-8")
    assert "`serve`" not in readme
    assert "serve(" not in readme


def test_qna06_observable_behavior_accepts_natural_none(tmp_path):
    task = _task("qna-06-test-gap")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    answer_path = workspace / "answer.txt"
    labels = (workspace / "labels.py").read_text(encoding="utf-8")
    assert "returns_none" not in labels
    pairs = dict(_parse_labeled_answer(answer_path.read_text(encoding="utf-8")))
    assert pairs["observable_behavior"] != "returns_none"
    result = verify_task(task, workspace)
    assert result.passed is True, result.reason
    for value in ("None", "returns None", "null"):
        apply_reference_fix(task, workspace)
        _rewrite_answer(answer_path, {"observable_behavior": value})
        result = verify_task(task, workspace)
        assert result.passed is True, (value, result.reason)


def test_qna08_alternate_valid_transition_passes(tmp_path):
    task = _task("qna-08-state-flow")
    workspace = materialize_task(task, tmp_path)
    apply_reference_fix(task, workspace)
    answer_path = workspace / "answer.txt"
    _rewrite_answer(answer_path, {"valid_transition": "paid->shipped"})
    result = verify_task(task, workspace)
    assert result.passed is True, result.reason
    apply_reference_fix(task, workspace)
    _rewrite_answer(
        answer_path,
        {
            "states": "draft, paid, shipped",
            "valid_transition": "draft -> paid",
        },
    )
    result = verify_task(task, workspace)
    assert result.passed is True, result.reason


def test_qna_answer_format_documents_keys_without_gold_identifiers(tmp_path):
    for task in _qna_tasks():
        workspace = materialize_task(task, tmp_path / task.task_id)
        format_path = workspace / "ANSWER_FORMAT.md"
        assert format_path.is_file(), task.task_id
        format_text = format_path.read_text(encoding="utf-8")
        apply_reference_fix(task, workspace)
        pairs = _parse_labeled_answer(
            (workspace / "answer.txt").read_text(encoding="utf-8")
        )
        assert pairs, task.task_id
        for key, value in pairs:
            assert key in format_text, (task.task_id, key)
        prompt = task.prompt
        for name in _hidden_gold_identifiers(pairs):
            assert name not in format_text, (task.task_id, name)
            assert name not in prompt, (task.task_id, name)
