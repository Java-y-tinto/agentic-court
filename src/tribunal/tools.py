import ast
import contextlib
import io
import subprocess

from langchain_core.tools import tool

from .security import validate_shell_command


@tool
def run_python(code: str) -> str:
    """Execute Python code. Returns stdout and the value of the last expression (like a REPL)."""
    buffer = io.StringIO()
    namespace: dict = {}
    try:
        tree = ast.parse(code)
        # Split off the last statement if it's a bare expression so we can eval + show its value
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            exec_tree = ast.Module(body=tree.body[:-1], type_ignores=[])
            eval_tree = ast.Expression(body=tree.body[-1].value)
            with contextlib.redirect_stdout(buffer):
                exec(compile(exec_tree, "<string>", "exec"), namespace)
                result = eval(compile(eval_tree, "<string>", "eval"), namespace)
            output = buffer.getvalue()
            if result is not None:
                output += repr(result)
        else:
            with contextlib.redirect_stdout(buffer):
                exec(code, namespace)
            output = buffer.getvalue()
        return output or "Code ran with no output."
    except Exception as e:
        return f"Error: {e}"


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression. Must be a valid Python expression."""
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"Error: {e}"


@tool
def run_shell(command: str) -> str:
    """Execute a shell command and return its output. Dangerous commands are blocked."""
    check = validate_shell_command(command)
    if not check.allowed:
        return f"Blocked by security layer: {check.reason}"
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin"},
        )
        return (proc.stdout + proc.stderr) or "Command ran with no output."
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30 seconds."
    except Exception as e:
        return f"Error: {e}"


TOOLS = [run_python, run_shell, calculator]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
