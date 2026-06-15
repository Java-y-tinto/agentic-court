import pytest

from src.classes import ToolCall, Verdict
from src.modules.web_search import WebSearch, WebSearchNotActive, get_active_search


class FakeClient:
    def __init__(self, results):
        self._results = results
        self.calls = []

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return {"results": self._results}


def _results(n=1):
    return [{"title": f"T{i}", "url": f"http://x/{i}", "content": f"c{i}"} for i in range(n)]


def test_formats_results():
    out = WebSearch(client=FakeClient(_results(2))).search("python")
    assert "T0" in out and "http://x/0" in out and "c0" in out


def test_no_results_message():
    assert WebSearch(client=FakeClient([])).search("q") == "No results."


def test_rate_limit_enforced():
    fake = FakeClient(_results(1))
    web = WebSearch(max_searches=2, client=fake)
    assert "T0" in web.search("a")
    assert "T0" in web.search("b")
    assert "budget exhausted" in web.search("c")
    assert len(fake.calls) == 2  # the over-budget call never reached the client


def test_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert "unavailable" in WebSearch().search("q").lower()


def test_client_error_is_caught():
    class Boom:
        def search(self, query, **kwargs):
            raise RuntimeError("network down")

    assert "failed" in WebSearch(client=Boom()).search("q").lower()


def test_get_active_requires_context():
    with pytest.raises(WebSearchNotActive):
        get_active_search()


def test_context_sets_and_resets_active():
    web = WebSearch(client=FakeClient(_results(1)))
    with web as active:
        assert get_active_search() is active
    with pytest.raises(WebSearchNotActive):
        get_active_search()


# --- governance policy: both the agent and the tribunal can web search ---------

def test_agent_and_tribunal_governance_allow_web_search():
    from src.agent.graph import _governance as agent_gov
    from src.tribunal.graph import _governance as tribunal_gov

    call = ToolCall(name="web_search", args={"query": "x"})
    assert agent_gov._policy.evaluate(call)[0] == Verdict.AUTO_ALLOW
    assert tribunal_gov._policy.evaluate(call)[0] == Verdict.AUTO_ALLOW


def test_unregistered_tool_is_still_denied():
    from src.tribunal.graph import _governance as tribunal_gov

    verdict, _ = tribunal_gov._policy.evaluate(ToolCall(name="rm_rf", args={}))
    assert verdict == Verdict.AUTO_DENY
