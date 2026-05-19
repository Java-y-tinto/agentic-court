# SentinelAI

A local, security-first multi-agent platform for complex tasks. SentinelAI runs an adversarial **worker / inspector / judge** court inside isolated containers, with zero-trust tool access and human-in-the-loop approval before any action touches the host.

This is also my Master's thesis (TFM) — the research question is whether an adversarial multi-agent loop measurably outperforms a single agent on correctness and hallucination rate.

---

## How it works

Every task runs through a three-agent loop:

```
START → worker → [governance] → inspector → judge → accept / retry / escalate
                      ↑____________________________|
```

| Agent | Role |
|-------|------|
| **Worker** | Completes the task; calls tools when needed; on retry, receives its previous output plus the inspector's critique |
| **Inspector** | Adversarially reviews the output — finds logical errors, edge cases, security issues, mismatches with requirements; never writes code, only critiques |
| **Judge** | Emits exactly one word: `accept`, `retry`, or `escalate`; a hard iteration ceiling forces escalation when the loop doesn't converge |

Tool calls from the worker are intercepted by a **governance layer** before execution:

1. A static security filter blocks known-dangerous patterns (fork bombs, reverse shells, disk writes, privilege escalation, piping URLs to shells) without asking.
2. Safe tool calls are paused with LangGraph `interrupt`, shown to the user, and only executed on explicit approval.

No agent ever holds credentials or host paths directly.

---

## Stack

| Component | Role | Status |
|-----------|------|--------|
| **LangGraph** | Tribunal state machine — explicit, inspectable graph | Implemented |
| **Ollama** | Local LLM inference (`qwen2.5`) — no cloud APIs by default | Implemented |
| **Python security layer** | Pre-sandbox command validation (regex blocklist) | Implemented |
| **Gradio** | Web UI for the approval flow and tribunal conversation | Planned (Phase 1) |
| **Docker** | Per-session container sandbox for tool execution | Planned (Phase 2) |
| **gVisor** | Container runtime with kernel syscall interception | Planned (Phase 2) |
| **ZeroMQ** | IPC bridge between sandboxed agents and host governance | Planned (Phase 2) |
| **Redis** | Async approval queue; persistent session state | Planned (Phase 3) |
| **ChromaDB** | Local vector store for session memory and RAG | Planned (Phase 3) |
| **Tauri** | Desktop UI (Rust backend + native WebView) — replaces Gradio for the final deliverable | Planned (Phase 5) |

---

## Architecture

```
src/tribunal/
├── state.py       — TribunalState TypedDict
├── tools.py       — tool definitions + TOOLS / TOOLS_BY_NAME registry
├── agents.py      — worker, inspector, judge, escalate node functions
├── governance.py  — intercepts tool calls; interrupts for user approval
├── security.py    — pre-sandbox static command validation
└── graph.py       — assembles and compiles the StateGraph
```

The graph is compiled with `MemorySaver` so tribunal state survives across `interrupt` / resume cycles in the same process. Redis will replace this once agents run in separate sandboxed processes.

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

# 4. (Optional) Add a Tavily API key for web search
echo "TAVILY_API_KEY=your_key_here" > .env

# 5. Run
uv run python main.py
```

When the worker requests a tool call, you will be prompted to approve or reject it before it executes.

---

## Tools available to the worker

| Tool | Description |
|------|-------------|
| `run_python` | Executes a Python snippet in an isolated REPL-style environment |
| `run_shell` | Executes a shell command (subject to security validation and user approval) |
| `calculator` | Evaluates a mathematical expression |

---

## Roadmap

| Phase | Goal | Key items |
|-------|------|-----------|
| **1** | Usable prototype | Gradio UI, file tools, Tavily search, CLI config |
| **2** | Sandboxing | Docker per-session containers → gVisor runtime → ZeroMQ bridge |
| **3** | Memory & persistence | ChromaDB session vectors, Redis state |
| **4** | Evaluation | Benchmark suite, single-agent baseline, metrics export |
| **5** | Desktop app | Tauri UI replacing Gradio |

See [ROADMAP.md](ROADMAP.md) for detail.

---

## Research context

The thesis evaluates whether the tribunal pattern (adversarial multi-agent loop) outperforms a single agent of equal capability. The benchmark will measure:

- **Correctness** — does the output satisfy the task requirements?
- **Hallucination rate** — factual or logical errors per task
- **Task completion** — pass/fail on a fixed task set
- **Iteration count** — how many retry cycles were needed
- **Latency** — wall time per task

The security architecture (gVisor + ZeroMQ + zero-trust governance) is a first-class design goal, not an afterthought — it is what makes deploying capable tool-using agents to real workstations defensible.

---

## Learning experiments

`learning experiments/` contains the incremental research that led to the current architecture:

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
