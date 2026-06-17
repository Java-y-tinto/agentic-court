from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]
    counter: int


def node_a(state: State) -> dict:
  return {"messages": [{"role": "assistant", "content": "Hello from node A"}]}


def node_b(state: State) -> dict:
    return {"messages": [{"role": "assistant", "content": "Hello from node B"}], "counter": state["counter"] + 1}


def node_c(state: State) -> dict:
    return {"messages": [{"role": "assistant", "content": "Hello from node C"}]}


def conditional_edge(state: State) -> str:
    if state["counter"] < 3:
        return "node_b"
    else:
        return "node_c"

graph = StateGraph(State)
graph.add_node("node_a", node_a)
graph.add_node("node_b", node_b)
graph.add_node("node_c", node_c)
graph.add_edge(START, "node_a")
graph.add_edge("node_a","node_b")
graph.add_conditional_edges("node_b", conditional_edge)
graph.add_edge("node_c", END)


app = graph.compile()

print(app.invoke({"messages": [{"role": "user", "content": "Hello"}], "counter": 0}))
