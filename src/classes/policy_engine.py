
# Policy Engine class. Takes a Tool and orchestrates its policy enforcement. Checks rules and falls back on the default Verdict if none are present

from .tool import Tool
from .tool_call import ToolCall
from .verdict import Verdict
from typing import Callable


class PolicyEngine:
    # List of tools in the registry
    def __init__(self, tools: list[Tool]):
        self._tools = {t.name: t for t in tools}

    # Evaluate the tool rules before execution, returns a tuple with the verdict and its reason
    def evaluate(self, call: ToolCall) -> tuple[Verdict, str]:
        tool = self._tools.get(call.name)

        if tool is None:
            return Verdict.AUTO_DENY, "tool not in approved registry"
        
        for rule in tool.rules:
            if rule.condition(call.args):
                return rule.verdict, rule.reason
            
        return tool.default, "no rule matched. Fallback to default verdict"
    
    def get_fn(self, name: str) -> Callable:
        return self._tools[name].fn