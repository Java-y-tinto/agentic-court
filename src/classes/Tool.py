# Tool class, abstraction of what a tool should have


from dataclasses import dataclass, field
from typing import Callable
from .Verdict import Verdict
import re


@dataclass
class Rule:
    condition: Callable[[dict], bool] # a function that takes a list of rules and returns a boolean
    reason: str
    verdict: Verdict



@dataclass
class Tool:
    name: str
    fn: Callable # The function executed by the governance layer on approval
    default: Verdict # Default policy for the governance layer
    rules: list[Rule] = field(default_factory=list) # List of rules of the tool that govern its use

    # Helper function that keeps definitions readable

    def _matches(pattern: str) -> Callable[[dict], bool]:
        return lambda args: bool(re.search(pattern, str(args), re.IGNORECASE)) # Search regex pattern included in the rule
    


# Usage:

# Tool(
#   name="run_shell",
#   fn=run_shell,
#   default=Verdict.REQUIRE_APPROVAL,
#   rules= [
#       Rule(_matches())
#          Rule(_matches(r"\brm\b.{0,30}-[a-zA-Z]*r[a-zA-Z]*f"), "recursive force delete", Verdict.AUTO_DENY),
#          Rule(_matches(r"\bsudo\b|\bsu\s+-"), "privilege escalation", Verdict.AUTO_DENY),
#   ]
#)