# Policy engine. Takes a tool name and its arguments. Returns a verdict based on set policy.
# As it's set policy, dependency injection is the best pattern instead of a singleton or a function


from langchain_core.messages import ToolMessage
from langgraph.types import interrupt  # Interrupt the graph and ask the user for approval

from src.classes import ToolCall, Verdict, PolicyEngine
from .logger import logger



class Governance: 
    def __init__(self, policy: PolicyEngine):
        self._policy = policy

    # Tool call
    def __call__(self, state: dict) -> dict:
        # Read the last message from the langgraph state
        last = state["messages"][-1]
        tool_results: list[ToolMessage] = []

        for raw_call in last.tool_calls:
            # Wrap in a ToolCall object
            call = ToolCall(name=raw_call["name"], args=raw_call["args"])
            # Ask the policyengine for a verdict
            verdict, reason = self._policy.evaluate(call)

            content = self._handle(call, verdict, reason) # Call the handling function
            # Append it to the State's tool results
            tool_results.append(ToolMessage(content=content, tool_call_id=raw_call["id"], name=call.name))

        return {"messages": tool_results}
    
    # Handle the tool calls and return the PolicyEngine's verdict to the Agent

    def _handle(self, call: ToolCall, verdict: Verdict, reason: str) -> str:
        if verdict == Verdict.AUTO_DENY:
            logger.warning(f"[Governance] Blocked {call.name} for: {reason} | {call.to_json()}")
            return f"Blocked by Governance: {reason}"
        
        if verdict == Verdict.AUTO_ALLOW:
            logger.debug(f"[Governance] Auto-allowed {call.name} | {call.to_json()}")
            return str(self._policy.get_fn(call.name)(**call.args))

        logger.debug(f"[Governance] Awaiting approval of {call.to_json()}")

        # Ask the user
        decision = interrupt({"tool": call.name, "args": call.args})

        if str(decision).strip().lower() in ("yes", "y"):
            #Execute the tool function
            result  = str(self._policy.get_fn(call.name)(**call.args))
            logger.info(f"[Governance] {call.name} approved | result: {result[:200]}")
            return result

        logger.info(f"[Governance] {call.name} rejected by user")
        return "Tool execution rejected by user"


        