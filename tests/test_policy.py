from src.classes import PolicyEngine, Rule, Tool, ToolCall, Verdict


def _engine():
    return PolicyEngine([
        Tool(
            name="guarded",
            fn=lambda **kw: "ran",
            default=Verdict.REQUIRE_APPROVAL,
            rules=[
                Rule(lambda args: "danger" in str(args), "dangerous args", Verdict.AUTO_DENY),
                Rule(lambda args: "safe" in str(args), "known-safe args", Verdict.AUTO_ALLOW),
            ],
        ),
        Tool(name="free", fn=lambda **kw: "ran", default=Verdict.AUTO_ALLOW),
    ])


def test_unknown_tool_is_denied():
    verdict, reason = _engine().evaluate(ToolCall(name="nope", args={}))
    assert verdict == Verdict.AUTO_DENY
    assert "not in approved registry" in reason


def test_matching_rule_wins_over_default():
    verdict, reason = _engine().evaluate(ToolCall(name="guarded", args={"x": "danger"}))
    assert verdict == Verdict.AUTO_DENY
    assert reason == "dangerous args"


def test_first_matching_rule_wins():
    verdict, _ = _engine().evaluate(ToolCall(name="guarded", args={"x": "danger but safe"}))
    assert verdict == Verdict.AUTO_DENY


def test_falls_back_to_default():
    verdict, _ = _engine().evaluate(ToolCall(name="guarded", args={"x": "benign"}))
    assert verdict == Verdict.REQUIRE_APPROVAL


def test_auto_allow_default():
    verdict, _ = _engine().evaluate(ToolCall(name="free", args={}))
    assert verdict == Verdict.AUTO_ALLOW
