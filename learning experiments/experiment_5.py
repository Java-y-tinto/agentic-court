from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain.tools import tool
from langchain.messages import ToolMessage
from langchain_ollama import ChatOllama

class State(TypedDict):
    messages: Annotated[list, add_messages]

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression. The expression must be a valid python one."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"

@tool
def run_python(code: str) -> str:
    """Run python code. CAREFUL WITH WHAT YOU RUN. You are forbidden from running any desctructive code (e.g., deleting files, etc.)"""
    try:
        exec(code)
        return "Code executed successfully."
    except Exception as e:
        return f"Error: {e}"

@tool
def reverse_string(string: str) -> str:
    """Reverse a string."""
    return string[::-1]


tools = [calculator, run_python, reverse_string]

llm = ChatOllama(model="qwen2.5", base_url="http://localhost:11434")
llm_with_tools = llm.bind_tools(tools)

tools_by_name = {tool.name: tool for tool in tools}

def call_model(state: State) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

def handle_tools(state: State) -> dict:
    last_message = state["messages"][-1]
    results = []

    for tool_call in last_message.tool_calls:
        print(f"\n [TOOL CALLED] {tool_call["name"]} with args: {tool_call['args']}")
        result = tools_by_name[tool_call["name"]].invoke(tool_call["args"])
        print(f"[TOOL RESULT] {result}")
        results.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"], name=tool_call["name"]))
    
    return {"messages": results}

def should_use_tools(state: State) -> str:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "handle_tools"
    else:
        return END

graph = StateGraph(State)
graph.add_node("call_model", call_model)
graph.add_node("handle_tools", handle_tools)

graph.add_edge(START, "call_model")
graph.add_conditional_edges("call_model", should_use_tools)
graph.add_edge("handle_tools", "call_model")

app = graph.compile()

state = {"messages": []}

while True:
    user_input = input("You: ").strip()
    if user_input.lower() == "exit":
        break

    state = app.invoke(
        {
            "messages": state["messages"] + [{"role": "user", "content": user_input}]
        }
    )
    print(f"QwenAI: {state['messages'][-1].content}")
    print("\n")

    