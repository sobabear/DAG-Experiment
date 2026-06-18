# DAG-Experiment — Core / Vanilla DAG 시스템

의존성이 없는 작고 **범용적인 방향성 비순환 그래프(DAG) 엔진**(Python)입니다.

이 프로젝트는 상위 시스템이 그 위에 구축할 수 있는 재사용 가능한 *코어*("vanilla" DAG 계층)입니다.
예를 들어 [ChengcanWu/BPD](https://github.com/ChengcanWu/BPD) 레퍼런스 프로젝트의
멀티 에이전트 **signed-DAG** 같은 시스템이 이를 기반으로 만들어질 수 있습니다.
그래프 자료구조, 사이클 안전(cycle-safe) 엣지 삽입, 위상 정렬/계층화, 순회,
그리고 위상 순서 실행 스케줄러를 제공하며, LLM·멀티 에이전트·탐지 로직은
**전혀 포함하지 않습니다**.

> BPD와의 관계: BPD의 `mas/graph.py`는 에이전트 간 통신을
> *signed, layered DAG*(노드 = 라운드별 에이전트, 엣지 = `{-1, 0, 1}`의 부호 있는 영향력)로
> 모델링한 뒤, 그 위에 탐지/복구 알고리즘(BPD)을 얹습니다.
> 이 프로젝트는 그 **코어 DAG**를 추출·일반화하여, 동일한 메커니즘
> — 라운드, 부호 있는 엣지, 위상 순서 실행 — 을 독립적으로 재사용할 수 있게 합니다.
> BPD 탐지 알고리즘 자체는 의도적으로 *포함하지 않았습니다*.

---

## 기능

- **노드(Nodes)** — 해시 가능한 id, 임의의 `data` 페이로드, 선택적 실행 함수
  `func`, 그리고 자유 형식의 메타데이터를 가집니다.
- **방향성 엣지(Directed edges)** — 선택적으로 **가중치/부호(weighted / signed)** 를
  가질 수 있습니다(예: BPD처럼 `{-1, 0, 1}`, 또는 임의의 숫자 가중치).
- **설계상 사이클 안전(Cycle-safe by construction)** — 사이클(또는 자기 루프)을
  만드는 엣지를 추가하면 `CycleError`가 발생하고 그래프는 변경되지 않습니다.
- **조회(Queries)** — `successors`, `predecessors`, `roots`, `leaves`, `ancestors`,
  `descendants`, `in_degree`, `out_degree`.
- **정렬(Ordering)** — `topological_sort()`(Kahn 알고리즘, 결정적 tie-break)과
  `topological_generations()`(계층화된 "라운드").
- **순회(Traversal)** — `bfs()`, `dfs()`.
- **실행 스케줄러(Execution scheduler)** — `Executor`는 각 노드의 `func`를
  의존 순서대로 실행하고, 선행 노드의 출력을 후속 노드로 전달합니다. 공유 컨텍스트,
  계층별 콜백, 엣지 가중치 주입을 선택적으로 지원합니다.

서드파티 런타임 의존성이 없습니다. 순수 표준 라이브러리만 사용합니다.

---

## 프로젝트 구조

```
DAG-Experiment/
├── src/dagcore/
│   ├── __init__.py        # 공개 API
│   ├── graph.py           # Node, Edge, DAG (코어 자료구조 + 조회)
│   ├── executor.py        # Executor, ExecutionResult (위상 순서 스케줄러)
│   └── errors.py          # GraphError, CycleError, NodeNotFoundError
├── examples/
│   ├── basic_pipeline.py  # 최소 데이터 흐름 파이프라인
│   └── signed_mas_dag.py  # 계층화된 signed-DAG (BPD "vanilla MAS" 패턴)
├── tests/                 # pytest 스위트 (graph, topology, executor)
├── pyproject.toml
└── README.md
```

---

## 설치

**Python 3.9+** 가 필요합니다.

```bash
# 가상 환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 패키지 설치 (개발/테스트 의존성 포함)
pip install -e ".[dev]"
```

---

## 빠른 시작

```python
from dagcore import DAG, Executor

g = DAG()

# func가 없는 소스 노드는 자신의 `data`를 출력으로 내보냅니다.
g.add_node("load", data=10)

# 변환 노드는 선행 노드의 출력을 `inputs` 매핑으로부터 읽습니다.
g.add_node("double", func=lambda inputs: inputs["load"] * 2)
g.add_node("inc",    func=lambda inputs: inputs["load"] + 1)
g.add_node("combine", func=lambda inputs: inputs["double"] + inputs["inc"])

g.add_edge("load", "double")
g.add_edge("load", "inc")
g.add_edge("double", "combine")
g.add_edge("inc", "combine")

result = Executor(g).run()
print(result.order)        # ['load', 'double', 'inc', 'combine']
print(result.generations)  # [['load'], ['double', 'inc'], ['combine']]
print(result.outputs)      # {'load': 10, 'double': 20, 'inc': 11, 'combine': 31}
```

### 부호 있는 엣지 & 계층화된 "라운드" (BPD 스타일)

```python
from dagcore import DAG

g = DAG()
g.add_node("r0:a1", data="A")   # 라운드 0, 에이전트 1 (정답 "B"와 불일치)
g.add_node("r0:a2", data="B")
g.add_node("r1:a1")             # 라운드 1 요약자(summarizer)

g.add_edge("r0:a1", "r1:a1", weight=-1)  # 부호 있는 영향력: 불일치
g.add_edge("r0:a2", "r1:a1", weight=+1)  # 부호 있는 영향력: 일치

print(g.topological_generations())  # [['r0:a1', 'r0:a2'], ['r1:a1']]
net = sum(g.get_edge(p, "r1:a1").weight for p in g.predecessors("r1:a1"))
print(net)  # 0  (순(net) 부호 영향력)
```

---

## API 개요

### `DAG`

| 메서드 | 설명 |
| --- | --- |
| `add_node(id, data=None, func=None, exist_ok=False, **meta)` | 노드를 추가하고 반환합니다. |
| `add_nodes_from(ids)` | 여러 노드를 추가합니다(이미 존재하면 무시). |
| `get_node(id)` / `has_node(id)` / `remove_node(id)` | 노드 접근 / 제거(연결된 엣지도 제거). |
| `add_edge(src, tgt, weight=None, create_missing=False, **meta)` | 엣지 추가/갱신; 사이클을 만들면 `CycleError` 발생. |
| `get_edge(src, tgt)` / `has_edge(src, tgt)` / `remove_edge(src, tgt)` | 엣지 접근 / 제거. |
| `successors(id)` / `predecessors(id)` | 직접 이웃 노드. |
| `in_degree(id)` / `out_degree(id)` | 진입/진출 차수. |
| `roots()` / `leaves()` | 소스 / 싱크 노드. |
| `ancestors(id)` / `descendants(id)` | 도달 가능성(집합). |
| `topological_sort()` | 선형 위상 순서(결정적). |
| `topological_generations()` | 계층화된 그룹("라운드"). |
| `is_acyclic()` | 무결성 확인(공개 API를 통해서는 항상 true). |
| `bfs(start)` / `dfs(start)` | 진출 엣지를 따라 순회. |
| `edges()` / `node_ids()` / `nodes()` / `edge_count()` | 일괄 접근자. |

### `Executor`

`Executor(graph, inject_weights=False).run(context=None, on_layer=None) -> ExecutionResult`

노드 함수를 위상 순서대로 실행합니다. 노드 함수는 매개변수 이름에 따라
유연하게 호출됩니다:

- `func(inputs)` — `inputs`는 `{predecessor_id: output}`
- `func(inputs, context)` — 실행 단위의 `context` 딕셔너리도 함께 전달
- `func(inputs, weights)` — `inject_weights=True`일 때, `weights`는 `{predecessor_id: edge_weight}`
- `func`가 **없는** 노드는 자신의 `data` 속성을 내보냅니다

`ExecutionResult`는 `.outputs`, `.order`, `.generations`를 가집니다.

### 예외(Errors)

`GraphError` (기본) · `CycleError` · `NodeNotFoundError`

---

## 예제 실행

```bash
python examples/basic_pipeline.py
python examples/signed_mas_dag.py
```

---

## 테스트

```bash
pytest
```

스위트(33개 테스트)는 노드/엣지 관리, 사이클 거부, 부호 있는 엣지,
조회, 위상 정렬 및 계층화, 순회, 그리고 실행 스케줄러를 다룹니다.

---

## 라이선스

MIT
