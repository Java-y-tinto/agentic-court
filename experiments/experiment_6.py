from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.tools import tool
from langchain.messages import ToolMessage
from langchain_ollama import ChatOllama

class State(TypedDict):
    messages: Annotated[list, add_messages]

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression using python. Expression must be a valid python expression."""
    return str(eval(expression))


@tool
def run_python(code: str) -> str:
    """Execute python code and return the output. Code must be valid"""
    import io, contextlib
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            exec(code)
            return buffer.getvalue() or "No output"
    except Exception as e:
        return f"Error: {e}"


@tool
def reverse_string(text: str) -> str:
    """Reverse a string."""
    return text[::-1]


tools = [calculator, run_python, reverse_string]

llm = ChatOllama(model="qwen2.5", base_url = "http://localhost:11434")
llm_with_tools = llm.bind_tools(tools)

def llm_node(state: State) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

tool_node = ToolNode(tools) # This is the handle_tools and the should_use_tools function but handled automatically by langgraph and as a node

graph = StateGraph(State)
graph.add_node("llm_node", llm_node)
graph.add_node("tools", tool_node)
graph.add_edge(START, "llm_node")
graph.add_conditional_edges("llm_node", tools_condition, ["tools", END])
graph.add_edge("tools", "llm_node")

app = graph.compile()

state = {"messages": []}

while True:
    user_input = input("You: ").strip()
    if user_input.lower() == "exit":
        break

    state = app.invoke(
        {"messages": state["messages"] + [{"role": "user", "content": user_input}]}
    )
    print(f"QwenAI: {state['messages'][-1].content}\n")

