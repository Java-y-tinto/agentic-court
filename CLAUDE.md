# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the tribunal
uv run python main.py

# Run a learning experiment
uv run python "learning experiments/experiment_8.py"

# Start Ollama (required for all LLM calls)
docker compose up -d

# Pull the model used (first time only)
docker exec ollama ollama pull qwen2.5
```

## Project goal

**SentinelAI** — a Master's thesis (TFM) project. Think OpenClaw but with proper security: a local multi-agent platform for **complex tasks that warrant a multi-agent environment**, where an adversarial tribunal (worker/inspector/judge) operates inside isolated gVisor containers with zero-trust access and human-in-the-loop approval for every tool use.

The learning experiments in `learning experiments/` are the research phase. `main.py` is currently a stub.

## Planned full stack

| Component | Role |
|-----------|------|
| LangGraph | Tribunal state machine (explicit, inspectable state — chosen over AutoGen/CrewAI for this reason) |
| Ollama | Local LLM inference; local-first principle, no cloud APIs by default |
| gVisor | Container runtime for sandboxing agent sessions (kernel syscall interception; preferred over plain Docker because Docker containers share the host kernel) |
| ZeroMQ | IPC bridge between isolated agent containers and the host governance layer; agents never get credentials or host paths directly |
| Redis | Async approval queue between agents and governance, plus short-term shared state for tribunal sessions |
| ChromaDB | Embedded vector store for RAG/long-term memory (no external server, fully local) |
| Tauri | Desktop UI (Rust backend + native WebView — chosen over Electron for smaller binary/attack surface) |
| Tavily | Web search tool (API key in `.env`) |

Note: `gradio` is in `pyproject.toml` and may be used for early prototyping before the Tauri UI is built. ZeroMQ, Redis, and gVisor are not yet in `pyproject.toml`.

## Architecture

**Source layout** (`src/tribunal/`):
- `state.py` — `TribunalState` TypedDict
- `tools.py` — tool definitions + `TOOLS` / `TOOLS_BY_NAME` registry
- `agents.py` — `worker`, `inspector`, `judge`, `escalate` node functions
- `governance.py` — intercepts tool calls, interrupts for user approval, executes on approval
- `graph.py` — assembles the `StateGraph`, compiles with `MemorySaver`

**The tribunal pattern** (implemented in `src/tribunal/`):
- `TribunalState` holds `task`, `worker_output`, `inspector_critique`, `judge_verdict`, `iterations`, `max_iterations`
- **worker** → generates output; on retries, receives previous output + inspector critique
- **inspector** → adversarially critiques the output; instructed never to write code, only critique in plain text
- **judge** → emits exactly one word: `accept`, `retry`, or `escalate`
- `route_verdict` conditional edge maps the verdict; a hard `max_iterations` ceiling forces escalation
- Graph: `START → worker → inspector → judge → (accept: END | retry: worker | escalate: escalate_node → END)`

**Security model (target architecture):**
- Zero-trust: no agent has direct system or network access
- All tool calls pass through a governance layer that is credential-agnostic
- Any action affecting the host requires explicit user approval before execution
- gVisor + pre-created container pool for each tribunal session
- ZeroMQ bridge exposes only approved tools to agents inside the sandbox

**Learning experiments** in `learning experiments/` build up to this pattern:
- 1–2: Basic LangGraph state and conditional edges
- 3–4: Integrating `ChatOllama`, multi-turn chat
- 5–6: Tool use, manual vs. `ToolNode`/`tools_condition`
- 7: Human-in-the-loop with `interrupt`, `Command`, and `MemorySaver` checkpointing
- 8: The full tribunal multi-agent loop

## Evaluation plan

The finished system will be benchmarked: tribunal vs. single-agent on complex tasks — measuring correctness, hallucination rate, task completion, iteration count, and latency.