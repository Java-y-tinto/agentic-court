from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_ollama import ChatOllama

class State(TypedDict):
    messages: Annotated[list, add_messages]

llm = ChatOllama(model="qwen2.5", base_url="http://localhost:11434")

def call_model(state: State) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


graph = StateGraph(State)
graph.add_node("call_model", call_model)
graph.add_edge(START, "call_model")
graph.add_edge("call_model", END)

app = graph.compile()

result = app.invoke({"messages": [{"role": "user", "content": "Hi, can you explain the difference between a process and a thread in one paragraph?"}]})

for message in result["messages"]:
    print(f"{message.type}: {message.content}")
    print("---")