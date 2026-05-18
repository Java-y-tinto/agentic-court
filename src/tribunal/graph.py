from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agents import escalate, inspector, judge, worker
from .governance import governance
from .state import TribunalState


def _after_worker(state: TribunalState) -> str:
    wm = state.get("worker_messages", [])
    if wm and getattr(wm[-1], "tool_calls", None):
        return "governance"
    return "inspector"


def _route_verdict(state: TribunalState) -> str:
    if state.get("iterations", 0) >= state.get("max_iterations", 3):
        return "escalate"
    verdict = state.get("judge_verdict", "").strip()
    return verdict if verdict in ("accept", "retry", "escalate") else "escalate"


def build():
    graph = StateGraph(TribunalState)

    graph.add_node("worker", worker)
    graph.add_node("governance", governance)
    graph.add_node("inspector", inspector)
    graph.add_node("judge", judge)
    graph.add_node("escalate", escalate)

    graph.add_edge(START, "worker")
    graph.add_conditional_edges("worker", _after_worker, {"governance": "governance", "inspector": "inspector"})
    graph.add_edge("governance", "worker")
    graph.add_edge("inspector", "judge")
    graph.add_conditional_edges("judge", _route_verdict, {"accept": END, "retry": "worker", "escalate": "escalate"})
    graph.add_edge("escalate", END)

    return graph.compile(checkpointer=MemorySaver())


app = build()
