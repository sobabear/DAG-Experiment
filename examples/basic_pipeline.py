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
