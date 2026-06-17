"""Governance policy assembly. Single source of truth for the tools and the
verdict/rules attached to them. The agent and the tribunal share one policy."""

import re
from typing import Callable

from src.classes import PolicyEngine, Rule, Tool, Verdict
from src.modules.governance import Governance

from .sandbox_tools import run_python, run_shell
from .shell_security import BLOCKED_SHELL_PATTERNS
from .web_search import web_search


def _matches(pattern: str) -> Callable[[dict], bool]:
    return lambda args: bool(re.search(pattern, str(args), re.IGNORECASE | re.DOTALL))


def default_governance() -> Governance:
    """The governance shared by the agent and the tribunal: sandboxed run_python /
    run_shell (both require approval; run_shell additionally auto-denies the shell
    blocklist) plus host-side web search (auto-allowed — egress is bounded by the
    rate limiting + logging in the WebSearch layer, not by per-call interruption)."""
    tools = [
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
        Tool(name="web_search", fn=web_search.func, default=Verdict.AUTO_ALLOW),
    ]
    return Governance(PolicyEngine(tools))
