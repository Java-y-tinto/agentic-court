from langchain_core.messages import ToolMessage
from langgraph.types import interrupt

from src.logger import logger

from .security import validate_shell_command
from .state import TribunalState
from .tools import TOOLS_BY_NAME


def governance(state: TribunalState) -> dict:
    last = state["worker_messages"][-1]
    tool_results: list[ToolMessage] = []

    for tool_call in last.tool_calls:
        name = tool_call["name"]
        args = tool_call["args"]

        # Auto-block dangerous shell commands before asking the user
        if name == "run_shell":
            check = validate_shell_command(args.get("command", ""))
            if not check.allowed:
                logger.warning("Governance — auto-blocked %s: %s", name, check.reason)
                tool_results.append(ToolMessage(
                    content=f"Blocked by security layer: {check.reason}",
                    tool_call_id=tool_call["id"],
                    name=name,
                ))
                continue

        logger.debug("Governance — awaiting approval for %s(%s)", name, args)
        decision = interrupt({"tool": name, "args": args})

        if str(decision).strip().lower() in ("yes", "y"):
            output = TOOLS_BY_NAME[name].invoke(args)
            content = str(output)
            logger.debug("Governance — %s approved, result: %s", name, content[:200])
        else:
            content = "Tool execution rejected by user."
            logger.info("Governance — %s rejected by user", name)

        tool_results.append(ToolMessage(
            content=content,
            tool_call_id=tool_call["id"],
            name=name,
        ))

    return {"worker_messages": state["worker_messages"] + tool_results}
