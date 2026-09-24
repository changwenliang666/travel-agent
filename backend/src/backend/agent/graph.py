from langgraph.graph import END, StateGraph

from backend.agent.nodes import answer_node, build_node, clarify_node, extract_node, route_after_extract


def make_graph(deps):
    def extract(state):
        return extract_node(state, deps)

    def clarify(state):
        return clarify_node(state, deps)

    def build(state):
        return build_node(state, deps)

    def answer(state):
        return answer_node(state, deps)

    graph = StateGraph(dict)
    graph.add_node("extract", extract)
    graph.add_node("clarify", clarify)
    graph.add_node("build", build)
    graph.add_node("answer", answer)
    graph.set_entry_point("extract")
    graph.add_conditional_edges("extract", route_after_extract, {"clarify": "clarify", "build": "build", "answer": "answer"})
    graph.add_edge("clarify", END)
    graph.add_edge("build", END)
    graph.add_edge("answer", END)
    return graph.compile()
