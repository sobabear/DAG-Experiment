"""BPD-style signed DAG storage only.

This example does not run agents, scoring, detection, repair, or execution. It
only shows the signed adjacency matrix used by the DAG core.

Run: python examples/signed_mas_dag.py
"""

from dagcore import EdgeGraph


def main() -> None:
    edges = EdgeGraph([3, 1])

    # Store signed influence from round-0 agents into one round-1 receiver.
    edges.update_edge(0, 1, 1, 1, -1)
    edges.update_edge(0, 2, 1, 1, 1)
    edges.update_edge(0, 3, 1, 1, 1)

    receiver = edges.node_index(1, 1)
    print("incoming signed edges:", edges.incoming_edges(receiver))


if __name__ == "__main__":
    main()
