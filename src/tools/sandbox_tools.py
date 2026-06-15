from langchain_core.tools import tool

from src.modules.sandbox import get_active


@tool
def run_python(code: str) -> str:
    """Execute Python code inside the session sandbox. Use print() to produce output.
    Files written to /workspace are visible to the user; there is no network access."""
    return get_active().run_python(code)


@tool
def run_shell(command: str) -> str:
    """Execute a shell command inside the session sandbox. The working directory
    /workspace is shared with the user for inputs and outputs; there is no network access."""
    return get_active().run_shell(command)


# Sandboxed execution tools, shared by the agent and the tribunal worker.
SANDBOX_TOOLS = [run_python, run_shell]
