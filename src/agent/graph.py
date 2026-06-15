import os

from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.modules.logger import logger
from src.tools.policy import make_governance, sandbox_policy_tools, web_search_policy_tool
from src.tribunal.graph import build as build_tribunal

from .agent import agent
from .state import AgentState
from .tools import DELEGATE_TOOL_NAME

# The agent exposes the sandboxed tools plus host-side web search; the tribunal
# (built below) exposes only the sandboxed tools.
_governance = make_governance(sandbox_policy_tools() + [web_search_policy_tool()])

_MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "3"))

# The tribunal as an embeddable subgraph: no checkpointer of its own, so it
# inherits this graph's checkpointer and its governance interrupts surface and
# resume at the top level. It runs in the same active sandbox session as the
# agent (get_active() is shared), so delegated work sees the same /workspace.
_tribunal = build_tribunal(checkpointer=None)


def _tribunal_init(task: str) -> dict:
    return {
        "task": task,
        "messages": [],
        "worker_output": "",
        "inspector_critique": "",
        "judge_verdict": "",
        "iterations": 0,
        "max_iterations": _MAX_ITERATIONS,
        "cycle_start": 0,
    }


def _summarize(final: dict) -> str:
    verdict = final.get("judge_verdict", "")
    output = final.get("worker_output", "No output.")
    if verdict == "escalate":
        critique = final.get("inspector_critique", "")
        return (
            "Tribunal verdict: ESCALATE (could not reach an accepted solution).\n"
            f"Best output:\n{output}\n\nInspector's unresolved critique:\n{critique}"
        )
    return f"Tribunal verdict: {verdict or 'unknown'}.\n\nOutput:\n{output}"


def _route_agent(state: AgentState) -> str:
    last = state["messages"][-1]
    calls = getattr(last, "tool_calls", None)
    if not calls:
        return END
    if any(c["name"] == DELEGATE_TOOL_NAME for c in calls):
        return "delegate"
    return "governance"


def delegate(state: AgentState) -> dict:
    # Handle exactly one delegation per entry. Running a single tribunal subgraph
    # per node entry keeps side effects bounded: when its governance interrupts,
    # this node re-runs on resume and the subgraph resumes from its checkpoint
    # rather than restarting. Any other calls in the same message are deferred so
    # every tool_call_id still gets a reply (the message protocol requires it).
    last = state["messages"][-1]
    results: list[ToolMessage] = []
    handled = False
    for call in last.tool_calls:
        if call["name"] == DELEGATE_TOOL_NAME and not handled:
            task = call["args"]["task"]
            logger.info("Delegate — running tribunal for: %s", task)
            final = _tribunal.invoke(_tribunal_init(task))
            content = _summarize(final)
            handled = True
        else:
            content = "Not executed: issue one tool call or delegation at a time."
        results.append(ToolMessage(content=content, tool_call_id=call["id"], name=call["name"]))
    return {"messages": results}


def build(checkpointer=None):
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent)
    graph.add_node("governance", _governance)
    graph.add_node("delegate", delegate)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        _route_agent,
        {"governance": "governance", "delegate": "delegate", END: END},
    )
    graph.add_edge("governance", "agent")
    graph.add_edge("delegate", "agent")

    return graph.compile(checkpointer=checkpointer or MemorySaver())


app = build()
