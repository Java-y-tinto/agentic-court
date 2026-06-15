from enum import Enum


# Verdict Enum
# auto-deny: ALWAYS block, no prompt, nothing. Returns a reason for being blocked. Patterns that are unsafe regardless of context (eg. {tool:"run_shell", args: "rm -rf / --no-preserve-root"})
# require-approval: Pause the flow and prompt the user. Default.
# auto-allow: execute without prompting. Reserved for tools that are safe or the user has explicitly allowed.


class Verdict(Enum):
    AUTO_ALLOW = "auto-allow"
    REQUIRE_APPROVAL = "require-approval"
    AUTO_DENY = "auto-deny"