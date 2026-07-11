# GAIA DAG Node Evaluators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert this repo into a frozen-worker, eval-only study that compares five DAG node evaluators on GAIA Level 2–3 (plus `--demo` smoke).

**Architecture:** Role-separated package `src/gaia_dag/` with Phase A (worker → traces) and Phase B (evaluate × 5 on identical traces). Existing BPD `dagcore` moves to `legacy/dagcore` and is not on the runtime path.

**Tech Stack:** Python 3.10+, pydantic (or dataclasses), openai, anthropic, google-generativeai, datasets, pypdf, python-dotenv, pytest, numpy (cosine).

**Spec:** `docs/superpowers/specs/2026-07-11-gaia-node-evaluators-design.md`

---

## File structure (create / move)

| Path | Responsibility |
|------|----------------|
| `legacy/dagcore/` | Former BPD matrix core (moved from `src/dagcore`) |
| `src/gaia_dag/__init__.py` | Package export |
| `src/gaia_dag/models.py` | `Node`, `Graph`, `NodeStatus`, `EvaluationResult` |
| `src/gaia_dag/orchestrator.py` | Topo sort + resolve inputs + run worker/eval |
| `src/gaia_dag/routing.py` | Fixed ambiguity → PASS/FAIL/AMBIGUOUS |
| `src/gaia_dag/worker.py` | `run_worker` / secondary sample |
| `src/gaia_dag/llm/clients.py` | OpenAI / Anthropic / Gemini wrappers + embeddings + logprobs |
| `src/gaia_dag/graphs/gaia_pipeline.py` | Build Plan→Solve→Answer |
| `src/gaia_dag/benchmarks/gaia_loader.py` | Demo + HF GAIA loader |
| `src/gaia_dag/scoring/gaia_em.py` | Normalize + EM + answer extract |
| `src/gaia_dag/evaluators/base.py` | Protocol + shared critic helpers |
| `src/gaia_dag/evaluators/*.py` | Five methods |
| `src/gaia_dag/metrics.py` | Aggregate ranking / eval_score |
| `src/gaia_dag/traces.py` | Save/load worker traces |
| `scripts/run_gaia_worker.py` | Phase A CLI |
| `scripts/run_gaia_eval.py` | Phase B CLI |
| `tests/` | Unit + mocked integration |
| `.env.example` | Already created |
| `pyproject.toml` / `README.md` | Retarget to gaia_dag |

---

### Task 1: Repo conversion scaffold

**Files:**
- Move: `src/dagcore/` → `legacy/dagcore/`
- Move: `tests/test_graph.py` → `legacy/tests/test_graph.py` (optional keep)
- Create: `src/gaia_dag/__init__.py`
- Modify: `pyproject.toml`
- Modify: `.gitignore` (ensure `.env`, `results/`)
- Note: `.env.example` already exists

- [ ] **Step 1: Move legacy package**

```bash
mkdir -p legacy
git mv src/dagcore legacy/dagcore
mkdir -p legacy/tests
git mv tests/test_graph.py legacy/tests/test_graph.py 2>/dev/null || true
mkdir -p src/gaia_dag tests scripts results/gaia/worker_traces
touch src/gaia_dag/__init__.py
```

- [ ] **Step 2: Rewrite `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "gaia-dag"
version = "0.1.0"
description = "Frozen-worker GAIA study comparing five DAG node evaluators."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
dependencies = [
  "openai>=1.40",
  "anthropic>=0.34",
  "google-generativeai>=0.8",
  "datasets>=2.20",
  "huggingface_hub>=0.24",
  "pypdf>=4.0",
  "python-dotenv>=1.0",
  "numpy>=1.26",
]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: scaffold gaia_dag package; move dagcore to legacy"
```

---

### Task 2: Models + routing + orchestrator

**Files:**
- Create: `src/gaia_dag/models.py`
- Create: `src/gaia_dag/routing.py`
- Create: `src/gaia_dag/orchestrator.py`
- Test: `tests/test_models_orchestrator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models_orchestrator.py
from gaia_dag.models import Node, Graph, NodeStatus
from gaia_dag.orchestrator import topological_order, resolve_inputs, run_graph
from gaia_dag.routing import compute_status, ambiguity_index


def test_topo_order_plan_solve_answer():
    g = Graph(nodes={
        "Answer": Node(node_id="Answer", task_description="a", depends_on=["Solve"]),
        "Plan": Node(node_id="Plan", task_description="p", depends_on=[]),
        "Solve": Node(node_id="Solve", task_description="s", depends_on=["Plan"]),
    })
    assert topological_order(g) == ["Plan", "Solve", "Answer"]


def test_resolve_inputs_from_parents():
    plan = Node(node_id="Plan", task_description="p", depends_on=[], output_data="PLAN")
    solve = Node(node_id="Solve", task_description="s", depends_on=["Plan"])
    g = Graph(nodes={"Plan": plan, "Solve": solve})
    resolve_inputs(g, "Solve")
    assert g.nodes["Solve"].input_data["Plan"] == "PLAN"


def test_routing_thresholds():
    assert compute_status(D=0.0, C=1.0, S=1.0) == NodeStatus.PASS
    assert compute_status(D=1.0, C=0.0, S=0.0) == NodeStatus.FAIL
    assert 0.0 <= ambiguity_index(0.4, 0.5, 0.5) <= 1.0


def test_run_graph_worker_only_sets_outputs():
    calls = []

    def fake_worker(node: Node) -> Node:
        node.output_data = f"out:{node.node_id}"
        calls.append(node.node_id)
        return node

    g = Graph(nodes={
        "Plan": Node(node_id="Plan", task_description="p", depends_on=[]),
        "Solve": Node(node_id="Solve", task_description="s", depends_on=["Plan"]),
    })
    run_graph(g, worker_fn=fake_worker, evaluate_fn=None)
    assert calls == ["Plan", "Solve"]
    assert g.nodes["Solve"].input_data["Plan"] == "out:Plan"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_models_orchestrator.py -v
```

Expected: import / not found errors.

- [ ] **Step 3: Implement models**

```python
# src/gaia_dag/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    AMBIGUOUS = "AMBIGUOUS"
    PENDING = "PENDING"


@dataclass
class Node:
    node_id: str
    task_description: str
    depends_on: list[str] = field(default_factory=list)
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: str | None = None
    status: NodeStatus = NodeStatus.PENDING
    C: float | None = None
    D: float | None = None
    S: float | None = None
    DSS: float | None = None
    eval_meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Graph:
    nodes: dict[str, Node]


@dataclass
class EvaluationResult:
    method: str
    task_id: str
    predicted: str
    gold_answer: str
    em: bool
    D: float | None
    C: float | None
    S: float | None
    DSS: float | None
    status: NodeStatus
    per_node: dict[str, dict[str, Any]] = field(default_factory=dict)
```

- [ ] **Step 4: Implement routing**

```python
# src/gaia_dag/routing.py
from __future__ import annotations
from gaia_dag.models import NodeStatus

NEUTRAL = 0.5


def ambiguity_index(D: float | None, C: float | None, S: float | None) -> float:
    d = NEUTRAL if D is None else float(D)
    c = NEUTRAL if C is None else float(C)
    s = NEUTRAL if S is None else float(S)
    return 0.5 * d + 0.3 * (1.0 - c) + 0.2 * (1.0 - s)


def compute_status(D: float | None = None, C: float | None = None, S: float | None = None) -> NodeStatus:
    a = ambiguity_index(D, C, S)
    if a < 0.3:
        return NodeStatus.PASS
    if a >= 0.5:
        return NodeStatus.FAIL
    return NodeStatus.AMBIGUOUS
```

- [ ] **Step 5: Implement orchestrator**

```python
# src/gaia_dag/orchestrator.py
from __future__ import annotations
from collections import deque
from typing import Callable

from gaia_dag.models import Graph, Node


def topological_order(graph: Graph) -> list[str]:
    indeg = {nid: 0 for nid in graph.nodes}
    children: dict[str, list[str]] = {nid: [] for nid in graph.nodes}
    for nid, node in graph.nodes.items():
        for parent in node.depends_on:
            if parent not in graph.nodes:
                raise KeyError(f"Missing parent {parent} for {nid}")
            indeg[nid] += 1
            children[parent].append(nid)
    q = deque([n for n, d in indeg.items() if d == 0])
    order: list[str] = []
    while q:
        n = q.popleft()
        order.append(n)
        for c in children[n]:
            indeg[c] -= 1
            if indeg[c] == 0:
                q.append(c)
    if len(order) != len(graph.nodes):
        raise ValueError("Cycle detected in graph")
    return order


def resolve_inputs(graph: Graph, node_id: str) -> None:
    node = graph.nodes[node_id]
    node.input_data = {
        pid: graph.nodes[pid].output_data for pid in node.depends_on
    }


def run_graph(
    graph: Graph,
    *,
    worker_fn: Callable[[Node], Node] | None = None,
    evaluate_fn: Callable[[Node], Node] | None = None,
) -> Graph:
    for nid in topological_order(graph):
        resolve_inputs(graph, nid)
        node = graph.nodes[nid]
        if worker_fn is not None:
            graph.nodes[nid] = worker_fn(node)
        if evaluate_fn is not None:
            # evaluate must not clear output_data
            before = graph.nodes[nid].output_data
            graph.nodes[nid] = evaluate_fn(graph.nodes[nid])
            if graph.nodes[nid].output_data != before:
                raise RuntimeError(f"evaluate() overwrote output_data on {nid}")
    return graph
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pip install -e ".[dev]" && pytest tests/test_models_orchestrator.py -v
```

- [ ] **Step 7: Commit**

```bash
git add src/gaia_dag tests/test_models_orchestrator.py
git commit -m "feat: add Node/Graph models, routing, and topo orchestrator"
```

---

### Task 3: GAIA EM scorer

**Files:**
- Create: `src/gaia_dag/scoring/__init__.py`
- Create: `src/gaia_dag/scoring/gaia_em.py`
- Test: `tests/test_gaia_em.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_gaia_em.py
from gaia_dag.scoring.gaia_em import normalize_answer, extract_final_answer, exact_match


def test_normalize_strips_articles_and_case():
    assert normalize_answer("The Answer.") == normalize_answer("answer")


def test_extract_final_answer_prefix():
    assert extract_final_answer("Reasoning...\nFinal answer: 42") == "42"


def test_exact_match_numbers():
    assert exact_match("Final answer: 42", "42") is True
    assert exact_match("41", "42") is False
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_gaia_em.py -v
```

- [ ] **Step 3: Implement**

```python
# src/gaia_dag/scoring/gaia_em.py
from __future__ import annotations
import re
import string


def extract_final_answer(text: str) -> str:
    if text is None:
        return ""
    m = re.search(r"final\s*answer\s*:\s*(.+)", text, flags=re.I | re.S)
    if m:
        return m.group(1).strip().splitlines()[0].strip()
    return text.strip().splitlines()[-1].strip()


def normalize_answer(text: str) -> str:
    text = extract_final_answer(text).lower().strip()
    text = "".join(ch for ch in text if ch not in string.punctuation)
    for article in (" a ", " an ", " the "):
        text = text.replace(article, " ")
    text = " ".join(text.split())
    # bare number preference: if looks like number+unit vs bare gold handled at compare time
    return text


def _strip_trailing_units(s: str) -> str:
    return re.sub(r"^([+-]?\d+(?:\.\d+)?)(?:\s+[a-z%]+)?$", r"\1", s)


def exact_match(predicted: str, gold: str) -> bool:
    p = normalize_answer(predicted)
    g = normalize_answer(gold)
    if p == g:
        return True
    # if gold is bare number, compare bare predicted number
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", g):
        return _strip_trailing_units(p) == g
    return False
```

- [ ] **Step 4: Run — expect PASS; commit**

```bash
pytest tests/test_gaia_em.py -v
git add src/gaia_dag/scoring tests/test_gaia_em.py
git commit -m "feat: add GAIA answer normalization and exact match"
```

---

### Task 4: Demo loader + graph builder + traces I/O

**Files:**
- Create: `src/gaia_dag/benchmarks/__init__.py`
- Create: `src/gaia_dag/benchmarks/gaia_loader.py`
- Create: `src/gaia_dag/graphs/__init__.py`
- Create: `src/gaia_dag/graphs/gaia_pipeline.py`
- Create: `src/gaia_dag/traces.py`
- Test: `tests/test_loader_pipeline_traces.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_loader_pipeline_traces.py
from pathlib import Path
from gaia_dag.benchmarks.gaia_loader import load_demo_tasks
from gaia_dag.graphs.gaia_pipeline import build_gaia_graph
from gaia_dag.traces import save_worker_trace, load_worker_trace, trace_path


def test_demo_tasks_nonempty():
    tasks = load_demo_tasks()
    assert len(tasks) >= 2
    assert {"task_id", "question", "gold_answer", "level"} <= set(tasks[0].keys())


def test_build_graph_three_nodes():
    task = load_demo_tasks()[0]
    g = build_gaia_graph(task)
    assert set(g.nodes) == {"Plan", "Solve", "Answer"}
    assert g.nodes["Answer"].depends_on == ["Solve"]


def test_trace_roundtrip(tmp_path: Path):
    task = load_demo_tasks()[0]
    g = build_gaia_graph(task)
    for n in g.nodes.values():
        n.output_data = f"out-{n.node_id}"
    secondaries = {k: f"sec-{k}" for k in g.nodes}
    p = save_worker_trace(tmp_path, task, g, secondaries, worker_model="gpt-4o-mini")
    assert p.exists()
    loaded = load_worker_trace(p)
    assert loaded["nodes"]["Plan"]["output_data"] == "out-Plan"
    assert loaded["secondaries"]["Answer"] == "sec-Answer"
```

- [ ] **Step 2: Implement loader (demo first)**

```python
# src/gaia_dag/benchmarks/gaia_loader.py
from __future__ import annotations
from typing import Any


def load_demo_tasks(max_tasks: int | None = None) -> list[dict[str, Any]]:
    tasks = [
        {
            "task_id": "demo_add_1",
            "level": 2,
            "question": "What is 17 + 25?",
            "gold_answer": "42",
            "file_path": None,
            "file_text": None,
        },
        {
            "task_id": "demo_upper_1",
            "level": 2,
            "question": "Uppercase the word 'gaia' and return only that word.",
            "gold_answer": "GAIA",
            "file_path": None,
            "file_text": None,
        },
        {
            "task_id": "demo_sub_1",
            "level": 3,
            "question": "Compute (100 - 37) / 3. Return an integer.",
            "gold_answer": "21",
            "file_path": None,
            "file_text": None,
        },
        {
            "task_id": "demo_rev_1",
            "level": 2,
            "question": "Reverse the characters of 'stressed' and return only the result.",
            "gold_answer": "desserts",
            "file_path": None,
            "file_text": None,
        },
        {
            "task_id": "demo_len_1",
            "level": 3,
            "question": "How many letters are in the English word 'benchmark'?",
            "gold_answer": "9",
            "file_path": None,
            "file_text": None,
        },
    ]
    if max_tasks is not None:
        tasks = tasks[:max_tasks]
    return tasks


def load_gaia_validation_l2_l3(max_tasks: int | None = None) -> list[dict[str, Any]]:
    """Load HF gaia-benchmark/GAIA validation Level 2+3. Requires HF_TOKEN + terms."""
    from datasets import load_dataset
    # Prefer the official config name used by the gated dataset; adjust if HF schema differs.
    ds = load_dataset("gaia-benchmark/GAIA", "2023_all", split="validation")
    out: list[dict[str, Any]] = []
    for row in ds:
        level = int(row.get("Level") or row.get("level") or 0)
        if level not in (2, 3):
            continue
        tid = str(row.get("task_id") or row.get("Task ID") or row["task_id"])
        question = row.get("Question") or row.get("question")
        gold = row.get("Final answer") or row.get("final_answer") or row.get("Answer")
        file_name = row.get("file_name") or row.get("file_path")
        file_text = None
        # Attachment extraction implemented in Task 5 helper if file present
        out.append({
            "task_id": tid,
            "level": level,
            "question": question,
            "gold_answer": str(gold).strip(),
            "file_path": file_name,
            "file_text": file_text,
            "raw": row,
        })
        if max_tasks is not None and len(out) >= max_tasks:
            break
    return out
```

- [ ] **Step 3: Implement graph builder**

```python
# src/gaia_dag/graphs/gaia_pipeline.py
from __future__ import annotations
from typing import Any
from gaia_dag.models import Graph, Node


def build_gaia_graph(task: dict[str, Any]) -> Graph:
    q = task["question"]
    attach = task.get("file_text") or ""
    attach_block = f"\n\nAttachment text:\n{attach}" if attach else ""

    plan = Node(
        node_id="Plan",
        task_description=(
            "Restate the question clearly and outline step-by-step how to solve it. "
            "Do NOT give the final answer yet.\n\n"
            f"Question: {q}{attach_block}"
        ),
        depends_on=[],
    )
    solve = Node(
        node_id="Solve",
        task_description=(
            "Execute the plan from the upstream Plan node. Provide reasoning and a draft answer. "
            "Use the plan text provided in context."
        ),
        depends_on=["Plan"],
    )
    answer = Node(
        node_id="Answer",
        task_description=(
            "From the Solve draft, emit ONLY a short final answer. "
            "Prefer the format: Final answer: <answer>. "
            "If the gold is typically a bare number, omit units."
        ),
        depends_on=["Solve"],
    )
    return Graph(nodes={"Plan": plan, "Solve": solve, "Answer": answer})
```

- [ ] **Step 4: Implement traces**

```python
# src/gaia_dag/traces.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from gaia_dag.models import Graph


def trace_path(root: Path, task_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in task_id)
    return root / f"{safe}.json"


def save_worker_trace(
    root: Path,
    task: dict[str, Any],
    graph: Graph,
    secondaries: dict[str, str],
    worker_model: str,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = trace_path(root, task["task_id"])
    if path.exists():
        return path  # resume-safe: do not overwrite
    payload = {
        "task_id": task["task_id"],
        "level": task.get("level"),
        "question": task["question"],
        "gold_answer": task["gold_answer"],
        "worker_model": worker_model,
        "nodes": {
            nid: {
                "task_description": n.task_description,
                "output_data": n.output_data,
                "depends_on": list(n.depends_on),
            }
            for nid, n in graph.nodes.items()
        },
        "secondaries": secondaries,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_worker_trace(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def graph_from_trace(trace: dict[str, Any]) -> Graph:
    from gaia_dag.models import Node, Graph
    nodes = {}
    for nid, nd in trace["nodes"].items():
        nodes[nid] = Node(
            node_id=nid,
            task_description=nd["task_description"],
            depends_on=list(nd.get("depends_on") or []),
            output_data=nd.get("output_data"),
        )
    return Graph(nodes=nodes)
```

- [ ] **Step 5: Tests PASS; commit**

```bash
pytest tests/test_loader_pipeline_traces.py -v
git add src/gaia_dag tests/test_loader_pipeline_traces.py
git commit -m "feat: demo loader, GAIA 3-node graph builder, trace I/O"
```

---

### Task 5: LLM clients + worker

**Files:**
- Create: `src/gaia_dag/llm/__init__.py`
- Create: `src/gaia_dag/llm/clients.py`
- Create: `src/gaia_dag/worker.py`
- Create: `src/gaia_dag/attachments.py` (PDF/txt extract)
- Test: `tests/test_worker_mocked.py`

- [ ] **Step 1: Implement clients with env-based config**

`clients.py` must provide:
- `chat_openai(messages, *, model=None, temperature=0.2) -> str`
- `chat_openai_logprobs_yes_no(prompt) -> float`  # C
- `embed_openai(texts: list[str]) -> list[list[float]]`
- `chat_anthropic(messages) -> str`
- `chat_gemini(messages) -> str`
- `cosine(a, b) -> float`
- `available_judge_providers() -> list[str]`
- Retries with exponential backoff (3 tries)
- Load dotenv at import/config time

Worker prompt construction: system + task_description + formatted parent outputs from `input_data`.

```python
# src/gaia_dag/worker.py (core)
def run_worker(node: Node, *, secondary: bool = False) -> Node:
    # call OpenAI; set node.output_data; return node
    ...

def generate_secondary(node: Node) -> str:
    # same prompt, independent sample (temperature slightly higher ok)
    ...
```

- [ ] **Step 2: Mocked test** — patch `chat_openai` to return fixed strings; assert `run_graph` fills outputs and secondaries helper works.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: LLM clients and worker-only generation"
```

---

### Task 6: Phase A CLI (`run_gaia_worker.py`)

**Files:**
- Create: `scripts/run_gaia_worker.py`

- [ ] **Step 1: CLI flags**

```
--demo
--max-tasks N
--out-dir results/gaia/worker_traces
--levels 2,3   # for HF mode
```

Logic:
1. Load tasks (demo or HF).
2. For each task: if trace exists → skip; else build graph, `run_graph(worker)`, generate secondaries per node, `save_worker_trace`.
3. Print summary counts.

- [ ] **Step 2: Smoke with mock** (optional unit) or document live:

```bash
# after OPENAI_API_KEY set:
python scripts/run_gaia_worker.py --demo --max-tasks 2
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: Phase A worker CLI with resume-safe traces"
```

---

### Task 7: Baseline evaluator + eval helpers

**Files:**
- Create: `src/gaia_dag/evaluators/__init__.py`
- Create: `src/gaia_dag/evaluators/base.py`
- Create: `src/gaia_dag/evaluators/baseline.py`
- Test: `tests/test_baseline_eval.py`

Shared helpers in `base.py`:
- `similarity_from_secondary(primary, secondary) -> S`
- `critic_deviation(task_description, output, *, parents=None, providers=...) -> D`
- Critic prompt asks for JSON `{"deviation": 0..1, "confidence": 0..1, "rationale": "..."}` when self-report C needed
- Clamp scores to [0, 1]

Baseline `evaluate(node)`:
1. Require `output_data`
2. Compute S from `node.eval_meta["secondary"]` if present else leave S None/0.5 later in routing
3. Single OpenAI critic **without** parents → D; C from critic JSON confidence
4. `node.status = compute_status(D,C,S)`
5. Return node unchanged `output_data`

- [ ] Tests with mocked critic/embed; commit

```bash
git commit -m "feat: Baseline evaluator (single critic D + embedding S)"
```

---

### Task 8: Phase B CLI skeleton + metrics

**Files:**
- Create: `src/gaia_dag/metrics.py`
- Create: `scripts/run_gaia_eval.py`
- Test: `tests/test_metrics.py`

Metrics:

```python
def eval_score(wrong_high_d, correct_low_d, pass_on_wrong, fail_on_correct) -> float:
    return (
        wrong_high_d * 40
        + correct_low_d * 30
        + (1 - pass_on_wrong) * 20
        + (1 - fail_on_correct) * 10
    )
```

`run_gaia_eval.py`:
- Load all traces from `--trace-dir`
- For each method name in registry (start with `baseline` only; others added in later tasks)
- Rebuild graph; attach secondaries into `eval_meta`
- `run_graph(evaluate_fn=...)`
- On Answer: extract prediction, EM vs gold
- Aggregate → `results/gaia/eval_results.json`

- [ ] Commit

```bash
git commit -m "feat: Phase B eval CLI skeleton and ranking metrics"
```

---

### Task 9: Logprobs confidence evaluator

**Files:**
- Create: `src/gaia_dag/evaluators/logprobs_confidence.py`
- Test: `tests/test_logprobs_eval.py` (mock logprobs)

Behavior: D/S same as Baseline; C from YES/NO logprobs probe:
`"Is the following output factually accurate and consistent with the task, with no hallucination? Answer YES or NO."`

Register method `logprobs` in eval CLI.

- [ ] Commit: `feat: logprobs confidence evaluator (C ablation)`

---

### Task 10: Multi-judge deviation evaluator

**Files:**
- Create: `src/gaia_dag/evaluators/multi_judge.py`
- Test: `tests/test_multi_judge.py` (mock 2–3 providers)

Behavior: C/S like Baseline; D = mean of available judges; critic sees **only** this node's task + output (no parents). Warn if <2 judges available.

- [ ] Commit: `feat: multi-judge deviation evaluator (no upstream context)`

---

### Task 11: DSS diagnostic evaluator

**Files:**
- Create: `src/gaia_dag/evaluators/dss.py`
- Test: `tests/test_dss.py`

Behavior:
- Baseline D/C/S
- Prepend fixed perturbation: `"Re-examine your assumptions and consider an alternative framing before answering."`
- One regenerate via worker LLM (this is **diagnostic**, not replacing primary `output_data`)
- `DSS = 1 - cosine(embed(primary), embed(perturbed))`
- If DSS ≥ 0.3 set `eval_meta["dss_high_risk"]=True`
- Ranking D must match Baseline semantics

- [ ] Commit: `feat: DSS diagnostic evaluator`

---

### Task 12: Context-aware ensemble

**Files:**
- Create: `src/gaia_dag/evaluators/context_ensemble.py`
- Test: `tests/test_context_ensemble.py`

Behavior:
- C = logprobs YES/NO
- D = multi-judge **with** parent task snippets + parent `output_data` in critic prompt; optional upstream DSS warning if parent `DSS` high
- + DSS as in Task 11
- Register as `context_ensemble`

- [ ] Commit: `feat: context-aware ensemble evaluator`

---

### Task 13: Wire all five methods + README

**Files:**
- Modify: `scripts/run_gaia_eval.py` method registry = all five
- Rewrite: `README.md` for this experiment
- Ensure: attachment extraction wired in HF loader (`attachments.py`)

README must document:
- Research question + frozen-worker rule
- Setup: `cp .env.example .env`, keys table
- Commands:

```bash
python scripts/run_gaia_worker.py --demo --max-tasks 5
python scripts/run_gaia_eval.py --trace-dir results/gaia/worker_traces --methods all
python scripts/run_gaia_worker.py --max-tasks 20   # HF pilot
```

- Ceiling caveat, DSS≈Baseline on D, context on vs off contrast
- Routing formula + eval_score weights

- [ ] Commit: `docs: README for GAIA evaluator experiment; wire five methods`

---

### Task 14: End-to-end verification

- [ ] **Step 1: Unit suite**

```bash
pytest -q
```

Expected: all PASS.

- [ ] **Step 2: Demo smoke (needs OPENAI_API_KEY; Anthropic/Gemini optional)**

```bash
cp .env.example .env   # user fills keys
python scripts/run_gaia_worker.py --demo --max-tasks 3
python scripts/run_gaia_eval.py --trace-dir results/gaia/worker_traces --methods all
```

Expected: traces on disk; `eval_results.json` with ranking for five methods (multi-judge may use fewer providers if keys missing).

- [ ] **Step 3: Do not run full L2+L3 until pilot OK** — document only.

- [ ] **Step 4: Final commit if any fixes**

```bash
git commit -m "fix: address smoke-test issues"
```

---

## Self-review checklist (plan author)

1. **Spec coverage:** Models, orchestrator, demo+HF loader, 3-node DAG, Phase A/B, five evaluators, EM, metrics, routing, env — each has a task.
2. **No placeholders:** Tasks include concrete code or explicit API lists.
3. **Type consistency:** `Node`, `Graph`, `NodeStatus`, `evaluate`/`run_worker`, trace schema fields match the design spec.
4. **Frozen-worker:** Orchestrator asserts evaluate does not overwrite `output_data`; traces resume-safe.

---

## Execution handoff

After this plan is saved, choose:

1. **Subagent-Driven (recommended)** — fresh subagent per task + review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Also: copy `.env.example` → `.env` and fill keys before Task 14 live smoke.
