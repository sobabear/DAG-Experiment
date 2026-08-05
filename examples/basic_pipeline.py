"""Minimal EdgeGraph example.

Run: python examples/basic_pipeline.py
"""

from dagcore import EdgeGraph


def main() -> None:
    graph = EdgeGraph([2, 1])

    graph.update_edge(0, 1, 1, 1, 1)
    graph.update_edge(0, 2, 1, 1, -1)

    sender_idx = graph.node_index(0, 1)
    receiver_idx = graph.node_index(1, 1)

    print("connections:", graph.connections)
    print("outgoing from round 0 agent 1:", graph.outgoing_edges(sender_idx))
    print("incoming to round 1 agent 1:", graph.incoming_edges(receiver_idx))


if __name__ == "__main__":
    main()

# ai tool 마다, 다르니 돌린 결과에 대한 평가각 아닌, 생성결과에 따른 결과 평가를 하는 것?
# 논문 가능성, 연구 디벨롭 가능성