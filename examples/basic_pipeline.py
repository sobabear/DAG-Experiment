"""A minimal data-flow pipeline built on the dagcore engine.

Run:  python examples/basic_pipeline.py
"""

from dagcore import DAG, Executor


def main() -> None:
    g = DAG()

    # Source node: a constant value (no func -> emits its data).
    g.add_node("load", data=10)

    # Transform nodes read predecessor outputs from the `inputs` mapping.
    g.add_node("double", func=lambda inputs: inputs["load"] * 2)
    g.add_node("inc", func=lambda inputs: inputs["load"] + 1)
    g.add_node("combine", func=lambda inputs: inputs["double"] + inputs["inc"])

    g.add_edge("load", "double")
    g.add_edge("load", "inc")
    g.add_edge("double", "combine")
    g.add_edge("inc", "combine")

    result = Executor(g).run()

    print("Topological order:", result.order)
    print("Layers          :", result.generations)
    print("Outputs         :", result.outputs)
    print("Final           :", result.outputs["combine"])  # 10*2 + (10+1) = 31


if __name__ == "__main__":
    main()
