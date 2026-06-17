from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.tools.policy import default_governance

from .agents import escalate, inspector, judge, worker
from .state import TribunalState

# Shared with the agent: sandboxed run_python/run_shell plus host-side web search,
# so the worker can research and the inspector can adversarially check its findings.
_governance = default_governance()


def _after_worker(state: TribunalState) -> str:
    messages = state.get("messages", [])
    if messages and getattr(messages[-1], "tool_calls", None):
        return "governance"
    return "inspector"


def _route_verdict(state: TribunalState) -> str:
    # An accepted solution is accepted even on the final iteration; the budget
    # ceiling only converts further retries into escalation.
    verdict = state.get("judge_verdict", "")
    if verdict == "accept":
        return "accept"
    if verdict == "retry" and state.get("iterations", 0) < state.get("max_iterations", 3):
        return "retry"
    return "escalate"


def build(checkpointer=MemorySaver()):
    # checkpointer=None compiles the tribunal as an embeddable subgraph: it then
    # inherits the parent graph's checkpointer, which is what lets a governance
    # interrupt raised inside a delegated run surface and resume at the top level.
    graph = StateGraph(TribunalState)

    graph.add_node("worker", worker)
    graph.add_node("governance", _governance)
    graph.add_node("inspector", inspector)
    graph.add_node("judge", judge)
    graph.add_node("escalate", escalate)

    graph.add_edge(START, "worker")
    graph.add_conditional_edges("worker", _after_worker, {"governance": "governance", "inspector": "inspector"})
    graph.add_edge("governance", "worker")
    graph.add_edge("inspector", "judge")
    graph.add_conditional_edges("judge", _route_verdict, {"accept": END, "retry": "worker", "escalate": "escalate"})
    graph.add_edge("escalate", END)

    return graph.compile(checkpointer=checkpointer)
