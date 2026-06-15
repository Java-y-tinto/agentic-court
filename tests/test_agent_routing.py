from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.agent import graph as agraph
from src.agent.state import AgentState
from src.tribunal.state import TribunalState


def _ai(*calls):
    return AIMessage(content="", tool_calls=list(calls))


def _call(name, **args):
    return {"name": name, "args": args, "id": name[:2]}


# --- routing -----------------------------------------------------------------

def test_final_answer_routes_to_end():
    state = {"messages": [AIMessage(content="here is the answer")]}
    assert agraph._route_agent(state) == END


def test_delegate_call_routes_to_delegate():
    state = {"messages": [_ai(_call("delegate_to_tribunal", task="x"))]}
    assert agraph._route_agent(state) == "delegate"


def test_normal_tool_call_routes_to_governance():
    state = {"messages": [_ai(_call("run_python", code="print(1)"))]}
    assert agraph._route_agent(state) == "governance"


def test_web_search_call_routes_to_governance():
    state = {"messages": [_ai(_call("web_search", query="news"))]}
    assert agraph._route_agent(state) == "governance"


def test_mixed_calls_with_delegate_route_to_delegate():
    state = {"messages": [_ai(_call("run_python", code="x"), _call("delegate_to_tribunal", task="x"))]}
    assert agraph._route_agent(state) == "delegate"


# --- delegate node ------------------------------------------------------------

def _fake_tribunal(verdict, output, interrupts=False):
    def work(_state):
        if interrupts:
            interrupt({"tool": "run_shell", "args": {"command": "ls"}})
        return {"judge_verdict": verdict, "worker_output": output}

    g = StateGraph(TribunalState)
    g.add_node("work", work)
    g.add_edge(START, "work")
    g.add_edge("work", END)
    return g.compile()  # no checkpointer -> embeddable


def test_delegate_returns_verdict_and_defers_extra_calls(monkeypatch):
    monkeypatch.setattr(agraph, "_tribunal", _fake_tribunal("accept", "the result"))
    state = {"messages": [_ai(_call("delegate_to_tribunal", task="build X"), _call("run_python", code="x"))]}

    out = agraph.delegate(state)
    msgs = out["messages"]

    assert all(isinstance(m, ToolMessage) for m in msgs)
    assert "accept" in msgs[0].content and "the result" in msgs[0].content
    assert "one tool call or delegation at a time" in msgs[1].content


def test_escalate_verdict_includes_critique(monkeypatch):
    def work(_state):
        return {"judge_verdict": "escalate", "worker_output": "best attempt", "inspector_critique": "still wrong"}

    g = StateGraph(TribunalState)
    g.add_node("work", work)
    g.add_edge(START, "work")
    g.add_edge("work", END)
    monkeypatch.setattr(agraph, "_tribunal", g.compile())

    out = agraph.delegate({"messages": [_ai(_call("delegate_to_tribunal", task="hard"))]})
    assert "ESCALATE" in out["messages"][0].content
    assert "still wrong" in out["messages"][0].content


# --- nested interrupt propagation (the Stage 3 risk) --------------------------

def test_governance_interrupt_inside_delegation_surfaces_and_resumes(monkeypatch):
    monkeypatch.setattr(agraph, "_tribunal", _fake_tribunal("accept", "done", interrupts=True))

    def seed(_state):
        return {"messages": [_ai(_call("delegate_to_tribunal", task="needs approval"))]}

    parent = StateGraph(AgentState)
    parent.add_node("seed", seed)
    parent.add_node("delegate", agraph.delegate)
    parent.add_edge(START, "seed")
    parent.add_edge("seed", "delegate")
    parent.add_edge("delegate", END)
    app = parent.compile(checkpointer=MemorySaver())

    cfg = {"configurable": {"thread_id": "t"}}
    first = app.invoke({"messages": []}, config=cfg)
    assert first.get("__interrupt__"), "delegated governance approval did not surface at top level"

    final = app.invoke(Command(resume="yes"), config=cfg)
    tool_msgs = [m for m in final["messages"] if isinstance(m, ToolMessage)]
    assert tool_msgs and "accept" in tool_msgs[-1].content
