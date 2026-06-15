# Tool class, abstraction of what a tool should have


from dataclasses import dataclass, field
from typing import Callable
from .verdict import Verdict


@dataclass
class Rule:
    condition: Callable[[dict], bool]  # takes the tool-call args, returns whether the rule applies
    reason: str
    verdict: Verdict


@dataclass
class Tool:
    name: str
    fn: Callable # The function executed by the governance layer on approval
    default: Verdict # Default policy for the governance layer
    rules: list[Rule] = field(default_factory=list) # List of rules of the tool that govern its use
