"""SE research fixtures: broken workspaces, verifiers, and reference fixes."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List

from ...protocol import TaskSpec, VerifierResult
from ..process import _run_subprocess

Builder = Callable[[Path, bool], None]
Verifier = Callable[[Path], VerifierResult]


def materialize_se_task(task: TaskSpec, dest: Path) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    builder = _lookup(_BUILDERS, task)
    builder(dest, False)
    return dest


def apply_se_reference_fix(task: TaskSpec, workspace: Path) -> None:
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    builder = _lookup(_BUILDERS, task)
    builder(workspace, True)


def verify_se_task(task: TaskSpec, workspace: Path) -> VerifierResult:
    workspace = Path(workspace)
    verifier = _lookup(_VERIFIERS, task)
    return verifier(workspace)


def _lookup(table: Dict[str, Callable], task: TaskSpec) -> Callable:
    if task.task_id in table:
        return table[task.task_id]
    if task.verifier_name in table:
        return table[task.verifier_name]
    raise ValueError("unknown SE task: {}".format(task.task_id))


def _write(dest: Path, relative: str, content: str) -> None:
    path = dest / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _result(passed: bool, reason: str = "") -> VerifierResult:
    return VerifierResult(
        passed=passed,
        score=1.0 if passed else 0.0,
        reason=reason,
    )


def _run(workspace: Path, script: str, timeout: float = 20.0) -> subprocess.CompletedProcess:
    return _run_subprocess([sys.executable, "-c", script], workspace, timeout)


def _assert_script(workspace: Path, script: str, timeout: float = 20.0) -> VerifierResult:
    try:
        proc = _run(workspace, script, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _result(False, "subprocess failed: {}".format(exc))
    if proc.returncode == 0:
        return _result(True, (proc.stdout or "").strip())
    reason = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return _result(False, reason[-4000:])


def _run_pytest(workspace: Path, testfile: str, timeout: float = 20.0) -> subprocess.CompletedProcess:
    return _run_subprocess(
        [sys.executable, "-m", "pytest", testfile, "-q"],
        workspace,
        timeout,
    )


def _parse_py(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _calls_name(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == name:
                return True
            if isinstance(func, ast.Attribute) and func.attr == name:
                return True
    return False


def _defines_function(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return True
    return False


def _uses_name(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
    return False


def _imported_modules(tree: ast.AST) -> List[str]:
    modules: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name.split(".")[0])
    return modules


def _imported_symbols(tree: ast.AST) -> List[str]:
    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.append(alias.name)
    return names


def _item_label_literals(tree: ast.AST) -> List[str]:
    found: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "item-" in node.value:
                found.append(node.value)
        if isinstance(node, ast.JoinedStr):
            chunks = []
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    chunks.append(part.value)
            blob = "".join(chunks)
            if "item-" in blob:
                found.append(blob)
    return found


def _calls_imported_helper(tree: ast.AST) -> bool:
    imported_locals = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_locals.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_locals.add(alias.asname or alias.name.split(".")[0])
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in imported_locals:
            return True
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id in imported_locals:
                return True
    return False


# ---------------------------------------------------------------------------
# se-01 multifile bug
# ---------------------------------------------------------------------------

_SE01_PARSER_BROKEN = """\
def parse(line):
    return [part for part in line.split() if part]
"""

_SE01_PARSER_FIXED = """\
def parse(line):
    tokens = []
    current = []
    in_quote = False
    for ch in line:
        if ch == '"':
            in_quote = not in_quote
            continue
        if ch == " " and not in_quote:
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens
"""

_SE01_SERVICE = """\
from parser import parse


def parse_request(line):
    return parse(line)
"""

_SE01_CLI = """\
from parser import parse


def parse_line(line):
    return parse(line)


def main(argv):
    return parse_line(" ".join(argv))
"""

_SE01_TEST = """\
from service import parse_request


def test_unquoted_tokens():
    assert parse_request("alpha beta gamma") == ["alpha", "beta", "gamma"]
"""

_SE01_README = """\
# Token service

`service.parse_request` and `cli.parse_line` both tokenize incoming lines.
Quoted phrases should stay together. Run `python3 -m pytest test_service.py`.
"""

_SE01_SETTINGS = """\
[parser]
quote_char = '"'
"""


def _build_se01(dest: Path, fixed: bool) -> None:
    _write(dest, "parser.py", _SE01_PARSER_FIXED if fixed else _SE01_PARSER_BROKEN)
    _write(dest, "service.py", _SE01_SERVICE)
    _write(dest, "cli.py", _SE01_CLI)
    _write(dest, "test_service.py", _SE01_TEST)
    _write(dest, "README.md", _SE01_README)
    _write(dest, "settings.toml", _SE01_SETTINGS)


def _verify_se01(workspace: Path) -> VerifierResult:
    proc = _run_pytest(workspace, "test_service.py")
    if proc.returncode != 0:
        reason = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return _result(False, "regression tests failed: " + reason[-4000:])
    script = r"""
from service import parse_request
from cli import parse_line, main

cases = [
    ("alpha beta gamma", ["alpha", "beta", "gamma"]),
    ('cmd "hello world" extra', ["cmd", "hello world", "extra"]),
    ('a "b c" d', ["a", "b c", "d"]),
    ('one "two three" four', ["one", "two three", "four"]),
]
for line, expected in cases:
    svc = parse_request(line)
    cli = parse_line(line)
    assert svc == expected, "service %r -> %r" % (line, svc)
    assert cli == expected, "cli %r -> %r" % (line, cli)
argv = main(["cmd", '"hello world"', "extra"])
assert argv == ["cmd", "hello world", "extra"], "cli.main: %r" % (argv,)
print("ok")
"""
    return _assert_script(workspace, script)


# ---------------------------------------------------------------------------
# se-02 API migration
# ---------------------------------------------------------------------------

_SE02_USERS_BROKEN = """\
USERS = {"alice": {"id": "alice", "name": "Alice"}}


def get_user(user_id):
    return USERS.get(user_id)
"""

_SE02_USERS_FIXED = """\
USERS = {"alice": {"id": "alice", "name": "Alice"}}


def fetch_user(user_id):
    return USERS.get(user_id)


def get_user(user_id):
    return fetch_user(user_id)
"""

_SE02_REPORTS_BROKEN = """\
from users import get_user


def user_report(user_id):
    user = get_user(user_id)
    if not user:
        return "missing"
    return "report:" + user["name"]
"""

_SE02_REPORTS_FIXED = """\
from users import fetch_user


def user_report(user_id):
    user = fetch_user(user_id)
    if not user:
        return "missing"
    return "report:" + user["name"]
"""

_SE02_DASHBOARD_BROKEN = """\
from users import get_user


def greet(user_id):
    user = get_user(user_id)
    if not user:
        return "guest"
    return "hello " + user["name"]
"""

_SE02_DASHBOARD_FIXED = """\
from users import fetch_user


def greet(user_id):
    user = fetch_user(user_id)
    if not user:
        return "guest"
    return "hello " + user["name"]
"""

_SE02_TEST = """\
from reports import user_report
from dashboard import greet


def test_known_user():
    assert user_report("alice") == "report:Alice"
    assert greet("alice") == "hello Alice"
"""

_SE02_README = """\
# User directory

`get_user` is deprecated. New code should use `fetch_user`.
Update reports and dashboard call sites.
"""

_SE02_CFG = """\
[api]
legacy = get_user
replacement = fetch_user
"""


def _build_se02(dest: Path, fixed: bool) -> None:
    _write(dest, "users.py", _SE02_USERS_FIXED if fixed else _SE02_USERS_BROKEN)
    _write(dest, "reports.py", _SE02_REPORTS_FIXED if fixed else _SE02_REPORTS_BROKEN)
    _write(dest, "dashboard.py", _SE02_DASHBOARD_FIXED if fixed else _SE02_DASHBOARD_BROKEN)
    _write(dest, "test_reports.py", _SE02_TEST)
    _write(dest, "README.md", _SE02_README)
    _write(dest, "api.ini", _SE02_CFG)


def _verify_se02(workspace: Path) -> VerifierResult:
    users_tree = _parse_py(workspace / "users.py")
    if not _defines_function(users_tree, "fetch_user"):
        return _result(False, "fetch_user is not implemented")
    for name in ("reports.py", "dashboard.py"):
        tree = _parse_py(workspace / name)
        if _calls_name(tree, "get_user") or "get_user" in _imported_symbols(tree):
            return _result(False, "{} still uses get_user".format(name))
        if not _calls_name(tree, "fetch_user"):
            return _result(False, "{} does not call fetch_user".format(name))
    script = r"""
from users import fetch_user
from reports import user_report
from dashboard import greet

assert fetch_user("alice")["name"] == "Alice"
assert user_report("alice") == "report:Alice"
assert greet("alice") == "hello Alice"
assert user_report("missing") == "missing"
print("ok")
"""
    return _assert_script(workspace, script)


# ---------------------------------------------------------------------------
# se-03 schema migration
# ---------------------------------------------------------------------------

_SE03_RECORDS = """\
{
  "records": [
    {"id": "r1", "name": "Ada"},
    {"id": "r2", "name": "Bob"},
    {"id": "r3", "name": "Cyd"}
  ]
}
"""

_SE03_MIGRATE_BROKEN = """\
import json
from pathlib import Path


def migrate(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    converted = []
    for rec in data.get("records", []):
        converted.append(
            {
                "id": rec["id"],
                "full_name": rec.get("name", rec.get("full_name", "")),
            }
        )
    data["records"] = converted[:-1]
    Path(path).write_text(json.dumps(data), encoding="utf-8")
"""

_SE03_MIGRATE_FIXED = """\
import json
from pathlib import Path


def migrate(path):
    target = Path(path)
    data = json.loads(target.read_text(encoding="utf-8"))
    for rec in data.get("records", []):
        if "full_name" not in rec and "name" in rec:
            rec["full_name"] = rec["name"]
        if "name" in rec:
            del rec["name"]
    target.write_text(json.dumps(data), encoding="utf-8")
"""

_SE03_STORE = """\
import json
from pathlib import Path


def load_records(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    loaded = []
    for rec in data.get("records", []):
        loaded.append({"id": rec["id"], "full_name": rec["full_name"]})
    return loaded
"""

_SE03_TEST = """\
import json
from pathlib import Path

from store import load_records


def test_new_format_roundtrip(tmp_path):
    path = tmp_path / "one.json"
    path.write_text(
        json.dumps({"records": [{"id": "n1", "full_name": "Neo"}]}),
        encoding="utf-8",
    )
    rows = load_records(path)
    assert rows == [{"id": "n1", "full_name": "Neo"}]
"""

_SE03_README = """\
# Directory store

The `name` field was renamed to `full_name`. Run `migrate.py` against
`records.json` so existing rows remain readable.
"""

_SE03_CFG = """\
{
  "schema_version": 2,
  "id_field": "id",
  "name_field": "full_name"
}
"""


def _build_se03(dest: Path, fixed: bool) -> None:
    if not (dest / "records.json").is_file() or not fixed:
        _write(dest, "records.json", _SE03_RECORDS)
    _write(dest, "migrate.py", _SE03_MIGRATE_FIXED if fixed else _SE03_MIGRATE_BROKEN)
    _write(dest, "store.py", _SE03_STORE)
    _write(dest, "test_store.py", _SE03_TEST)
    _write(dest, "README.md", _SE03_README)
    _write(dest, "schema.json", _SE03_CFG)


def _verify_se03(workspace: Path) -> VerifierResult:
    script = r"""
import json
from pathlib import Path

from migrate import migrate
from store import load_records

probe = Path("_verifier_probe.json")
expected_ids = ["v1", "v2", "v3"]
expected_names = ["AdaVerifier", "BobVerifier", "CydVerifier"]
probe.write_text(
    json.dumps(
        {
            "records": [
                {"id": expected_ids[0], "name": expected_names[0]},
                {"id": expected_ids[1], "name": expected_names[1]},
                {"id": expected_ids[2], "name": expected_names[2]},
            ]
        }
    ),
    encoding="utf-8",
)
migrate(str(probe))
migrate(str(probe))
raw = json.loads(probe.read_text(encoding="utf-8"))
rows = raw.get("records") or []
assert [row.get("id") for row in rows] == expected_ids, rows
assert all("name" not in row for row in rows), rows
assert [row.get("full_name") for row in rows] == expected_names, rows
loaded = load_records(str(probe))
assert [row["id"] for row in loaded] == expected_ids, loaded
assert [row["full_name"] for row in loaded] == expected_names, loaded
print("ok")
"""
    return _assert_script(workspace, script)


# ---------------------------------------------------------------------------
# se-04 race condition
# ---------------------------------------------------------------------------

_SE04_COUNTER_BROKEN = """\
import time


class Counter(object):
    def __init__(self):
        self.value = 0

    def increment(self):
        current = self.value
        time.sleep(0.005)
        self.value = current + 1
"""

_SE04_COUNTER_FIXED = """\
import threading


class Counter(object):
    def __init__(self):
        self.value = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self.value += 1
"""

_SE04_APP = """\
from counter import Counter


def make_counter():
    return Counter()
"""

_SE04_TEST = """\
from counter import Counter


def test_sequential_increments():
    counter = Counter()
    counter.increment()
    counter.increment()
    assert counter.value == 2
"""

_SE04_README = """\
# Request counter

`Counter.increment` is used from many threads. Sequential tests pass, but
concurrent callers should not lose updates.
"""

_SE04_CFG = """\
[counter]
threads = 100
"""


def _build_se04(dest: Path, fixed: bool) -> None:
    _write(dest, "counter.py", _SE04_COUNTER_FIXED if fixed else _SE04_COUNTER_BROKEN)
    _write(dest, "app.py", _SE04_APP)
    _write(dest, "test_counter.py", _SE04_TEST)
    _write(dest, "README.md", _SE04_README)
    _write(dest, "app.ini", _SE04_CFG)


def _verify_se04(workspace: Path) -> VerifierResult:
    script = r"""
import threading
from counter import Counter

counter = Counter()
n = 100
barrier = threading.Barrier(n)
errors = []

def worker():
    try:
        barrier.wait()
        counter.increment()
    except Exception as exc:
        errors.append(exc)

threads = [threading.Thread(target=worker) for _ in range(n)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert not errors, errors
assert counter.value == 100, counter.value
print("ok")
"""
    return _assert_script(workspace, script, timeout=30.0)


# ---------------------------------------------------------------------------
# se-05 cache invalidation
# ---------------------------------------------------------------------------

_SE05_CATALOG_BROKEN = """\
class Catalog(object):
    def __init__(self):
        self._items = {}
        self._primary = {}
        self._by_name = {}

    def add(self, item_id, name):
        self._items[item_id] = name
        self._primary[item_id] = name
        self._by_name[name] = item_id

    def update(self, item_id, name):
        self._items[item_id] = name

    def get(self, item_id):
        if item_id in self._primary:
            return self._primary[item_id]
        return self._items.get(item_id)

    def find_id(self, name):
        return self._by_name.get(name)
"""

_SE05_CATALOG_FIXED = """\
class Catalog(object):
    def __init__(self):
        self._items = {}
        self._primary = {}
        self._by_name = {}

    def add(self, item_id, name):
        self._items[item_id] = name
        self._primary[item_id] = name
        self._by_name[name] = item_id

    def update(self, item_id, name):
        old = self._items.get(item_id)
        self._items[item_id] = name
        self._primary.pop(item_id, None)
        if old is not None:
            self._by_name.pop(old, None)
        self._primary[item_id] = name
        self._by_name[name] = item_id

    def get(self, item_id):
        if item_id in self._primary:
            return self._primary[item_id]
        return self._items.get(item_id)

    def find_id(self, name):
        return self._by_name.get(name)
"""

_SE05_APP = """\
from catalog import Catalog


def seed():
    catalog = Catalog()
    catalog.add("p1", "alpha")
    return catalog
"""

_SE05_TEST = """\
from catalog import Catalog


def test_add_and_get():
    catalog = Catalog()
    catalog.add("p1", "alpha")
    assert catalog.get("p1") == "alpha"
    assert catalog.find_id("alpha") == "p1"
"""

_SE05_README = """\
# Catalog cache

Items are cached by id and by name. Updating a record must not leave stale
lookups in either cache.
"""

_SE05_CFG = """\
{"primary_cache": "id", "derived_cache": "name"}
"""


def _build_se05(dest: Path, fixed: bool) -> None:
    _write(dest, "catalog.py", _SE05_CATALOG_FIXED if fixed else _SE05_CATALOG_BROKEN)
    _write(dest, "app.py", _SE05_APP)
    _write(dest, "test_catalog.py", _SE05_TEST)
    _write(dest, "README.md", _SE05_README)
    _write(dest, "cache.json", _SE05_CFG)


def _verify_se05(workspace: Path) -> VerifierResult:
    script = r"""
from catalog import Catalog

catalog = Catalog()
catalog.add("p1", "alpha")
catalog.update("p1", "beta")
assert catalog.get("p1") == "beta", catalog.get("p1")
assert catalog.find_id("alpha") is None, catalog.find_id("alpha")
assert catalog.find_id("beta") == "p1", catalog.find_id("beta")
print("ok")
"""
    return _assert_script(workspace, script)


# ---------------------------------------------------------------------------
# se-06 retry / timeout
# ---------------------------------------------------------------------------

_SE06_CLOCK = """\
class FakeClock(object):
    def __init__(self):
        self._now = 0.0

    def time(self):
        return self._now

    def sleep(self, seconds):
        self._now += float(seconds)
"""

_SE06_RETRY_BROKEN = """\
def retry(operation, max_attempts, timeout, clock):
    last = None
    for _ in range(max_attempts + 7):
        try:
            last = operation()
        except Exception as exc:
            last = exc
    if isinstance(last, Exception):
        raise last
    return last
"""

_SE06_RETRY_FIXED = """\
def retry(operation, max_attempts, timeout, clock):
    start = clock.time()
    last_error = None
    attempts = 0
    while attempts < max_attempts:
        if clock.time() - start >= timeout:
            raise TimeoutError("timeout")
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            attempts += 1
            if clock.time() - start >= timeout:
                raise TimeoutError("timeout")
    if last_error is not None:
        raise last_error
    raise RuntimeError("retry exhausted")
"""

_SE06_TEST = """\
from clock import FakeClock
from retry import retry


def test_first_call_success():
    clock = FakeClock()
    assert retry(lambda: "ok", 3, 10.0, clock) == "ok"
"""

_SE06_README = """\
# Outbound client

Implement `retry(operation, max_attempts, timeout, clock)`.
`clock` exposes `time()` and `sleep(seconds)` so tests can avoid real waits.
"""

_SE06_CFG = """\
{"max_attempts": 3, "timeout": 5.0}
"""


def _build_se06(dest: Path, fixed: bool) -> None:
    _write(dest, "clock.py", _SE06_CLOCK)
    _write(dest, "retry.py", _SE06_RETRY_FIXED if fixed else _SE06_RETRY_BROKEN)
    _write(dest, "test_retry.py", _SE06_TEST)
    _write(dest, "README.md", _SE06_README)
    _write(dest, "settings.json", _SE06_CFG)


def _verify_se06(workspace: Path) -> VerifierResult:
    script = r"""
from clock import FakeClock
from retry import retry

class Clock(FakeClock):
    pass

# stop on first success
clock = Clock()
calls = []

def flaky():
    calls.append(clock.time())
    if len(calls) < 2:
        raise ConnectionError("fail")
    return "ok"

assert retry(flaky, 5, 30.0, clock) == "ok"
assert len(calls) == 2, calls

# cap attempts
clock = Clock()
fails = []

def always_fail():
    fails.append(1)
    raise ConnectionError("fail")

raised = None
try:
    retry(always_fail, 3, 30.0, clock)
except Exception as exc:
    raised = exc
assert raised is not None
assert len(fails) == 3, fails

# timeout after a hung attempt, no extra retries
clock = Clock()
hangs = []

def hang():
    hangs.append(1)
    clock.sleep(20)
    raise ConnectionError("hang")

raised = None
try:
    retry(hang, 5, 5.0, clock)
except Exception as exc:
    raised = exc
assert raised is not None
assert len(hangs) == 1, hangs
print("ok")
"""
    return _assert_script(workspace, script)


# ---------------------------------------------------------------------------
# se-07 auth / path security
# ---------------------------------------------------------------------------

_SE07_AUTH = """\
ROLES = {
    "alice": "admin",
    "bob": "user",
}
"""

_SE07_FILES_BROKEN = """\
from pathlib import Path

from auth import ROLES

DATA_ROOT = Path(__file__).resolve().parent / "data"


def read_document(username, relative_path):
    target = DATA_ROOT / relative_path
    return target.read_text(encoding="utf-8")
"""

_SE07_FILES_FIXED = """\
from pathlib import Path

from auth import ROLES

DATA_ROOT = Path(__file__).resolve().parent / "data"


def read_document(username, relative_path):
    role = ROLES.get(username)
    if role not in ("admin", "user"):
        raise PermissionError("unauthorized")
    root = DATA_ROOT.resolve()
    target = (DATA_ROOT / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise PermissionError("traversal")
    if not target.is_file():
        raise FileNotFoundError(relative_path)
    return target.read_text(encoding="utf-8")
"""

_SE07_TEST = """\
from files import read_document


def test_admin_reads_public():
    text = read_document("alice", "public.txt")
    assert "public" in text
"""

_SE07_README = """\
# Document service

`read_document(username, relative_path)` serves files from `data/`.
Only known roles may read, and paths must stay inside that directory.
"""

_SE07_CFG = """\
{"data_root": "data", "roles": ["admin", "user"]}
"""


def _build_se07(dest: Path, fixed: bool) -> None:
    _write(dest, "auth.py", _SE07_AUTH)
    _write(dest, "files.py", _SE07_FILES_FIXED if fixed else _SE07_FILES_BROKEN)
    _write(dest, "test_files.py", _SE07_TEST)
    _write(dest, "README.md", _SE07_README)
    _write(dest, "security.json", _SE07_CFG)
    _write(dest, "data/public.txt", "public document\n")
    _write(dest, "outside.txt", "secret-outside\n")


def _verify_se07(workspace: Path) -> VerifierResult:
    script = r"""
from files import read_document

def rejected(fn):
    try:
        fn()
    except (PermissionError, ValueError, OSError):
        return True
    return False

assert "public" in read_document("alice", "public.txt")
assert rejected(lambda: read_document("eve", "public.txt")), "unauthorized role allowed"
assert rejected(lambda: read_document("alice", "../outside.txt")), "traversal allowed"
assert rejected(lambda: read_document("bob", "../outside.txt")), "user traversal allowed"
print("ok")
"""
    return _assert_script(workspace, script)


# ---------------------------------------------------------------------------
# se-08 hidden edge cases
# ---------------------------------------------------------------------------

_SE08_LABELS_BROKEN = """\
def process(label, points=0):
    head = label[0]
    label.encode("ascii")
    if len(label) > 20:
        raise ValueError("too long")
    return {"label": label.strip().upper(), "points": points, "ok": True}
"""

_SE08_LABELS_FIXED = """\
import json
from pathlib import Path

_SETTINGS = json.loads(
    (Path(__file__).resolve().parent / "settings.json").read_text(encoding="utf-8")
)
MAX_LABEL_LENGTH = int(_SETTINGS["max_label_length"])


def process(label, points=0):
    if points < 0:
        return {"ok": False, "error": "points"}
    if len(label) > MAX_LABEL_LENGTH:
        return {"ok": False, "error": "too long"}
    return {"label": label.strip().upper(), "points": points, "ok": True}
"""

_SE08_APP = """\
from labels import process


def handle(label, points):
    return process(label, points)
"""

_SE08_TEST = """\
from labels import process


def test_typical_label():
    result = process("hello", 4)
    assert result["ok"] is True
    assert result["label"] == "HELLO"
    assert result["points"] == 4
"""

_SE08_README = """\
# Label processor

`process(label, points)` stores a trimmed, uppercased label.
Points must be non-negative. Length limits are in `settings.json`.
"""

_SE08_SETTINGS = """\
{"max_label_length": 32}
"""


def _build_se08(dest: Path, fixed: bool) -> None:
    _write(dest, "settings.json", _SE08_SETTINGS)
    _write(dest, "labels.py", _SE08_LABELS_FIXED if fixed else _SE08_LABELS_BROKEN)
    _write(dest, "app.py", _SE08_APP)
    _write(dest, "test_labels.py", _SE08_TEST)
    _write(dest, "README.md", _SE08_README)


def _verify_se08(workspace: Path) -> VerifierResult:
    script = r"""
import json
from pathlib import Path
from labels import process

limit = json.loads(Path("settings.json").read_text(encoding="utf-8"))["max_label_length"]
happy = process("hello", 4)
assert happy["ok"] is True
empty = process("", 0)
assert empty["ok"] is True, empty
assert empty.get("label", "") == ""
uni = process("naive\u0308", 1)
if not uni.get("ok"):
    uni = process("na\u00efve", 1)
assert uni["ok"] is True, uni
assert uni["label"]
neg = process("ab", -3)
assert neg.get("ok") is False, neg
wide = process("a" * int(limit), 1)
assert wide["ok"] is True, wide
print("ok")
"""
    return _assert_script(workspace, script)


# ---------------------------------------------------------------------------
# se-09 coupling refactor
# ---------------------------------------------------------------------------

_SE09_ALPHA_BROKEN = """\
GLOBAL = {"n": 0}


def _label(n):
    return "item-{}".format(n)


def public_a(n):
    GLOBAL["n"] = n
    return _label(n)
"""

_SE09_BETA_BROKEN = """\
GLOBAL = {"n": 0}


def _label(n):
    return "item-{}".format(n)


def public_b(n):
    GLOBAL["n"] = n
    return _label(n * 2)
"""

_SE09_SHARED = """\
def label(n):
    return "item-{}".format(n)
"""

_SE09_ALPHA_FIXED = """\
from shared import label


def public_a(n):
    return label(n)
"""

_SE09_BETA_FIXED = """\
from shared import label


def public_b(n):
    return label(n * 2)
"""

_SE09_TEST = """\
from alpha import public_a
from beta import public_b


def test_public_outputs():
    assert public_a(1) == "item-1"
    assert public_b(1) == "item-2"
"""

_SE09_README = """\
# Inventory labels

`public_a` and `public_b` should keep returning the same strings, but the
duplicated helper and shared GLOBAL dict need to be removed.
"""

_SE09_CFG = """\
[modules]
alpha = public_a
beta = public_b
"""


def _build_se09(dest: Path, fixed: bool) -> None:
    if fixed:
        _write(dest, "shared.py", _SE09_SHARED)
        _write(dest, "alpha.py", _SE09_ALPHA_FIXED)
        _write(dest, "beta.py", _SE09_BETA_FIXED)
    else:
        shared = dest / "shared.py"
        if shared.is_file():
            shared.unlink()
        _write(dest, "alpha.py", _SE09_ALPHA_BROKEN)
        _write(dest, "beta.py", _SE09_BETA_BROKEN)
    _write(dest, "test_labels.py", _SE09_TEST)
    _write(dest, "README.md", _SE09_README)
    _write(dest, "modules.ini", _SE09_CFG)


def _verify_se09(workspace: Path) -> VerifierResult:
    alpha = _parse_py(workspace / "alpha.py")
    beta = _parse_py(workspace / "beta.py")
    if _uses_name(alpha, "GLOBAL") or _uses_name(beta, "GLOBAL"):
        return _result(False, "GLOBAL dict is still present")
    local_modules = []
    for path in workspace.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        if path.stem in ("alpha", "beta"):
            continue
        local_modules.append(path.stem)
    shared = set(local_modules) & set(_imported_modules(alpha)) & set(_imported_modules(beta))
    if not shared:
        return _result(False, "alpha and beta do not share a helper module")
    if not _calls_imported_helper(alpha) or not _calls_imported_helper(beta):
        return _result(False, "alpha and beta must call the shared helper")
    if _item_label_literals(alpha) and _item_label_literals(beta):
        return _result(False, "duplicate label format logic remains in alpha and beta")
    script = r"""
from alpha import public_a
from beta import public_b

assert public_a(3) == "item-3"
assert public_b(3) == "item-6"
assert public_a(0) == "item-0"
print("ok")
"""
    return _assert_script(workspace, script)


# ---------------------------------------------------------------------------
# se-10 performance bottleneck
# ---------------------------------------------------------------------------

_SE10_SEARCH_BROKEN = """\
def find_matching(haystack, needles):
    found = []
    for needle in needles:
        for item in haystack:
            if item == needle:
                found.append(item)
                break
    return found
"""

_SE10_SEARCH_FIXED = """\
def find_matching(haystack, needles):
    index = {}
    for item in haystack:
        index[item] = item
    found = []
    for needle in needles:
        matched = index.get(needle)
        if matched is not None or needle in index:
            found.append(index[needle])
    return found
"""

_SE10_APP = """\
from search import find_matching


def lookup(haystack, needles):
    return find_matching(haystack, needles)
"""

_SE10_TEST = """\
from search import find_matching


def test_small_lookup():
    haystack = ["a", "b", "c"]
    assert find_matching(haystack, ["b", "c"]) == ["b", "c"]
"""

_SE10_README = """\
# Record lookup

`find_matching(haystack, needles)` returns haystack items that appear in
`needles`, preserving needle order. The naive nested scan does not scale.
"""

_SE10_CFG = """\
{"index": "recommended"}
"""


def _build_se10(dest: Path, fixed: bool) -> None:
    _write(dest, "search.py", _SE10_SEARCH_FIXED if fixed else _SE10_SEARCH_BROKEN)
    _write(dest, "app.py", _SE10_APP)
    _write(dest, "test_search.py", _SE10_TEST)
    _write(dest, "README.md", _SE10_README)
    _write(dest, "search.json", _SE10_CFG)


def _verify_se10(workspace: Path) -> VerifierResult:
    script = r"""
from search import find_matching

class Probe(object):
    comparisons = 0

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        Probe.comparisons += 1
        if isinstance(other, Probe):
            return self.value == other.value
        return self.value == other

    def __hash__(self):
        return hash(self.value)

size = 2500
haystack = [Probe(i) for i in range(size)]
needles = [Probe(i) for i in range(size - 100, size)]
needles.insert(10, Probe(-7))
Probe.comparisons = 0
got = find_matching(haystack, needles)
expected = list(range(size - 100, size))
assert [item.value for item in got] == expected, [item.value for item in got]
for item in got:
    assert item is haystack[item.value], item.value
assert Probe.comparisons <= 15000, Probe.comparisons
print("ok")
"""
    return _assert_script(workspace, script, timeout=30.0)


_BUILDERS = {
    "se-01-multifile-bug": _build_se01,
    "multifile_bug": _build_se01,
    "se-02-api-migration": _build_se02,
    "api_migration": _build_se02,
    "se-03-schema-migration": _build_se03,
    "schema_migration": _build_se03,
    "se-04-race-condition": _build_se04,
    "race_condition": _build_se04,
    "se-05-cache-invalidation": _build_se05,
    "cache_invalidation": _build_se05,
    "se-06-retry-timeout": _build_se06,
    "retry_timeout": _build_se06,
    "se-07-auth-path-security": _build_se07,
    "auth_path_security": _build_se07,
    "se-08-hidden-edge-case": _build_se08,
    "hidden_edge_case": _build_se08,
    "se-09-coupling-refactor": _build_se09,
    "coupling_refactor": _build_se09,
    "se-10-performance-bottleneck": _build_se10,
    "performance_bottleneck": _build_se10,
}

_VERIFIERS = {
    "se-01-multifile-bug": _verify_se01,
    "multifile_bug": _verify_se01,
    "se-02-api-migration": _verify_se02,
    "api_migration": _verify_se02,
    "se-03-schema-migration": _verify_se03,
    "schema_migration": _verify_se03,
    "se-04-race-condition": _verify_se04,
    "race_condition": _verify_se04,
    "se-05-cache-invalidation": _verify_se05,
    "cache_invalidation": _verify_se05,
    "se-06-retry-timeout": _verify_se06,
    "retry_timeout": _verify_se06,
    "se-07-auth-path-security": _verify_se07,
    "auth_path_security": _verify_se07,
    "se-08-hidden-edge-case": _verify_se08,
    "hidden_edge_case": _verify_se08,
    "se-09-coupling-refactor": _verify_se09,
    "coupling_refactor": _verify_se09,
    "se-10-performance-bottleneck": _verify_se10,
    "performance_bottleneck": _verify_se10,
}
