from langgraph.graph import StateGraph, MessagesState, START, END

def node_a(state: MessagesState) -> dict:
  return {"messages": [{"role": "assistant", "content": "Hello from node A"}]}


def node_b(state: MessagesState) -> dict:
    return {"messages": [{"role": "assistant", "content": "Hello from node B"}]}


def node_c(state: MessagesState) -> dict:
    return {"messages": [{"role": "assistant", "content": "Hello from node C"}]}

graph = StateGraph(MessagesState)
graph.add_node("node_a", node_a)
graph.add_node("node_b", node_b)
graph.add_node("node_c", node_c)
graph.add_edge(START, "node_a")
graph.add_edge("node_b", "node_c")
graph.add_edge("node_c", END)
graph.add_edge("node_a", "node_b")



app = graph.compile()

print(app.invoke({"messages": [{"role": "user", "content": "Hello"}]}))