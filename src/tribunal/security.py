"""
Pre-sandbox command validation. This is a stopgap until gVisor sandboxing is in place.
It is not a substitute for proper isolation — it is an explicit first filter.
"""

import re
from typing import NamedTuple


class ValidationResult(NamedTuple):
    allowed: bool
    reason: str | None  # None when allowed


_BLOCKED: list[tuple[str, str]] = [
    # Recursive / forced deletion
    (r"\brm\b.{0,30}-[a-zA-Z]*r[a-zA-Z]*f", "recursive force delete"),
    (r"\brmdir\b.*--ignore-fail", "forced directory removal"),
    # Privilege escalation
    (r"\bsudo\b|\bsu\s+-", "privilege escalation"),
    # Disk and filesystem writes
    (r"\bdd\b.*of=/dev/[sh]d", "direct disk write"),
    (r"\bmkfs\b|\bmformat\b", "filesystem formatting"),
    (r">\s*/dev/[sh]d[a-z]", "redirect to raw disk device"),
    # Dangerous permission / ownership changes on system paths
    (r"\bchmod\b.{0,20}[0-7]*[67][0-7][0-7]\s+/", "broad permission change on system path"),
    (r"\bchown\b.*root.*/", "ownership change to root on system path"),
    # Fork bomb
    (r":\(\)\s*\{.*\|.*:.*&.*\}", "fork bomb"),
    # Pipe URL to shell
    (r"\bcurl\b.*\|\s*(ba)?sh", "piping URL to shell"),
    (r"\bwget\b.*-O\s*-\s*\|", "piping URL to shell"),
    # Sensitive file access
    (r"/etc/(passwd|shadow|sudoers|crontab)", "access to sensitive system files"),
    # Reverse shells / netcat
    (r"\bnc\b.*-e|\bnetcat\b.*-e", "netcat reverse shell"),
    (r"\bbash\b.*-i.*>&", "interactive reverse shell redirect"),
    # Kernel / boot tampering
    (r"/boot/|\bgrub\b", "boot or kernel file access"),
]


def validate_shell_command(command: str) -> ValidationResult:
    for pattern, reason in _BLOCKED:
        if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
            return ValidationResult(allowed=False, reason=reason)
    return ValidationResult(allowed=True, reason=None)
