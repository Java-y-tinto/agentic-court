# Governance node. Evaluates each tool call against the PolicyEngine and executes
# the approved ones. As it's set policy, dependency injection is the best pattern
# instead of a singleton or a function.


from langchain_core.messages import ToolMessage
from langgraph.types import interrupt  # Interrupt the graph and ask the user for approval

from src.classes import ToolCall, Verdict, PolicyEngine
from .logger import logger



class Governance:
    def __init__(self, policy: PolicyEngine):
        self._policy = policy

    def __call__(self, state: dict) -> dict:
        last = state["messages"][-1]
        calls = [ToolCall(name=rc["name"], args=rc["args"]) for rc in last.tool_calls]
        evaluations = [self._policy.evaluate(call) for call in calls]

        # Phase 1: collect user decisions. All interrupt() calls must happen
        # before any tool executes — LangGraph replays this whole node on every
        # resume and only interrupt() return values are cached, so anything
        # executed before a pending interrupt would run again on each replay.
        approvals: dict[int, str] = {}
        for i, (call, (verdict, _)) in enumerate(zip(calls, evaluations)):
            if verdict == Verdict.REQUIRE_APPROVAL:
                logger.debug(f"[Governance] Awaiting approval of {call.to_json()}")
                approvals[i] = str(interrupt({"tool": call.name, "args": call.args}))

        # Phase 2: execute. Only reached once every interrupt has a decision,
        # so each tool runs exactly once.
        tool_results: list[ToolMessage] = []
        for i, (raw_call, call, (verdict, reason)) in enumerate(zip(last.tool_calls, calls, evaluations)):
            content = self._handle(call, verdict, reason, approvals.get(i))
            tool_results.append(ToolMessage(content=content, tool_call_id=raw_call["id"], name=call.name))

        return {"messages": tool_results}

    def _handle(self, call: ToolCall, verdict: Verdict, reason: str, decision: str | None) -> str:
        if verdict == Verdict.AUTO_DENY:
            logger.warning(f"[Governance] Blocked {call.name} for: {reason} | {call.to_json()}")
            return f"Blocked by Governance: {reason}"

        if verdict == Verdict.AUTO_ALLOW:
            logger.debug(f"[Governance] Auto-allowed {call.name} | {call.to_json()}")
            return str(self._policy.get_fn(call.name)(**call.args))

        if decision.strip().lower() in ("yes", "y"):
            result = str(self._policy.get_fn(call.name)(**call.args))
            logger.info(f"[Governance] {call.name} approved | result: {result[:200]}")
            return result

        logger.info(f"[Governance] {call.name} rejected by user")
        return "Tool execution rejected by user"
