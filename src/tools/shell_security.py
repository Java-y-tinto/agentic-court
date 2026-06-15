"""
Shell-command regex blocklist, enforced as AUTO_DENY governance rules (see
src/tools/policy.py). Defense-in-depth on top of the sandbox, not a substitute
for it — it only filters the legible path (run_shell), not e.g. os.system from
run_python, which still requires user approval.
"""

# (pattern, reason) pairs; matched case-insensitively against the tool-call args
BLOCKED_SHELL_PATTERNS: list[tuple[str, str]] = [
    # Recursive / forced deletion: rm with both a recursive and a force flag,
    # in either order, short or long form
    (r"\brm\b(?=.{0,60}((?<!-)-[a-zA-Z]*r|--recursive))(?=.{0,60}((?<!-)-[a-zA-Z]*f|--force))", "recursive force delete"),
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
    (r"\bwget\b.*-O\s*-.*\|", "piping URL to shell"),
    # Sensitive file access
    (r"/etc/(passwd|shadow|sudoers|crontab)", "access to sensitive system files"),
    # Reverse shells / netcat
    (r"\bnc\b.*-e|\bnetcat\b.*-e", "netcat reverse shell"),
    (r"\bbash\b.*-i.*>&", "interactive reverse shell redirect"),
    # Kernel / boot tampering
    (r"/boot/|\bgrub\b", "boot or kernel file access"),
]
