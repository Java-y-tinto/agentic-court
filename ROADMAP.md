# SentinelAI — Roadmap

## Architecture decisions

- **Host-trusted orchestration.** The LangGraph loop and LLM calls run as a trusted
  process on the host; only the agent's *actions* execute inside the gVisor sandbox.
  The untrusted thing is model output, and it never runs anywhere but the container.
  Consequence: no ZeroMQ bridge (nothing lives in the cage except generated code) and
  no need to give the sandbox network access.
- **Approval at the boundary, not per tool call.** Human approval is reserved for actions
  that touch the host. Actions contained by the sandbox are the security control in
  themselves (flipping `run_python` / `run_shell` to `AUTO_ALLOW` is the remaining Phase 1
  step — they still prompt today). Egress is the exception to a per-call prompt:
  approving every web search is impractical friction for a day-to-day agent, so web
  search runs host-side under **hard controls** — credential-blind, search-only (no
  arbitrary URL fetch/POST), per-session rate-limited, and logged — with a hardened
  system prompt as defense-in-depth against prompt-injected exfiltration, not as the sole
  control. (Earlier this was an approval gate; the hard-controls model replaced it.)
- **Agent + tribunal, both untrusted.** A conversational agent handles day-to-day work and
  delegates complex or correctness-critical tasks to the tribunal. The agent is *not* a
  trusted supervisor: its tool calls run in the same sandbox and pass through the same
  governance as the tribunal. The tribunal is embedded as a subgraph compiled without its
  own checkpointer, so a governance interrupt raised inside a delegated run surfaces and
  resumes at the top level, and both share the one active sandbox session.
- **Credential blindness.** API keys live only in the host governance layer, which
  executes boundary tools on the agent's behalf and writes results into the workspace.
  The agent never sees a key, a host path, or the network.
- **No container pool.** Bind mounts are fixed at container creation, so pooled
  containers can't receive per-session workspaces; gVisor cold start is sub-second
  anyway (measure once and cite in the thesis).

---

## Done

- [x] Tribunal pattern: worker / inspector / judge loop (LangGraph state machine)
- [x] Day-to-day agent that delegates complex tasks to the tribunal (`delegate_to_tribunal`); tribunal embedded as a checkpointer-less subgraph so its interrupts surface at the top level, sharing one sandbox session (`src/agent/`)
- [x] Human-in-the-loop governance with interrupt / approve flow
- [x] Single governance policy shared by the agent and the tribunal (`src/tools/policy.py`)
- [x] Tool registry: `run_python`, `run_shell`, `web_search`
- [x] Host-side web search (Tavily backend, pluggable): credential-blind, search-only, per-session rate-limited, logged; `AUTO_ALLOW` under hard controls rather than a per-call approval gate (`src/modules/web_search.py`)
- [x] Shell-command regex blocklist enforced as `AUTO_DENY` governance rules
- [x] Structured logging: per-run timestamped files, DEBUG to file / INFO to console
- [x] Governance phase 1: `PolicyEngine` with per-tool `Rule` lists and `AUTO_ALLOW` / `REQUIRE_APPROVAL` / `AUTO_DENY` verdicts
- [x] Docker sandbox — one container per tribunal session, `workspace/<session_id>` mount only, no network (`src/modules/sandbox.py`)
- [x] gVisor runtime (`runsc`) as default; `SANDBOX_RUNTIME=runc` escape hatch for dev
- [x] Container hardening: non-root user, `cap_drop=ALL`, `no-new-privileges`, read-only rootfs, tmpfs `/tmp`, resource limits
- [x] Two-phase governance node (interrupts before execution — no double-execution on LangGraph replay)
- [x] Configurable via env vars: `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `JUDGE_MODEL`, `MAX_ITERATIONS`, `MAX_WEB_SEARCHES`
- [x] Gradio approval-flow UI prototype — chat + Approve/Reject buttons over the same graph, per-session sandbox lifecycle (`app.py`)
- [x] Test suite: policy engine, blocklist, verdict parsing/routing, agent routing, web search (`uv run pytest`)

---

## Phase 1 — Finish the prototype
_Goal: something you can demo and use for real tasks. The core loop, sandbox, governance,
host-side web search, and a Gradio approval UI are done (see above); what remains:_

- [ ] **Move the approval boundary** — flip `run_python` / `run_shell` to `AUTO_ALLOW`
  - The sandbox is the security control; approving commands inside it adds friction, not security
  - Regex blocklist stays as a logged `AUTO_DENY` defense-in-depth layer
  - `REQUIRE_APPROVAL` becomes the policy for boundary-crossing tools only

- [ ] **File tools** — `read_file`, `write_file`, `list_dir`
  - Execute inside the sandbox, scoped to `/workspace`; structured tools are more reliable for small models than shell one-liners

- [ ] **Finish the Gradio UI** — the approval gate and chat exist; still to add:
  - Agent / worker / inspector / judge turns visible in real time (currently only the final reply is shown)
  - Drag-and-drop file input → copy into `workspace/<session_id>/`
  - Output listing/download skipping symlinks (agent could plant links to host paths)

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
