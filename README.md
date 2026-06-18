# DAG-Experiment — BPD DAG Core Only

This project implements only the core DAG data structure used by
[ChengcanWu/BPD](https://github.com/ChengcanWu/BPD), based on the idea in
`mas/graph.py`.

It is intentionally small. It does **not** implement BPD itself.

## Scope

Included:

- Layered DAG layout from `agents_per_round`
- Mapping `(round_idx, agent_id)` to a zero-based node index
- Signed adjacency matrix storage
- Edge update by sender/receiver round and agent id
- Outgoing edge queries
- Incoming edge queries
- Validation that real DAG edges move from an earlier round to a later round

Not included:

- Agents
- LLM calls
- Prompt handling
- Answer scoring
- Multi-agent round orchestration
- Topological executor/scheduler
- BPD detection, repair, or recovery algorithms
- General-purpose graph algorithms beyond this DAG core

## Core model

`EdgeGraph` stores edges in a matrix:

```text
connections[receiver_idx][sender_idx] = signed_score
```

A score of `0` means no edge. Non-zero scores are signed edge values such as
`-1` or `1`.

Nodes are arranged by round:

```python
agents_per_round = [3, 2]
```

This means:

- round `0` has agents `1..3`
- round `1` has agents `1..2`
- total nodes: `5`

Agent ids are one-based, matching the BPD reference style.

## Installation

Python 3.9+ is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```python
from dagcore import EdgeGraph

edges = EdgeGraph([3, 1])

# round 0 agent 1 -> round 1 agent 1 with signed score -1
edges.update_edge(0, 1, 1, 1, -1)

# round 0 agent 2 -> round 1 agent 1 with signed score +1
edges.update_edge(0, 2, 1, 1, 1)

sender_idx = edges.node_index(0, 1)
receiver_idx = edges.node_index(1, 1)

print(edges.outgoing_edges(sender_idx))   # [(3, -1)]
print(edges.incoming_edges(receiver_idx)) # [(0, -1), (1, 1)]
```

## API

### `EdgeGraph(agents_per_round)`

Creates a layered signed DAG matrix.

- `agents_per_round`: list of positive integers
- `total_nodes`: total node count
- `connections`: matrix where rows are receivers and columns are senders

### `node_index(round_idx, agent_id) -> int`

Returns the zero-based node index for a round and one-based agent id.

Raises `NodeNotFoundError` if the round or agent id is out of range.

### `update_edge(sender_round, sender_id, receiver_round, receiver_id, score) -> None`

Adds, updates, or removes an edge score.

- `sender_round < 0` is ignored, matching BPD's initial no-sender behavior.
- `sender_round` must be less than `receiver_round` for real edges.
- `score == 0` represents no edge.

Raises `InvalidEdgeError` if the edge does not point from an earlier round to a
later round.

### `outgoing_edges(sender_idx) -> list[tuple[int, int]]`

Returns `(receiver_idx, score)` pairs for all non-zero outgoing edges.

### `incoming_edges(receiver_idx) -> list[tuple[int, int]]`

Returns `(sender_idx, score)` pairs for all non-zero incoming edges.

## Project structure

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

## Run tests

```bash
pytest
```

## License

MIT
peline.py
└── signed_mas_dag.py
```

## Run tests

```bash
pytest
```

## License

MIT
