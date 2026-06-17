# SentinelAI

A local, security-first multi-agent platform for complex tasks. A conversational agent handles day-to-day work and delegates the hard parts to an adversarial **worker / inspector / judge** tribunal. Both run inside isolated gVisor containers with zero-trust tool access and human-in-the-loop approval before any action touches the host.

This is also my Master's thesis (TFM) — the research question is whether an adversarial multi-agent loop measurably outperforms a single agent on correctness and hallucination rate.

---

## How it works

There are two layers. A **day-to-day agent** holds the conversation and does simple work itself; when a task is complex, error-prone, or correctness-critical, it delegates to the **tribunal** — an adversarial worker / inspector / judge loop. Both layers run the same sandboxed tools through the same governance, so the agent is *not* a trusted supervisor.

```
START → agent → ┬─ final answer ──────────────────────────────────────→ END
                ├─ tool call ── [governance] ──────────────────────────→ agent
                └─ delegate ──→ tribunal ──→ verdict + output ──────────→ agent

tribunal:  START → worker → [governance] → inspector → judge → accept / retry / escalate
                              ↑________________________________________|
```

| Agent | Role |
|-------|------|
| **Worker** | Completes the task; calls tools when needed; on retry, receives its previous output plus the inspector's critique |
| **Inspector** | Adversarially reviews the output — finds logical errors, edge cases, security issues, mismatches with requirements; never writes code, only critiques |
| **Judge** | Emits exactly one word: `accept`, `retry`, or `escalate`; a hard iteration ceiling forces escalation when the loop doesn't converge |

Tool calls are intercepted by a **governance layer** before execution:

1. A static security filter blocks known-dangerous shell patterns (fork bombs, reverse shells, disk writes, privilege escalation, piping URLs to shells) without asking.
2. Sandboxed tool calls (`run_python` / `run_shell`) are paused with LangGraph `interrupt`, shown to the user, and only executed on explicit approval.
3. `web_search` is the exception: it runs host-side under hard controls — credential-blind, search-only, per-session rate-limited, and logged — rather than a per-call prompt, since approving every query is impractical for a day-to-day agent.

No agent ever holds credentials or host paths directly.

---

## Stack

| Component | Role | Status |
|-----------|------|--------|
| **LangGraph** | Agent + tribunal state machines — explicit, inspectable graphs | Implemented |
| **Ollama** | Local LLM inference (`qwen2.5` by default, any model configurable) — no cloud APIs | Implemented |
| **Python security layer** | Pre-sandbox shell-command validation (regex blocklist) | Implemented |
| **Docker** | Per-session container sandbox for tool execution | Implemented |
| **gVisor** | Container runtime with kernel syscall interception | Implemented (`scripts/setup-gvisor.sh`) |
| **Tavily** | Host-side web search backend — credential-blind, rate-limited, pluggable (SearXNG / DuckDuckGo drop in) | Implemented |
| **Gradio** | Web UI for the approval flow and conversation (`app.py`) | Prototype |
| **ChromaDB** | Local vector store for session memory and RAG | Planned |
| **Redis** | Optional checkpointer to persist state across restarts (replaces `MemorySaver`) | Planned |
| **Tauri** | Desktop UI (Rust backend + native WebView) — replaces Gradio for the final deliverable | Planned |

> ZeroMQ was considered for an agent↔host IPC bridge and dropped: orchestration is host-trusted, so nothing runs inside the container that would need a bridge.

---

## Architecture

```
src/
├── agent/        — day-to-day agent: state, agent node, tools, graph (the main.py entry point)
├── tribunal/     — worker / inspector / judge / escalate nodes, state, and graph
├── tools/        — capability layer shared by both: sandbox tools, web search,
│                   shell blocklist, and the single-source-of-truth governance policy
├── modules/      — governance node, gVisor sandbox, host-side web search, logger
└── classes/      — Verdict enum, Rule / Tool dataclasses, ToolCall, PolicyEngine
```

`main.py` runs the agent graph, which embeds the tribunal as a subgraph compiled **without its own checkpointer** — so a governance `interrupt` raised inside a delegated run surfaces and resumes at the top level, and delegated work shares the same active sandbox session. The agent graph is compiled with `MemorySaver` so state survives across `interrupt` / resume cycles in the same process; an optional Redis checkpointer would persist it across restarts.

---

## Getting started

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/), [uv](https://github.com/astral-sh/uv)

```bash
# 1. Clone and install dependencies
git clone https://github.com/java-y-tinto/agentic-court.git
cd agentic-court
uv sync

# 2. Start the Ollama inference server
docker compose up -d

# 3. Pull the model (first run only)
docker exec ollama ollama pull qwen2.5

# 4. Install gVisor and register the runsc Docker runtime (first run only)
sudo bash scripts/setup-gvisor.sh

# 5. (Optional) Add a Tavily API key for web search
echo "TAVILY_API_KEY=your_key_here" > .env

# 6. Run — CLI REPL
uv run python main.py

# …or the Gradio web UI prototype
uv run python app.py
```

When the agent (or a delegated worker) requests a sandboxed tool call, you are prompted to approve or reject it before it executes inside the session's container.

---

## Tools

| Tool | Available to | Description |
|------|-------------|-------------|
| `run_python` | Agent, worker | Executes a Python snippet inside the session sandbox container (user approval) |
| `run_shell` | Agent, worker | Executes a shell command inside the session sandbox (regex blocklist + user approval) |
| `web_search` | Agent, worker | Host-side web search — credential-blind, search-only, rate-limited, logged; no per-call prompt |
| `delegate_to_tribunal` | Agent | Hands a single self-contained task to the worker / inspector / judge tribunal |

Sandboxed tools run in a gVisor container with no network access. The only surface shared with the host is the session workspace (`workspace/<session_id>/`, mounted at `/workspace` inside the container): drop input files there before or during the task, and collect any output files the agent produces from the same directory. The container is destroyed when the task ends; the workspace directory persists.

For development without gVisor, `SANDBOX_RUNTIME=runc uv run python main.py` falls back to the standard runtime (no kernel-level isolation).

---

## Roadmap

| Phase | Goal | Key items |
|-------|------|-----------|
| **Done** | Core platform | Agent + tribunal loop, gVisor sandbox, governance, host-side web search, Gradio approval prototype |
| **1** | Finish prototype | Auto-allow sandboxed tools, file tools, real-time turn streaming + file drag-and-drop in the UI |
| **2** | Memory & persistence | ChromaDB session vectors, optional Redis checkpointer |
| **3** | Evaluation | Benchmark suite, single-agent baseline, metrics export |
| **4** | Desktop app | Tauri UI replacing Gradio |

See [ROADMAP.md](ROADMAP.md) for detail.

---

## Research context

The thesis evaluates whether the tribunal pattern (adversarial multi-agent loop) outperforms a single agent of equal capability. The benchmark will measure:

- **Correctness** — does the output satisfy the task requirements?
- **Hallucination rate** — factual or logical errors per task
- **Task completion** — pass/fail on a fixed task set
- **Iteration count** — how many retry cycles were needed
- **Latency** — wall time per task

The security architecture (gVisor sandboxing + host-trusted orchestration + zero-trust governance) is a first-class design goal, not an afterthought — it is what makes deploying capable tool-using agents to real workstations defensible.

---

## Learning experiments

`experiments/` contains the incremental research that led to the current architecture:

| Experiment | Topic |
|------------|-------|
| 1–2 | LangGraph state and conditional edges |
| 3–4 | Integrating `ChatOllama`, multi-turn chat |
| 5–6 | Tool use: manual dispatch vs. `ToolNode` / `tools_condition` |
| 7 | Human-in-the-loop with `interrupt`, `Command`, and `MemorySaver` checkpointing |
| 8 | Full tribunal multi-agent loop |

---

## License

MIT
