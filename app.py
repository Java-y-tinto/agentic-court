"""Gradio prototype UI for SentinelAI.

A thin frontend over the same agent graph `main.py` drives. The graph, governance,
and tools are UI-agnostic; this module only wires three things Gradio needs that the
CLI got for free:

1. Per-session lifecycle — each browser session gets its own gVisor sandbox and
   web-search budget, started on first message and torn down via gr.State's
   delete_callback when the session ends.
2. Per-request context activation — ContextVars don't cross threads, and Gradio runs
   each handler on a pool thread, so we re-bind the session's sandbox + web search
   around every graph call (Session.active()).
3. The approval gate — governance pauses the graph mid-turn via interrupt(). The CLI
   drained that with a blocking input(); here it becomes an Approve/Reject panel and
   the turn advances by resuming with Command(resume=...).
"""

import atexit
import os
import signal
import uuid
from contextlib import contextmanager
from pathlib import Path

import gradio as gr
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from src.agent.graph import app
from src.modules.sandbox import Sandbox, cleanup_stale_sandboxes
from src.modules.web_search import WebSearch

load_dotenv()  # TAVILY_API_KEY etc. stay host-side, never enter the sandbox

_WORKSPACE_ROOT = Path(__file__).parent / "workspace"
_SANDBOX_RUNTIME = os.getenv("SANDBOX_RUNTIME", "runsc")
_MAX_WEB_SEARCHES = int(os.getenv("MAX_WEB_SEARCHES", "10"))

# Live sessions, so a graceful shutdown (atexit / SIGTERM) can stop their
# sandboxes promptly. A hard kill (SIGKILL) skips this — the startup sweep in
# main() is the catch-all for containers that outlive their process.
_live_sessions: set["Session"] = set()


class Session:
    """One browser session: a live sandbox, a web-search budget, and a graph thread
    keyed by the same id. Created lazily on the first message; closed via the
    gr.State delete_callback when Gradio drops the session."""

    def __init__(self) -> None:
        self.id = str(uuid.uuid4())
        self.config = {"configurable": {"thread_id": self.id}}
        self.sandbox = Sandbox(self.id, _WORKSPACE_ROOT, runtime=_SANDBOX_RUNTIME)
        self.web_search = WebSearch(_MAX_WEB_SEARCHES)
        self.sandbox.start()
        _live_sessions.add(self)

    @contextmanager
    def active(self):
        """Bind this session's sandbox + web search for the current request."""
        with self.sandbox.activate(), self.web_search.activate():
            yield

    def close(self) -> None:
        self.sandbox.stop()
        _live_sessions.discard(self)


def _shutdown() -> None:
    """Stop every live session's sandbox. Runs on normal exit (atexit) and on
    SIGTERM; idempotent, since close() removes the session from the set."""
    for session in list(_live_sessions):
        session.close()


def _handle_sigterm(signum, frame) -> None:
    _shutdown()
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


def _pending_approval(session: Session) -> dict | None:
    """The first tool call awaiting approval in this session's graph state, or None.
    Mirrors main.py's drain check — governance raises one interrupt at a time."""
    snapshot = app.get_state(session.config)
    for task in snapshot.tasks:
        for iv in task.interrupts:
            return iv.value  # {"tool": ..., "args": ...}
    return None


def _assistant_reply(session: Session) -> str:
    return app.get_state(session.config).values["messages"][-1].content


def _advance(history: list[dict], session: Session):
    """Render the next UI state after a graph step: either an approval gate (graph
    is paused) or the final assistant reply (graph is done)."""
    pending = _pending_approval(session)
    if pending is not None:
        approval_md = (
            "### Approval required\n"
            f"**Tool:** `{pending['tool']}`\n\n"
            "**Args:**\n```\n"
            f"{pending['args']}\n```"
        )
        return (
            history,
            session,
            gr.update(visible=True),            # approval_group
            approval_md,                         # approval_text
            gr.update(interactive=False, value=""),  # msg
        )

    history = history + [{"role": "assistant", "content": _assistant_reply(session)}]
    return (
        history,
        session,
        gr.update(visible=False),
        "",
        gr.update(interactive=True, value=""),
    )


def on_submit(message: str, history: list[dict], session: Session | None):
    message = (message or "").strip()
    if not message:
        return history, session, gr.update(visible=False), "", gr.update(value="")

    if session is None:
        try:
            session = Session()
        except Exception as exc:  # sandbox/Docker/gVisor startup is a real boundary
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": f"Could not start a sandbox session: {exc}"},
            ]
            return history, None, gr.update(visible=False), "", gr.update(value="")

    history = history + [{"role": "user", "content": message}]
    with session.active():
        app.invoke({"messages": [HumanMessage(message)]}, config=session.config)
    return _advance(history, session)


def on_decision(decision: str, history: list[dict], session: Session):
    with session.active():
        app.invoke(Command(resume=decision), config=session.config)
    return _advance(history, session)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="SentinelAI") as demo:
        gr.Markdown("# SentinelAI\nLocal multi-agent tribunal — every host boundary "
                    "crossing needs your approval.")

        # Holds the live Session object; close it when the browser session ends.
        session_state = gr.State(
            value=None,
            delete_callback=lambda s: s.close() if s is not None else None,
        )

        chatbot = gr.Chatbot(height=460, label="Conversation")

        with gr.Group(visible=False) as approval_group:
            approval_text = gr.Markdown()
            with gr.Row():
                approve_btn = gr.Button("Approve", variant="primary")
                reject_btn = gr.Button("Reject", variant="stop")

        msg = gr.Textbox(placeholder="Ask SentinelAI…", show_label=False, autofocus=True)

        outputs = [chatbot, session_state, approval_group, approval_text, msg]

        msg.submit(on_submit, [msg, chatbot, session_state], outputs)
        approve_btn.click(
            lambda h, s: on_decision("yes", h, s), [chatbot, session_state], outputs
        )
        reject_btn.click(
            lambda h, s: on_decision("no", h, s), [chatbot, session_state], outputs
        )

    return demo


if __name__ == "__main__":
    cleanup_stale_sandboxes()  # clear any containers a previous run left behind
    atexit.register(_shutdown)
    signal.signal(signal.SIGTERM, _handle_sigterm)
    build_ui().launch()
