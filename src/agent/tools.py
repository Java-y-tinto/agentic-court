from langchain_core.tools import tool

from src.tools.sandbox_tools import run_python, run_shell
from src.tools.web_search import web_search

# Threshold below which the model should just answer / use a sandbox tool, and
# above which it should delegate — kept in the prompt, not enforced here.

DELEGATE_TOOL_NAME = "delegate_to_tribunal"


@tool
def delegate_to_tribunal(task: str) -> str:
    """Hand a single, self-contained task to the adversarial tribunal (a
    worker/inspector/judge loop) when it is too complex, error-prone, or
    correctness-critical to do reliably in one shot. Describe the task fully and
    self-containedly; the tribunal does not see this conversation. Returns the
    tribunal's verdict and final output."""
    # Never executed: the graph router intercepts this call and routes it to the
    # delegate node, which runs the tribunal subgraph. Present only so the model
    # sees the tool schema.
    raise RuntimeError("delegate_to_tribunal must be handled by the delegate node")


# run_python / run_shell are the same sandboxed tools the tribunal worker uses;
# the agent is contained and governed identically — it is not a trusted layer.
# web_search is a boundary tool run host-side by governance (see src/tools/policy.py).
AGENT_TOOLS = [run_python, run_shell, web_search, delegate_to_tribunal]
