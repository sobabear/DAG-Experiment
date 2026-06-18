"""A layered, *signed* DAG -- the "vanilla MAS" pattern from the BPD reference.

This shows how the generic dagcore engine reproduces the core idea behind
ChengcanWu/BPD's ``mas/graph.py``: agents are arranged into sequential rounds
(layers), and the influence one agent has on another is recorded as a *signed*
edge weight in {-1, 0, 1} (disagree / neutral / agree).

Unlike the reference, no LLM is required: each agent here is a plain Python
function, and edge weights are assigned by a simple stub "scorer". The point is
to demonstrate the DAG mechanics -- rounds, signed edges, and topological
execution -- not the BPD detection algorithm.

Run:  python examples/signed_mas_dag.py
"""

from dagcore import DAG, Executor


# A toy "scorer": +1 if two answers agree, -1 if they disagree, 0 otherwise.
def score(answer_a: str, answer_b: str) -> int:
    if answer_a == answer_b:
        return 1
    return -1


def build_mas() -> DAG:
    g = DAG()
    num_agents = 3
    correct = "B"

    # --- Round 0: each agent gives an initial answer ---------------------
    # Agent 1 is a "troublemaker" and answers wrongly.
    initial = {1: "A", 2: "B", 3: "B"}
    for aid in range(1, num_agents + 1):
        ans = initial[aid]
        g.add_node(f"r0:a{aid}", data=ans, agent_id=aid, round=0)

    # --- Round 1: each agent summarizes by majority of round-0 answers ---
    for aid in range(1, num_agents + 1):
        node_id = f"r1:a{aid}"

        def summarize(inputs, _self=aid):
            # Majority vote over predecessor answers.
            tally = {}
            for ans in inputs.values():
                tally[ans] = tally.get(ans, 0) + 1
            return max(tally, key=tally.get)

        g.add_node(node_id, func=summarize, agent_id=aid, round=1)

        # Connect every round-0 answer into this summarizer and sign the edge
        # by whether the sender agreed with the (known) correct answer.
        for sender in range(1, num_agents + 1):
            sender_node = f"r0:a{sender}"
            weight = score(g.get_node(sender_node).data, correct)
            g.add_edge(sender_node, node_id, weight=weight)

    return g


def main() -> None:
    g = build_mas()

    print("Rounds (topological generations):")
    for i, layer in enumerate(g.topological_generations()):
        print(f"  round {i}: {layer}")

    print("\nSigned edges (sender -> receiver : weight):")
    for e in g.edges():
        print(f"  {e.source} -> {e.target} : {e.weight:+d}")

    result = Executor(g).run()
    print("\nFinal answers per agent:")
    for aid in (1, 2, 3):
        print(f"  agent {aid}: {result.outputs[f'r1:a{aid}']}")

    # Aggregate signed influence received by each summarizer.
    print("\nNet signed influence into each summarizer:")
    for aid in (1, 2, 3):
        node = f"r1:a{aid}"
        net = sum(g.get_edge(p, node).weight for p in g.predecessors(node))
        print(f"  {node}: {net:+d}")


if __name__ == "__main__":
    main()
