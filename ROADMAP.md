# SentinelAI — Roadmap

## Architecture decisions

- **Host-trusted orchestration.** The LangGraph loop and LLM calls run as a trusted
  process on the host; only the agent's *actions* execute inside the gVisor sandbox.
  The untrusted thing is model output, and it never runs anywhere but the container.
  Consequence: no ZeroMQ bridge (nothing lives in the cage except generated code) and
  no need to give the sandbox network access.
- **Approval at the boundary, not per tool call.** Actions contained by the sandbox are
  auto-allowed; human approval is reserved for boundary crossings — anything that sends
  data out (web search, URL fetch) or touches the host. Outbound queries are an egress
  channel (prompt-injected exfiltration), which is why they prompt.
- **Credential blindness.** API keys live only in the host governance layer, which
  executes boundary tools on the agent's behalf and writes results into the workspace.
  The agent never sees a key, a host path, or the network.
- **No container pool.** Bind mounts are fixed at container creation, so pooled
  containers can't receive per-session workspaces; gVisor cold start is sub-second
  anyway (measure once and cite in the thesis).

---

## Done

- [x] Tribunal pattern: worker / inspector / judge loop (LangGraph state machine)
- [x] Human-in-the-loop governance with interrupt / approve flow
- [x] Tool registry: `run_python`, `run_shell`
- [x] Shell-command regex blocklist enforced as `AUTO_DENY` governance rules
- [x] Structured logging: per-run timestamped files, DEBUG to file / INFO to console
- [x] Governance phase 1: `PolicyEngine` with per-tool `Rule` lists and `AUTO_ALLOW` / `REQUIRE_APPROVAL` / `AUTO_DENY` verdicts
- [x] Docker sandbox — one container per tribunal session, `workspace/<session_id>` mount only, no network (`src/modules/sandbox.py`)
- [x] gVisor runtime (`runsc`) as default; `SANDBOX_RUNTIME=runc` escape hatch for dev
- [x] Container hardening: non-root user, `cap_drop=ALL`, `no-new-privileges`, read-only rootfs, tmpfs `/tmp`, resource limits
- [x] Two-phase governance node (interrupts before execution — no double-execution on LangGraph replay)
- [x] Configurable via env vars: `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `JUDGE_MODEL`, `MAX_ITERATIONS`
- [x] Test suite: policy engine, blocklist, verdict parsing/routing (`uv run pytest`)

---

## Phase 1 — Usable prototype
_Goal: something you can demo and use for real tasks_

- [ ] **Move the approval boundary** — flip `run_python` / `run_shell` to `AUTO_ALLOW`
  - The sandbox is the security control; approving commands inside it adds friction, not security
  - Regex blocklist stays as a logged `AUTO_DENY` defense-in-depth layer
  - `REQUIRE_APPROVAL` becomes the policy for boundary-crossing tools only

- [ ] **Boundary tools, executed host-side by governance** — first one: Tavily web search
  - Governance runs the tool with the host-held API key and writes results into the workspace; the agent only sees content
  - `REQUIRE_APPROVAL`: the user reads the outbound query before it leaves (egress gate)

- [ ] **File tools** — `read_file`, `write_file`, `list_dir`
  - Execute inside the sandbox, scoped to `/workspace`; structured tools are more reliable for small models than shell one-liners

- [ ] **Gradio UI** — replace the blocking `input()` REPL
  - Tribunal conversation visible in real time (worker / inspector / judge turns)
  - Approval prompts as interactive buttons; requires rethinking interrupt/resume for async
  - Drag-and-drop file input → copy into `workspace/<session_id>/`
  - Output listing/download skips symlinks (agent could plant links to host paths)

- [x] **Configurable model and max_iterations** — env vars `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `JUDGE_MODEL` (separate judge model mitigates self-evaluation bias), `MAX_ITERATIONS`

---

## Phase 2 — Memory and persistence
_Goal: agents that improve over sessions_

- [ ] **ChromaDB session memory** — store task/output/critique vectors
  - Worker can retrieve similar past solutions as context
  - Inspector can retrieve past critique patterns
  - Fully local, no cloud dependency

- [ ] **(Optional) Redis checkpointer** — replace `MemorySaver` to persist tribunal
  state across process restarts. No longer required: agents stay in-process under
  host-trusted orchestration

---

## Phase 3 — Evaluation
_Goal: empirical evidence for the thesis_

- [ ] **Benchmark suite** — fixed set of tasks across complexity levels
  - Code tasks, reasoning tasks, ambiguous/underspecified tasks

- [ ] **Single-agent baseline** — same model, no tribunal, same tools
  - Direct comparison for correctness, hallucination rate, iteration count, latency

- [ ] **Judge-model bias control** — run benchmarks with `JUDGE_MODEL` different from
  the worker model; report agreement between judge models on a sample

- [ ] **Metrics logging** — per-run: iterations used, verdict per cycle, tool calls, wall time
  - Export to CSV for analysis
  - Include sandbox cold-start measurement (supports the no-pool decision)

---

## Phase 4 — Tauri desktop app
_Goal: production-quality UI replacing Gradio for the thesis deliverable_

- [ ] Tauri app (Rust backend + native WebView)
  - Rust backend manages the Python orchestrator's process lifecycle and streams its events to the UI
  - Smaller binary and attack surface than Electron — directly relevant for a security-focused project
  - Replaces Gradio; all UI features carried over (drag-and-drop, approval buttons, symlink-safe output handling)
