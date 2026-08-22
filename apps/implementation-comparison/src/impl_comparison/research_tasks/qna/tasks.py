"""QnA research fixtures: read-the-repo workspaces and labeled-answer verifiers."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ...protocol import TaskSpec, VerifierResult

Builder = Callable[[Path], None]


def materialize_qna_task(task: TaskSpec, dest: Path) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    leftover = dest / "answer.txt"
    if leftover.is_file():
        leftover.unlink()
    builder = _lookup(_BUILDERS, task)
    builder(dest)
    return dest


def apply_qna_reference_fix(task: TaskSpec, workspace: Path) -> None:
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    spec = _lookup(_SPECS, task)
    _write(workspace, "answer.txt", _format_gold(spec))


def verify_qna_task(task: TaskSpec, workspace: Path) -> VerifierResult:
    workspace = Path(workspace)
    spec = _lookup(_SPECS, task)
    return _verify_spec(workspace, spec)


def _lookup(table: Dict[str, object], task: TaskSpec) -> object:
    if task.task_id in table:
        return table[task.task_id]
    if task.verifier_name in table:
        return table[task.verifier_name]
    raise ValueError("unknown QnA task: {}".format(task.task_id))


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


def _format_gold(spec: Dict[str, object]) -> str:
    gold = spec["gold"]
    lines = []
    for key in spec["required"]:
        lines.append("{}: {}\n".format(key, gold[key]))
    return "".join(lines)


def _parse_labeled_answer(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
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
            values[key] = value
    return values


def _canonical(kind: str, value: str) -> object:
    text = str(value).strip()
    if kind == "states":
        return tuple(
            part.strip().lower() for part in text.split(",") if part.strip()
        )
    if kind == "transition":
        compact = text.replace(" ", "").replace("\\", "/").replace("→", "->")
        return compact.lower()
    if kind == "none_result":
        return " ".join(text.replace("_", " ").split()).lower()
    if kind == "slash":
        return text.replace("\\", "/")
    return text


def _path_keys(spec: Dict[str, object]) -> Tuple[str, ...]:
    explicit = spec.get("path_keys")
    if explicit:
        return tuple(explicit)
    return tuple((spec.get("api") or {}).values())


def _workspace_file(workspace: Path, relative: str) -> Optional[Path]:
    raw = relative.strip().replace("\\", "/")
    if raw.startswith("./"):
        raw = raw[2:]
    if not raw or raw.startswith("/") or raw.startswith("~"):
        return None
    if ".." in Path(raw).parts:
        return None
    workspace = workspace.resolve()
    path = (workspace / raw).resolve()
    try:
        path.relative_to(workspace)
    except ValueError:
        return None
    if path.is_file():
        return path
    return None


def _defined_names(path: Path) -> List[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
    return names


def _answer_format(rows: Sequence[Tuple[str, str]]) -> str:
    lines = [
        "# Answer format",
        "",
        "Write `answer.txt` with one `key: value` pair per line.",
        "Key names are listed below. Values must come from this repository;",
        "do not invent files, functions, or architecture options.",
        "",
        "Required keys:",
    ]
    for key, blurb in rows:
        lines.append("- `{}`: {}".format(key, blurb))
    lines.append("")
    return "\n".join(lines)


def _verify_spec(workspace: Path, spec: Dict[str, object]) -> VerifierResult:
    answer_path = workspace / "answer.txt"
    if not answer_path.is_file():
        return _result(False, "answer.txt missing")
    try:
        text = answer_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _result(False, "answer.txt unreadable: {}".format(exc))
    parsed = _parse_labeled_answer(text)
    required = spec["required"]
    gold = spec["gold"]
    for key in required:
        value = parsed.get(key)
        if value is None or not str(value).strip():
            return _result(False, "missing required key {}".format(key))
    for key in _path_keys(spec):
        value = parsed.get(key, "")
        if _workspace_file(workspace, value) is None:
            return _result(False, "nonexistent path {}".format(value))
    pair_keys = spec.get("pair_keys") or ()
    if pair_keys:
        got = {parsed.get(key) for key in pair_keys}
        want = {gold[key] for key in pair_keys}
        if got != want:
            return _result(False, "trade-off mismatch")
    allowed = spec.get("allowed") or {}
    contains = spec.get("contains") or {}
    canon = spec.get("canon") or {}
    skip = set(pair_keys)
    for key, want in gold.items():
        if key in skip:
            continue
        got = parsed.get(key, "")
        kind = canon.get(key)
        if kind:
            got_c = _canonical(kind, got)
            if key in allowed:
                options = {_canonical(kind, opt) for opt in allowed[key]}
                if got_c not in options:
                    return _result(False, "unsupported value for {}".format(key))
                continue
            if got_c != _canonical(kind, want):
                return _result(False, "mismatch for {}".format(key))
            continue
        if key in allowed:
            if got not in allowed[key]:
                return _result(False, "unsupported value for {}".format(key))
            continue
        needles = contains.get(key)
        if needles:
            lowered = got.lower()
            for needle in needles:
                if needle.lower() not in lowered:
                    return _result(False, "omitted fact in {}".format(key))
            continue
        if got != want:
            return _result(False, "mismatch for {}".format(key))
    for name_key, path_key in (spec.get("api") or {}).items():
        name = parsed.get(name_key, "")
        cited = parsed.get(path_key, "")
        path = _workspace_file(workspace, cited)
        if path is None:
            return _result(False, "cited file missing for {}".format(name_key))
        if name not in _defined_names(path):
            return _result(False, "unsupported api {}".format(name))
    return _result(True, "qna ok")


# ---------------------------------------------------------------------------
# qna-01 call graph
# ---------------------------------------------------------------------------

_QNA01_API = """\
from service import process_order


def handle_request(payload):
    return process_order(payload)
"""

_QNA01_SERVICE = """\
from audit import write_event
from db import insert_row
from models import build_record


def process_order(payload):
    record = build_record(payload)
    insert_row(record)
    write_event("stored")
    return record
"""

_QNA01_MODELS = """\
def build_record(payload):
    return {"sku": payload.get("sku"), "qty": int(payload.get("qty", 0))}
"""

_QNA01_DB = """\
from models import build_record

_ROWS = []


def insert_row(record):
    _ROWS.append(record)
    return record


def seed(payload):
    return insert_row(build_record(payload))
"""

_QNA01_AUDIT = """\
from models import build_record

_EVENTS = []


def write_event(name):
    _EVENTS.append(name)
    return name


def describe(payload):
    return build_record(payload)
"""

_QNA01_README = """\
# Order intake

HTTP traffic enters this package and is stored. Trace the public entrypoint
through the domain layer to the persistence write. Follow imports; do not
guess module names.
"""

_QNA01_FORMAT = _answer_format(
    [
        ("caller", "function name of the public entrypoint"),
        ("caller_path", "file that defines caller"),
        ("intermediate", "function between the entrypoint and persistence"),
        ("intermediate_path", "file that defines intermediate"),
        ("sink", "function that performs the persistence write"),
        ("sink_path", "file that defines sink"),
    ]
)


def _build_qna01(dest: Path) -> None:
    _write(dest, "api.py", _QNA01_API)
    _write(dest, "service.py", _QNA01_SERVICE)
    _write(dest, "models.py", _QNA01_MODELS)
    _write(dest, "db.py", _QNA01_DB)
    _write(dest, "audit.py", _QNA01_AUDIT)
    _write(dest, "README.md", _QNA01_README)
    _write(dest, "ANSWER_FORMAT.md", _QNA01_FORMAT)


_QNA01_SPEC = {
    "required": (
        "caller",
        "caller_path",
        "intermediate",
        "intermediate_path",
        "sink",
        "sink_path",
    ),
    "gold": {
        "caller": "handle_request",
        "caller_path": "api.py",
        "intermediate": "process_order",
        "intermediate_path": "service.py",
        "sink": "insert_row",
        "sink_path": "db.py",
    },
    "api": {
        "caller": "caller_path",
        "intermediate": "intermediate_path",
        "sink": "sink_path",
    },
}


# ---------------------------------------------------------------------------
# qna-02 config impact
# ---------------------------------------------------------------------------

_QNA02_CONFIG_JSON = """\
{
  "idle_timeout": 2,
  "batch_size": 8
}
"""

_QNA02_SETTINGS = """\
DEFAULTS = {"idle_timeout": 30, "batch_size": 1}
"""

_QNA02_CONFIG = """\
import json
from pathlib import Path

from settings import DEFAULTS


def load_settings():
    raw = json.loads(Path("config.json").read_text(encoding="utf-8"))
    merged = dict(DEFAULTS)
    merged.update(raw)
    return merged
"""

_QNA02_WORKER = """\
from config import load_settings


def run_batch():
    cfg = load_settings()
    timeout = cfg["idle_timeout"]
    return {"idle_wait_seconds": timeout, "processed": cfg["batch_size"]}
"""

_QNA02_APP = """\
from worker import run_batch


def main():
    return run_batch()
"""

_QNA02_RUNNER = """\
from app import main


def start():
    return main()
"""

_QNA02_README = """\
# Batch worker

Runtime settings live in `config.json` and are merged with defaults.
Changing a setting alters how long the worker waits between batches.
"""

_QNA02_FORMAT = _answer_format(
    [
        ("config_key", "JSON key whose value changes wait time"),
        ("parser", "function that loads and merges settings"),
        ("parser_path", "file that defines parser"),
        ("consumer", "function that reads the key at runtime"),
        ("consumer_path", "file that defines consumer"),
        ("behavior_change", "metric or field that moves when the key changes"),
    ]
)


def _build_qna02(dest: Path) -> None:
    _write(dest, "config.json", _QNA02_CONFIG_JSON)
    _write(dest, "settings.py", _QNA02_SETTINGS)
    _write(dest, "config.py", _QNA02_CONFIG)
    _write(dest, "worker.py", _QNA02_WORKER)
    _write(dest, "app.py", _QNA02_APP)
    _write(dest, "runner.py", _QNA02_RUNNER)
    _write(dest, "README.md", _QNA02_README)
    _write(dest, "ANSWER_FORMAT.md", _QNA02_FORMAT)


_QNA02_SPEC = {
    "required": (
        "config_key",
        "parser",
        "parser_path",
        "consumer",
        "consumer_path",
        "behavior_change",
    ),
    "gold": {
        "config_key": "idle_timeout",
        "parser": "load_settings",
        "parser_path": "config.py",
        "consumer": "run_batch",
        "consumer_path": "worker.py",
        "behavior_change": "idle_wait_seconds",
    },
    "api": {
        "parser": "parser_path",
        "consumer": "consumer_path",
    },
}


# ---------------------------------------------------------------------------
# qna-03 root cause
# ---------------------------------------------------------------------------

_QNA03_TOKENS = """\
def split_spec(text):
    start_s, end_s = text.split("-")
    return int(start_s), int(end_s)
"""

_QNA03_PARSER = """\
from tokens import split_spec


def parse_bounds(text):
    start, end = split_spec(text)
    exclusive_stop = end
    return list(range(start, exclusive_stop))
"""

_QNA03_ITEMS = """\
def as_items(values):
    return list(values)
"""

_QNA03_LISTING = """\
from items import as_items
from parser import parse_bounds


def list_items(spec):
    return as_items(parse_bounds(spec))
"""

_QNA03_CLI = """\
from listing import list_items


def main(spec):
    return list_items(spec)
"""

_QNA03_NOTES = """\
# Failure notes

Command `list 1-10` is supposed to print every integer from 1 through 10.
The current output is `1 2 3 4 5 6 7 8 9` — the last value is missing.
"""

_QNA03_README = """\
# Inclusive listing

`cli.main` prints a numeric range described as `start-end`.
The notes describe a missing final value. Find the defect and the function
that must change.
"""

_QNA03_FORMAT = _answer_format(
    [
        ("root_cause", "snake_case label for the defect class found in code"),
        ("triggering_input", "the range spec that reproduces the missing last value"),
        ("fix_path", "file that contains the defect"),
        ("fix_function", "function that must be edited"),
    ]
)


def _build_qna03(dest: Path) -> None:
    _write(dest, "tokens.py", _QNA03_TOKENS)
    _write(dest, "parser.py", _QNA03_PARSER)
    _write(dest, "items.py", _QNA03_ITEMS)
    _write(dest, "listing.py", _QNA03_LISTING)
    _write(dest, "cli.py", _QNA03_CLI)
    _write(dest, "NOTES.md", _QNA03_NOTES)
    _write(dest, "README.md", _QNA03_README)
    _write(dest, "ANSWER_FORMAT.md", _QNA03_FORMAT)


_QNA03_SPEC = {
    "required": ("root_cause", "triggering_input", "fix_path", "fix_function"),
    "gold": {
        "root_cause": "exclusive_stop",
        "triggering_input": "1-10",
        "fix_path": "parser.py",
        "fix_function": "parse_bounds",
    },
    "allowed": {
        "root_cause": ("exclusive_stop", "off_by_one", "off-by-one"),
    },
    "api": {
        "fix_function": "fix_path",
    },
}


# ---------------------------------------------------------------------------
# qna-04 change impact
# ---------------------------------------------------------------------------

_QNA04_MODELS = """\
def item_label(n):
    return "item-{}".format(n)
"""

_QNA04_CORE = """\
from models import item_label


def build_core(n):
    return item_label(n)
"""

_QNA04_MID = """\
from core import build_core


def apply_mid(n):
    return build_core(n)
"""

_QNA04_APP = """\
from mid import apply_mid


def render_app(n):
    return apply_mid(n)
"""

_QNA04_TEST = """\
from app import render_app


def test_render_output():
    assert render_app(2) == "item-2"
"""

_QNA04_README = """\
# Label pipeline

A proposed edit to the lowest-level builder will travel through the
import chain. Identify the immediate importer, the next consumer, and
the test that exercises the public output.
"""

_QNA04_FORMAT = _answer_format(
    [
        ("direct_dependency", "function in the module that imports the core builder"),
        ("direct_path", "file that defines direct_dependency"),
        ("transitive_dependency", "function in the next consumer above that module"),
        ("transitive_path", "file that defines transitive_dependency"),
        ("affected_test", "test function that covers the public output"),
        ("test_path", "file that defines affected_test"),
    ]
)


def _build_qna04(dest: Path) -> None:
    _write(dest, "models.py", _QNA04_MODELS)
    _write(dest, "core.py", _QNA04_CORE)
    _write(dest, "mid.py", _QNA04_MID)
    _write(dest, "app.py", _QNA04_APP)
    _write(dest, "test_app.py", _QNA04_TEST)
    _write(dest, "README.md", _QNA04_README)
    _write(dest, "ANSWER_FORMAT.md", _QNA04_FORMAT)


_QNA04_SPEC = {
    "required": (
        "direct_dependency",
        "direct_path",
        "transitive_dependency",
        "transitive_path",
        "affected_test",
        "test_path",
    ),
    "gold": {
        "direct_dependency": "apply_mid",
        "direct_path": "mid.py",
        "transitive_dependency": "render_app",
        "transitive_path": "app.py",
        "affected_test": "test_render_output",
        "test_path": "test_app.py",
    },
    "api": {
        "direct_dependency": "direct_path",
        "transitive_dependency": "transitive_path",
        "affected_test": "test_path",
    },
}


# ---------------------------------------------------------------------------
# qna-05 security path
# ---------------------------------------------------------------------------

_QNA05_MODELS = """\
class Document(object):
    def __init__(self, body):
        self.body = body
"""

_QNA05_STORE = """\
from pathlib import Path

ROOT = Path("data")


def read_blob(name):
    return (ROOT / name).read_text(encoding="utf-8")
"""

_QNA05_PATHS = """\
def clamp_relative(name):
    cleaned = name.replace("\\\\", "/")
    if name.startswith("..") or "/.." in cleaned:
        raise ValueError("dotdot_outside")
    return name
"""

_QNA05_AUDIT = """\
_LOG = []


def log_read(name):
    _LOG.append(name)
    return name
"""

_QNA05_HANDLER = """\
from audit import log_read
from models import Document
from paths import clamp_relative
from store import read_blob

UNTRUSTED_EXAMPLE = "../secret.txt"


def fetch_document(name):
    log_read(name)
    return Document(read_blob(name))


def unused_guard(name):
    return clamp_relative(name)
"""

_QNA05_SERVER = """\
from handler import fetch_document


def serve(name):
    return fetch_document(name)
"""

_QNA05_README = """\
# Document fetch

Blobs under `data/` are read using a caller-supplied name.
Relative names are not forced to stay inside that directory.
A helper that rejects escaping names already exists; cite it as the
mitigation rather than inventing a new API.
"""

_QNA05_FORMAT = _answer_format(
    [
        ("attack_input", "untrusted relative name that would escape the data directory"),
        ("vulnerable_boundary", "function that accepts the untrusted name"),
        ("boundary_path", "file that defines vulnerable_boundary"),
        ("mitigation", "existing function that rejects escaping names"),
        ("mitigation_path", "file that defines mitigation"),
    ]
)


def _build_qna05(dest: Path) -> None:
    _write(dest, "models.py", _QNA05_MODELS)
    _write(dest, "store.py", _QNA05_STORE)
    _write(dest, "paths.py", _QNA05_PATHS)
    _write(dest, "audit.py", _QNA05_AUDIT)
    _write(dest, "handler.py", _QNA05_HANDLER)
    _write(dest, "server.py", _QNA05_SERVER)
    _write(dest, "data/public.txt", "public document\n")
    _write(dest, "README.md", _QNA05_README)
    _write(dest, "ANSWER_FORMAT.md", _QNA05_FORMAT)


_QNA05_SPEC = {
    "required": (
        "attack_input",
        "vulnerable_boundary",
        "boundary_path",
        "mitigation",
        "mitigation_path",
    ),
    "gold": {
        "attack_input": "../secret.txt",
        "vulnerable_boundary": "fetch_document",
        "boundary_path": "handler.py",
        "mitigation": "clamp_relative",
        "mitigation_path": "paths.py",
    },
    "path_keys": ("boundary_path", "mitigation_path"),
    "allowed": {
        "attack_input": ("../secret.txt",),
    },
    "canon": {
        "attack_input": "slash",
    },
    "api": {
        "vulnerable_boundary": "boundary_path",
        "mitigation": "mitigation_path",
    },
}


# ---------------------------------------------------------------------------
# qna-06 test gap
# ---------------------------------------------------------------------------

_QNA06_UTIL = """\
def upper(text):
    return text.upper()
"""

_QNA06_REPORT = """\
from util import upper


def format_label(text):
    return upper(text)
"""

_QNA06_RULES = """\
from report import format_label


def normalize(text):
    return format_label(text.strip())
"""

_QNA06_LABELS = """\
from rules import normalize


def process_label(label):
    empty_label = label == ""
    if empty_label:
        return None
    return normalize(label)
"""

_QNA06_TEST = """\
from labels import process_label


def test_typical_label():
    assert process_label("hello") == "HELLO"
"""

_QNA06_README = """\
# Label processor

Visible tests cover the typical non-empty input. Inspect the implementation
for a branch the tests never enter, what that branch returns, and propose a
test name that mentions the branch.
"""

_QNA06_FORMAT = _answer_format(
    [
        ("missing_branch", "identifier of the untested branch in the implementation"),
        ("observable_behavior", "Python value returned by that branch"),
        ("proposed_test", "test name or idea that mentions the missing branch"),
        ("impl_path", "file that contains the untested branch"),
    ]
)


def _build_qna06(dest: Path) -> None:
    _write(dest, "util.py", _QNA06_UTIL)
    _write(dest, "report.py", _QNA06_REPORT)
    _write(dest, "rules.py", _QNA06_RULES)
    _write(dest, "labels.py", _QNA06_LABELS)
    _write(dest, "test_labels.py", _QNA06_TEST)
    _write(dest, "README.md", _QNA06_README)
    _write(dest, "ANSWER_FORMAT.md", _QNA06_FORMAT)


_QNA06_SPEC = {
    "required": (
        "missing_branch",
        "observable_behavior",
        "proposed_test",
        "impl_path",
    ),
    "gold": {
        "missing_branch": "empty_label",
        "observable_behavior": "returns None",
        "proposed_test": "test_empty_label",
        "impl_path": "labels.py",
    },
    "path_keys": ("impl_path",),
    "allowed": {
        "observable_behavior": (
            "None",
            "null",
            "returns None",
            "returns null",
            "return None",
            "return null",
        ),
    },
    "canon": {
        "observable_behavior": "none_result",
    },
    "contains": {
        "proposed_test": ("empty_label", "test"),
    },
}


# ---------------------------------------------------------------------------
# qna-07 performance location
# ---------------------------------------------------------------------------

_QNA07_STATS = """\
_METRICS = {}


def record_metric(name, value):
    _METRICS[name] = value
    return value
"""

_QNA07_INDEX = """\
from stats import record_metric


def build_index(haystack):
    table = {}
    for item in haystack:
        table[item] = item
    record_metric("index_size", len(table))
    return table
"""

_QNA07_SEARCH = """\
from index import build_index


def find_matching(haystack, needles):
    found = []
    for needle in needles:
        for item in haystack:
            if item == needle:
                found.append(item)
                break
    return found


def unused_index(haystack):
    return build_index(haystack)
"""

_QNA07_MEASURE = """\
\"\"\"Measurement command: python3 -m timeit\"\"\"

from search import find_matching
from stats import record_metric


def measure():
    data = list(range(40))
    result = find_matching(data, data)
    record_metric("elapsed_ms", 1)
    return result
"""

_QNA07_APP = """\
from measure import measure
from search import find_matching


def run(haystack, needles):
    measure()
    return find_matching(haystack, needles)
"""

_QNA07_README = """\
# Lookup service

Matching is implemented with a nested scan. Time the hot function with the
command documented next to the measurement helper, and name the metric that
helper records.
"""

_QNA07_FORMAT = _answer_format(
    [
        ("hot_path", "function that performs the nested scan"),
        ("hot_path_file", "file that defines hot_path"),
        ("measure_command", "command documented for timing that function"),
        ("expected_metric", "metric name recorded by the measurement helper"),
    ]
)


def _build_qna07(dest: Path) -> None:
    _write(dest, "stats.py", _QNA07_STATS)
    _write(dest, "index.py", _QNA07_INDEX)
    _write(dest, "search.py", _QNA07_SEARCH)
    _write(dest, "measure.py", _QNA07_MEASURE)
    _write(dest, "app.py", _QNA07_APP)
    _write(dest, "README.md", _QNA07_README)
    _write(dest, "ANSWER_FORMAT.md", _QNA07_FORMAT)


_QNA07_SPEC = {
    "required": (
        "hot_path",
        "hot_path_file",
        "measure_command",
        "expected_metric",
    ),
    "gold": {
        "hot_path": "find_matching",
        "hot_path_file": "search.py",
        "measure_command": "python3 -m timeit",
        "expected_metric": "elapsed_ms",
    },
    "api": {
        "hot_path": "hot_path_file",
    },
}


# ---------------------------------------------------------------------------
# qna-08 state flow
# ---------------------------------------------------------------------------

_QNA08_MODELS = """\
class Order(object):
    def __init__(self, order_id):
        self.order_id = order_id
        self.state = "draft"
"""

_QNA08_EVENTS = """\
_EVENTS = []


def emit(name):
    _EVENTS.append(name)
    return name
"""

_QNA08_STORE = """\
from models import Order

_SAVED = {}


def save_order(order):
    _SAVED[order.order_id] = order.state
    return order


def load_order(order_id):
    order = Order(order_id)
    order.state = _SAVED.get(order_id, "draft")
    return order
"""

_QNA08_ORDERS = """\
from events import emit
from models import Order
from store import save_order

STATES = ("draft", "paid", "shipped")
ALLOWED = (("draft", "paid"), ("paid", "shipped"))


def can_transition(current, nxt):
    return (current, nxt) in ALLOWED


def pay(order):
    if not can_transition(order.state, "paid"):
        raise ValueError("invalid")
    order.state = "paid"
    save_order(order)
    emit("paid")
    return order


def new_order(order_id):
    return Order(order_id)
"""

_QNA08_APP = """\
from orders import new_order, pay


def checkout(order_id):
    order = new_order(order_id)
    return pay(order)
"""

_QNA08_README = """\
# Checkout states

An order starts in one named state, can move through a small allow-list,
and is written back through the store module. List the states, one legal
transition, and the function that persists the record.
"""

_QNA08_FORMAT = _answer_format(
    [
        ("states", "comma-separated state names in order"),
        ("valid_transition", "one allowed edge written as from->to"),
        ("persistence_point", "function that writes the order record"),
        ("persist_path", "file that defines persistence_point"),
    ]
)


def _build_qna08(dest: Path) -> None:
    _write(dest, "models.py", _QNA08_MODELS)
    _write(dest, "events.py", _QNA08_EVENTS)
    _write(dest, "store.py", _QNA08_STORE)
    _write(dest, "orders.py", _QNA08_ORDERS)
    _write(dest, "app.py", _QNA08_APP)
    _write(dest, "README.md", _QNA08_README)
    _write(dest, "ANSWER_FORMAT.md", _QNA08_FORMAT)


_QNA08_SPEC = {
    "required": (
        "states",
        "valid_transition",
        "persistence_point",
        "persist_path",
    ),
    "gold": {
        "states": "draft,paid,shipped",
        "valid_transition": "draft->paid",
        "persistence_point": "save_order",
        "persist_path": "store.py",
    },
    "path_keys": ("persist_path",),
    "allowed": {
        "valid_transition": ("draft->paid", "paid->shipped"),
    },
    "canon": {
        "states": "states",
        "valid_transition": "transition",
    },
    "api": {
        "persistence_point": "persist_path",
    },
}


# ---------------------------------------------------------------------------
# qna-09 recovery path
# ---------------------------------------------------------------------------

_QNA09_LOGUTIL = """\
_LINES = []


def log_event(name):
    _LINES.append(name)
    return name
"""

_QNA09_REMOTE = """\
def fetch_remote():
    raise ConnectionError("unavailable")
"""

_QNA09_STORE = """\
from logutil import log_event

_BATCH = {"dirty": True}


def rollback_batch():
    _BATCH["dirty"] = False
    log_event("rollback")
    return _BATCH


def mark_terminal(state):
    _BATCH["state"] = state
    return state
"""

_QNA09_WORKER = """\
from logutil import log_event
from remote import fetch_remote
from store import mark_terminal, rollback_batch

MAX_TRIES = 3


def retry_fetch():
    last = None
    for _ in range(MAX_TRIES):
        try:
            return fetch_remote()
        except Exception as exc:
            last = exc
            log_event("retry")
    raise last


def run_job():
    try:
        return retry_fetch()
    except Exception:
        rollback_batch()
        return mark_terminal("failed")
"""

_QNA09_APP = """\
from worker import run_job


def main():
    return run_job()
"""

_QNA09_README = """\
# Ingest worker

Outbound fetch can fail. The worker retries, then rolls the in-memory batch
back and records a terminal state. Name the failing call, the retry and
rollback functions, and that terminal state.
"""

_QNA09_FORMAT = _answer_format(
    [
        ("failure_boundary", "function whose failure starts recovery"),
        ("remote_path", "file that defines failure_boundary"),
        ("retry_path", "function that retries the failing call"),
        ("worker_path", "file that defines retry_path"),
        ("rollback_path", "function that undoes the in-memory batch"),
        ("store_path", "file that defines rollback_path"),
        ("terminal_state", "state stored after rollback"),
    ]
)


def _build_qna09(dest: Path) -> None:
    _write(dest, "logutil.py", _QNA09_LOGUTIL)
    _write(dest, "remote.py", _QNA09_REMOTE)
    _write(dest, "store.py", _QNA09_STORE)
    _write(dest, "worker.py", _QNA09_WORKER)
    _write(dest, "app.py", _QNA09_APP)
    _write(dest, "README.md", _QNA09_README)
    _write(dest, "ANSWER_FORMAT.md", _QNA09_FORMAT)


_QNA09_SPEC = {
    "required": (
        "failure_boundary",
        "remote_path",
        "retry_path",
        "worker_path",
        "rollback_path",
        "store_path",
        "terminal_state",
    ),
    "gold": {
        "failure_boundary": "fetch_remote",
        "remote_path": "remote.py",
        "retry_path": "retry_fetch",
        "worker_path": "worker.py",
        "rollback_path": "rollback_batch",
        "store_path": "store.py",
        "terminal_state": "failed",
    },
    "api": {
        "failure_boundary": "remote_path",
        "retry_path": "worker_path",
        "rollback_path": "store_path",
    },
}


# ---------------------------------------------------------------------------
# qna-10 architecture tradeoff
# ---------------------------------------------------------------------------

_QNA10_SETTINGS = """\
def client_limit():
    return 10
"""

_QNA10_QUEUE = """\
_PENDING = []


def enqueue_async(job):
    _PENDING.append(job)
    return "queued"
"""

_QNA10_CLIENT = """\
from settings import client_limit


def call_sync(job):
    return {"job": job, "limit": client_limit()}
"""

_QNA10_RUNTIME = """\
from client import call_sync
from jobqueue import enqueue_async


def dispatch(mode, job):
    if mode == "sync":
        return call_sync(job)
    return enqueue_async(job)
"""

_QNA10_APP = """\
from runtime import dispatch


def handle(mode, job):
    return dispatch(mode, job)
"""

_QNA10_ARCH = """\
# Architecture

Two options are in scope for request handling: **sync** and **async**.
Do not propose additional styles.

## Sync

The handler waits until work finishes. Token: `sync_blocks_caller`.

## Async

The handler returns after enqueueing work. Token: `async_needs_queue`.
This option requires a durable queue.

## Bounded recommendation

Use these tokens only:

- `prefer_sync_under_ten` when the documented client limit is enough
- `prefer_async_above_ten` when the client count grows past that limit
"""

_QNA10_README = """\
# Request runtime

`docs/ARCHITECTURE.md` compares the two supported request models.
Summarize the documented trade-offs and pick one bounded recommendation.
"""

_QNA10_FORMAT = _answer_format(
    [
        ("tradeoff_one", "documented trade-off token for the first option"),
        ("tradeoff_two", "documented trade-off token for the second option"),
        ("recommendation", "one bounded recommendation token from the docs"),
        ("doc_path", "path of the architecture note"),
    ]
)


def _build_qna10(dest: Path) -> None:
    _write(dest, "settings.py", _QNA10_SETTINGS)
    _write(dest, "jobqueue.py", _QNA10_QUEUE)
    _write(dest, "client.py", _QNA10_CLIENT)
    _write(dest, "runtime.py", _QNA10_RUNTIME)
    _write(dest, "app.py", _QNA10_APP)
    _write(dest, "docs/ARCHITECTURE.md", _QNA10_ARCH)
    _write(dest, "README.md", _QNA10_README)
    _write(dest, "ANSWER_FORMAT.md", _QNA10_FORMAT)


_QNA10_SPEC = {
    "required": (
        "tradeoff_one",
        "tradeoff_two",
        "recommendation",
        "doc_path",
    ),
    "gold": {
        "tradeoff_one": "sync_blocks_caller",
        "tradeoff_two": "async_needs_queue",
        "recommendation": "prefer_sync_under_ten",
        "doc_path": "docs/ARCHITECTURE.md",
    },
    "pair_keys": ("tradeoff_one", "tradeoff_two"),
    "path_keys": ("doc_path",),
    "allowed": {
        "recommendation": ("prefer_sync_under_ten", "prefer_async_above_ten"),
    },
}


_SPECS = {
    "qna-01-call-graph": _QNA01_SPEC,
    "call_graph": _QNA01_SPEC,
    "qna-02-config-impact": _QNA02_SPEC,
    "config_impact": _QNA02_SPEC,
    "qna-03-root-cause": _QNA03_SPEC,
    "root_cause": _QNA03_SPEC,
    "qna-04-change-impact": _QNA04_SPEC,
    "change_impact": _QNA04_SPEC,
    "qna-05-security-path": _QNA05_SPEC,
    "security_path": _QNA05_SPEC,
    "qna-06-test-gap": _QNA06_SPEC,
    "test_gap": _QNA06_SPEC,
    "qna-07-performance-location": _QNA07_SPEC,
    "performance_location": _QNA07_SPEC,
    "qna-08-state-flow": _QNA08_SPEC,
    "state_flow": _QNA08_SPEC,
    "qna-09-recovery-path": _QNA09_SPEC,
    "recovery_path": _QNA09_SPEC,
    "qna-10-architecture-tradeoff": _QNA10_SPEC,
    "architecture_tradeoff": _QNA10_SPEC,
}

_BUILDERS = {
    "qna-01-call-graph": _build_qna01,
    "call_graph": _build_qna01,
    "qna-02-config-impact": _build_qna02,
    "config_impact": _build_qna02,
    "qna-03-root-cause": _build_qna03,
    "root_cause": _build_qna03,
    "qna-04-change-impact": _build_qna04,
    "change_impact": _build_qna04,
    "qna-05-security-path": _build_qna05,
    "security_path": _build_qna05,
    "qna-06-test-gap": _build_qna06,
    "test_gap": _build_qna06,
    "qna-07-performance-location": _build_qna07,
    "performance_location": _build_qna07,
    "qna-08-state-flow": _build_qna08,
    "state_flow": _build_qna08,
    "qna-09-recovery-path": _build_qna09,
    "recovery_path": _build_qna09,
    "qna-10-architecture-tradeoff": _build_qna10,
    "architecture_tradeoff": _build_qna10,
}
