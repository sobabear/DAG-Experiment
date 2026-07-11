# DAG-Experiment — BPD DAG 코어만

이 프로젝트는 [ChengcanWu/BPD](https://github.com/ChengcanWu/BPD)에서 사용하는
핵심 DAG 자료구조만 구현합니다. `mas/graph.py`의 아이디어를 기반으로 합니다.

의도적으로 작게 유지하며, BPD 자체는 **구현하지 않습니다**.

## 범위

포함:

- `agents_per_round` 기반 계층형 DAG 레이아웃
- `(round_idx, agent_id)`를 0부터 시작하는 노드 인덱스로 매핑
- 부호 있는 인접 행렬 저장
- sender/receiver의 round와 agent id로 엣지 갱신
- 나가는 엣지 조회
- 들어오는 엣지 조회
- 실제 DAG 엣지가 이전 round에서 이후 round로만 향하는지 검증

미포함:

- Agent
- LLM 호출
- 프롬프트 처리
- 답변 채점
- 멀티 에이전트 round 오케스트레이션
- 위상 정렬 실행기/스케줄러
- BPD 탐지, 복구, 복원 알고리즘
- 이 DAG 코어를 넘는 범용 그래프 알고리즘

## 핵심 모델

`EdgeGraph`는 엣지를 행렬로 저장합니다:

```text
connections[receiver_idx][sender_idx] = signed_score
```

점수가 `0`이면 엣지가 없음을 의미합니다. 0이 아닌 점수는 `-1` 또는 `1`과 같은
부호 있는 엣지 값입니다.

노드는 round 단위로 배치됩니다:

```python
agents_per_round = [3, 2]
```

의미:

- round `0`에는 agent `1..3`
- round `1`에는 agent `1..2`
- 전체 노드 수: `5`

Agent id는 BPD 참조 구현과 같이 1부터 시작합니다.

## 설치

Python 3.9+ 가 필요합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 사용법

```python
from dagcore import EdgeGraph

edges = EdgeGraph([3, 1])

# round 0 agent 1 -> round 1 agent 1, 부호 점수 -1
edges.update_edge(0, 1, 1, 1, -1)

# round 0 agent 2 -> round 1 agent 1, 부호 점수 +1
edges.update_edge(0, 2, 1, 1, 1)

sender_idx = edges.node_index(0, 1)
receiver_idx = edges.node_index(1, 1)

print(edges.outgoing_edges(sender_idx))   # [(3, -1)]
print(edges.incoming_edges(receiver_idx)) # [(0, -1), (1, 1)]
```

## API

### `EdgeGraph(agents_per_round)`

계층형 부호 있는 DAG 행렬을 생성합니다.

- `agents_per_round`: 양의 정수 리스트
- `total_nodes`: 전체 노드 수
- `connections`: 행이 receiver, 열이 sender인 행렬

### `node_index(round_idx, agent_id) -> int`

round와 1부터 시작하는 agent id에 대응하는 0부터 시작하는 노드 인덱스를 반환합니다.

round 또는 agent id가 범위를 벗어나면 `NodeNotFoundError`를 발생시킵니다.

### `update_edge(sender_round, sender_id, receiver_round, receiver_id, score) -> None`

엣지 점수를 추가, 갱신, 또는 제거합니다.

- `sender_round < 0`은 무시됩니다. BPD의 초기 no-sender 동작과 동일합니다.
- 실제 엣지에서는 `sender_round`가 `receiver_round`보다 작아야 합니다.
- `score == 0`은 엣지 없음을 의미합니다.

엣지가 이전 round에서 이후 round로 향하지 않으면 `InvalidEdgeError`를
발생시킵니다.

### `outgoing_edges(sender_idx) -> list[tuple[int, int]]`

0이 아닌 나가는 엣지에 대해 `(receiver_idx, score)` 쌍을 반환합니다.

### `incoming_edges(receiver_idx) -> list[tuple[int, int]]`

0이 아닌 들어오는 엣지에 대해 `(sender_idx, score)` 쌍을 반환합니다.

## 프로젝트 구조

```text
src/dagcore/
├── __init__.py
├── graph.py      # EdgeGraph
└── errors.py     # GraphError, NodeNotFoundError, InvalidEdgeError

tests/
└── test_graph.py

examples/
├── basic_pipeline.py
└── signed_mas_dag.py
```

## 테스트 실행

```bash
pytest
```

## 라이선스

MIT
