# SentinelAI — Roadmap

## Done
- [x] Tribunal pattern: worker / inspector / judge loop (LangGraph state machine)
- [x] Human-in-the-loop governance with interrupt / approve flow
- [x] Tool registry: `run_python` (REPL-style), `run_shell`, `calculator`
- [x] Pre-sandbox security layer blocking dangerous shell commands before approval
- [x] Structured logging: per-run timestamped files, DEBUG to file / INFO to console

---

## Phase 1 — Usable prototype
_Goal: something you can demo and use for real tasks_

- [ ] **Gradio UI** — replace the blocking `input()` REPL with a web interface
  - Tribunal conversation visible in real time (worker / inspector / judge turns)
  - Approval prompts as interactive buttons, not CLI input
  - Requires rethinking the interrupt/resume flow for async context

- [ ] **File tools** — `read_file`, `write_file`, `list_dir`
  - Scoped to a working directory; no access outside it
  - Governance gates all writes

- [ ] **Tavily web search tool** — API key already in `.env`

- [ ] **Configurable model and max_iterations** — accept CLI flags or a config file instead of hardcoded values; enables quick experimentation without touching code

---

## Phase 2 — Sandboxing
_Goal: the core security differentiator — agents can't touch the host_

- [ ] **Docker sandbox** — run worker tool execution inside a container
  - One container per tribunal session, torn down on completion
  - Volume mount for the working directory only, nothing else
  - Validate the full flow before moving to gVisor

- [ ] **gVisor runtime** — replace Docker's default runtime with `runsc`
  - Kernel syscall interception; agents can't escape to host kernel
  - Pre-created container pool to avoid cold-start latency per task

- [ ] **ZeroMQ bridge** — IPC between sandboxed agent and host governance layer
  - Agents submit tool requests over a socket; governance holds credentials and executes
  - Agents never see API keys, host paths, or network directly

---

## Phase 3 — Memory and persistence
_Goal: agents that improve over sessions_

- [ ] **ChromaDB session memory** — store task/output/critique vectors
  - Worker can retrieve similar past solutions as context
  - Inspector can retrieve past critique patterns
  - Fully local, no cloud dependency

- [ ] **Redis session state** — replace `MemorySaver` (in-process) with Redis
  - Persists tribunal state across process restarts
  - Required once sandboxed agents are separate processes

---

## Phase 4 — Evaluation
_Goal: empirical evidence for the thesis_

- [ ] **Benchmark suite** — fixed set of tasks across complexity levels
  - Code tasks, reasoning tasks, ambiguous/underspecified tasks

- [ ] **Single-agent baseline** — same model, no tribunal, same tools
  - Direct comparison for correctness, hallucination rate, iteration count, latency

- [ ] **Metrics logging** — per-run: iterations used, verdict per cycle, tool calls, wall time
  - Export to CSV for analysis

---

## Phase 5 — Tauri desktop app
_Goal: production-quality UI replacing Gradio for the thesis deliverable_

- [ ] Tauri app (Rust backend + native WebView)
  - Rust backend handles ZeroMQ communication and process lifecycle
  - Smaller binary and attack surface than Electron — directly relevant for a security-focused project
  - Replaces Gradio; all UI features carried over
