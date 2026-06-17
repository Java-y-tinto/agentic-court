# Human-in-the-loop experiment

from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from langgraph.types import interrupt, Command
from langchain.tools import tool
from langchain.messages import ToolMessage

class State(TypedDict):
    messages: Annotated[list, add_messages]
    pending_tool_call: dict | None # This will store the tool call that is waiting for human input

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression using python. Expression must be a valid python expression."""
    return str(eval(expression))

@tool
def run_python(code: str) -> str:
    """Execute python code and return the output. Code must be valid"""
    import io
    import contextlib
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

tools_by_name = {tool.name: tool for tool in tools}

llm = ChatOllama(model="qwen2.5", base_url = "http://localhost:11434")
llm_with_tools = llm.bind_tools(tools)

def llm_node(state: State) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

def approval_node(state: State) -> str:
    last_message = state['messages'][-1]

    if not last_message.tool_calls:
        return {}
    
    tool_call = last_message.tool_calls[0]

    # Pause the graph here and wait for human approval, surfacing a value to the user

    decision = interrupt({
        "tool": tool_call['name'],
        "args": tool_call['args'],
        "question": f"Do you approve the execution of {tool_call['name']} with args {tool_call['args']}?"
    })

    if decision.lower() != "yes":
        return {
            "messages": [ToolMessage(
                content="Tool call rejected by user",
                tool_call_id = tool_call['id']
            )]
        }
    result = tools_by_name[tool_call['name']].invoke(tool_call['args'])
    return {
        "messages": [ToolMessage(
            content=str(result),
            tool_call_id = tool_call['id']
        )]
    }

def approval_edge(state: State) -> str:
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        return "approval_node"
    else:
        return END


graph = StateGraph(State)
graph.add_node("llm_node",llm_node)
graph.add_node("approval_node",approval_node)
graph.add_edge(START,"llm_node")
graph.add_conditional_edges("llm_node", approval_edge)
graph.add_edge("approval_node", "llm_node")

checkpointer = MemorySaver()

app = graph.compile(checkpointer=checkpointer)

# Al tener checkpointer, no tenemos que pasar manualmente todo el historial de mensajes
config = {"configurable": {"thread_id": "1"}}

while True:
    user_input = input("You: ").strip()
    if user_input.lower() == "exit":
        break
    result = app.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config
    )

    last_message = result["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Read the interrupt value from the checkpointer
        state_snapshot = app.get_state(config)
        for task in state_snapshot.tasks:
            if task.interrupts:
                for interrupt_val in task.interrupts:
                    print("\n--- Approval required ---")
                    print(f"Tool:     {interrupt_val.value['tool']}")
                    print(f"Args:     {interrupt_val.value['args']}")
                    print(f"Question: {interrupt_val.value['question']}")

        approval = input("\nApprove? (yes/no): ").strip()
        final = app.invoke(Command(resume=approval), config=config)
    print(f"\nQwenAI: {final['messages'][-1].content}\n")
else:
    print(f"QwenAI: {last_message.content}\n")