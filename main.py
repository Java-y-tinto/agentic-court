import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from src.agent.graph import app
from src.modules.sandbox import Sandbox
from src.modules.web_search import WebSearch

_WORKSPACE_ROOT = Path(__file__).parent / "workspace"
_SANDBOX_RUNTIME = os.getenv("SANDBOX_RUNTIME", "runsc")
_MAX_WEB_SEARCHES = int(os.getenv("MAX_WEB_SEARCHES", "10"))


def _drain_interrupts(config: dict) -> dict:
    """Resume any pending governance approvals and return the final state. A
    delegated tribunal run interrupts here too — its approvals surface at the
    top level just like the agent's own tool calls."""
    while True:
        snapshot = app.get_state(config)
        pending = [iv for t in snapshot.tasks for iv in t.interrupts]
        if not pending:
            return snapshot.values

        iv = pending[0]
        print(f"\n  [Approval required]")
        print(f"  Tool : {iv.value['tool']}")
        print(f"  Args : {iv.value['args']}")
        decision = input("  Approve? (yes/no): ").strip()
        app.invoke(Command(resume=decision), config=config)


def main():
    load_dotenv()  # TAVILY_API_KEY etc. stay host-side, never enter the sandbox
    print("SentinelAI — type 'exit' to quit\n")

    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    with (
        Sandbox(session_id, _WORKSPACE_ROOT, runtime=_SANDBOX_RUNTIME) as sandbox,
        WebSearch(_MAX_WEB_SEARCHES),
    ):
        print(f"Sandbox workspace: {sandbox.workspace} (mounted at /workspace)\n")

        while True:
            user = input("You: ").strip()
            if not user or user.lower() == "exit":
                break

            app.invoke({"messages": [HumanMessage(user)]}, config=config)
            state = _drain_interrupts(config)
            reply = state["messages"][-1].content
            print(f"\nAssistant: {reply}\n")


if __name__ == "__main__":
    main()
