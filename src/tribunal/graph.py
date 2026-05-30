import re

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.classes import PolicyEngine, Rule, Tool, Verdict
from src.modules.governance import Governance

from .agents import escalate, inspector, judge, worker
from .state import TribunalState
from .tools import calculator, run_python, run_shell


def _matches(pattern: str):
    return lambda args: bool(re.search(pattern, str(args), re.IGNORECASE))


_tools = [
    Tool(
        name="run_python",
        fn=run_python.func,
        default=Verdict.REQUIRE_APPROVAL,
    ),
    Tool(
        name="run_shell",
        fn=run_shell.func,
        default=Verdict.REQUIRE_APPROVAL,
        rules=[
            Rule(_matches(r"\brm\b.{0,30}-[a-zA-Z]*r[a-zA-Z]*f"), "recursive force delete", Verdict.AUTO_DENY),
            Rule(_matches(r"\brmdir\b.*--ignore-fail"), "forced directory removal", Verdict.AUTO_DENY),
            Rule(_matches(r"\bsudo\b|\bsu\s+-"), "privilege escalation", Verdict.AUTO_DENY),
            Rule(_matches(r"\bdd\b.*of=/dev/[sh]d"), "direct disk write", Verdict.AUTO_DENY),
            Rule(_matches(r"\bmkfs\b|\bmformat\b"), "filesystem formatting", Verdict.AUTO_DENY),
            Rule(_matches(r">\s*/dev/[sh]d[a-z]"), "redirect to raw disk device", Verdict.AUTO_DENY),
            Rule(_matches(r"\bchmod\b.{0,20}[0-7]*[67][0-7][0-7]\s+/"), "broad permission change on system path", Verdict.AUTO_DENY),
            Rule(_matches(r"\bchown\b.*root.*/"), "ownership change to root on system path", Verdict.AUTO_DENY),
            Rule(_matches(r":\(\)\s*\{.*\|.*:.*&.*\}"), "fork bomb", Verdict.AUTO_DENY),
            Rule(_matches(r"\bcurl\b.*\|\s*(ba)?sh"), "piping URL to shell", Verdict.AUTO_DENY),
            Rule(_matches(r"\bwget\b.*-O\s*-\s*\|"), "piping URL to shell", Verdict.AUTO_DENY),
            Rule(_matches(r"/etc/(passwd|shadow|sudoers|crontab)"), "access to sensitive system files", Verdict.AUTO_DENY),
            Rule(_matches(r"\bnc\b.*-e|\bnetcat\b.*-e"), "netcat reverse shell", Verdict.AUTO_DENY),
            Rule(_matches(r"\bbash\b.*-i.*>&"), "interactive reverse shell redirect", Verdict.AUTO_DENY),
            Rule(_matches(r"/boot/|\bgrub\b"), "boot or kernel file access", Verdict.AUTO_DENY),
        ],
    ),
    Tool(
        name="calculator",
        fn=calculator.func,
        default=Verdict.AUTO_ALLOW,
    ),
]

_policy = PolicyEngine(_tools)
_governance = Governance(_policy)


def _after_worker(state: TribunalState) -> str:
    messages = state.get("messages", [])
    if messages and getattr(messages[-1], "tool_calls", None):
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

    return graph.compile(checkpointer=MemorySaver())


app = build()
