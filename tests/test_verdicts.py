import pytest

from src.tribunal.agents import parse_verdict
from src.tribunal.graph import _route_verdict


@pytest.mark.parametrize("text,expected", [
    ("accept", "accept"),
    ("Accept.", "accept"),
    ('"retry"', "retry"),
    ("I think we should escalate this one.", "escalate"),
    ("ACCEPT\n", "accept"),
])
def test_parse_verdict_tolerates_noise(text, expected):
    assert parse_verdict(text) == expected


@pytest.mark.parametrize("text", [
    "",
    "the solution is correct",
    "accept or retry, hard to say",
])
def test_parse_verdict_escalates_when_ambiguous(text):
    assert parse_verdict(text) == "escalate"


def _state(verdict, iterations, max_iterations=3):
    return {"judge_verdict": verdict, "iterations": iterations, "max_iterations": max_iterations}


def test_accept_on_final_iteration_is_accepted():
    assert _route_verdict(_state("accept", 3)) == "accept"


def test_retry_within_budget():
    assert _route_verdict(_state("retry", 1)) == "retry"


def test_retry_past_budget_escalates():
    assert _route_verdict(_state("retry", 3)) == "escalate"


def test_explicit_escalate():
    assert _route_verdict(_state("escalate", 1)) == "escalate"
