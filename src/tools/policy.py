"""Governance policy assembly. Single source of truth for which tools each layer
(agent, tribunal) exposes and the verdict/rules attached to them, so the policy is
defined once and composed per layer rather than duplicated."""

import re
from typing import Callable

from src.classes import PolicyEngine, Rule, Tool, Verdict
from src.modules.governance import Governance

from .sandbox_tools import run_python, run_shell
from .shell_security import BLOCKED_SHELL_PATTERNS
from .web_search import web_search


def _matches(pattern: str) -> Callable[[dict], bool]:
    return lambda args: bool(re.search(pattern, str(args), re.IGNORECASE | re.DOTALL))


def sandbox_policy_tools() -> list[Tool]:
    """Sandboxed execution tools, shared by the agent and the tribunal. Both
    require approval; run_shell additionally auto-denies the shell blocklist."""
    return [
        Tool(name="run_python", fn=run_python.func, default=Verdict.REQUIRE_APPROVAL),
        Tool(
            name="run_shell",
            fn=run_shell.func,
            default=Verdict.REQUIRE_APPROVAL,
            rules=[
                Rule(_matches(pattern), reason, Verdict.AUTO_DENY)
                for pattern, reason in BLOCKED_SHELL_PATTERNS
            ],
        ),
    ]


def web_search_policy_tool() -> Tool:
    """Host-side web search. Auto-allowed (no per-call approval); egress is bounded
    by the rate limiting + logging in the WebSearch layer, not by interruption."""
    return Tool(name="web_search", fn=web_search.func, default=Verdict.AUTO_ALLOW)


def make_governance(tools: list[Tool]) -> Governance:
    return Governance(PolicyEngine(tools))
