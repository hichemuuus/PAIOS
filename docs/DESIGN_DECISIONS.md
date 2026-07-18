# Design Decisions

Every non-trivial architectural decision in Veyron, with rationale.
See `DECISIONS.md` for the chronological log of assumptions made during development.

---

## Why DAG Planning Instead of Linear Chains?

Linear chains fail for complex tasks. DAG enables parallel execution of independent steps, proper dependency resolution via topological sort, and circular dependency detection via DFS. The planner generates a dependency graph, validates it, then executes ready steps concurrently via `asyncio.gather()`. This reduces total execution time for multi-step tasks by 30-60% compared to sequential execution.

## Why Hybrid ML + LLM Architecture?

Micro-models (scikit-learn) handle deterministic classification tasks (intent routing, tool selection, memory retrieval, error recovery) with sub-millisecond latency and zero external dependencies. The LLM (Ollama) handles generation tasks (planning, reflection, response synthesis) that require reasoning. This avoids the latency (500ms+ round-trip vs 0.6ms local), cost ($0 for local inference), and reliability issues (network dependency, API outages) of using an LLM for everything. The micro-model layer saves ~74% of LLM calls on synthetic benchmarks.

## Why Local Models Instead of Cloud AI?

- Privacy: all data stays local — no data leaves the machine
- Offline capability: entire system functions without internet
- Latency: sub-10ms classification vs 500ms+ cloud round-trip
- Cost: zero inference cost for micro-models; Ollama runs on consumer hardware
- Control: full model lifecycle management — train, evaluate, promote, rollback

## Why SQLite Instead of PostgreSQL?

- Single-file deployment (no server process to manage)
- Zero configuration for end users
- WAL mode enables concurrent reads + writes without locks
- Sufficient for a local-first desktop application (sub-ms queries at dataset sizes under 100K rows)
- Avoids Docker/PostgreSQL dependency for end users
- Two engine configurations (async + sync) share the same file

## Why Tauri Instead of Electron?

- Binary size: ~5 MB Tauri runtime vs ~150 MB Electron (bundles Chromium)
- Memory: ~55 MB (Tauri) vs ~200 MB (Electron) at idle
- Native performance: Rust backend process manager with direct OS API access
- Smaller attack surface: no Chromium IPC surface
- Tight integration: system tray, native updater, Windows `CREATE_NO_WINDOW` for child processes
- PyInstaller sidecar pattern keeps Python backend separate from Rust shell

## Why No Heavy Agent Framework (LangChain/LangGraph)?

Purpose-built ReAct loop + DAG planner instead of LangChain/LangGraph. Keeps the system transparent — every line of agent logic is in `core/agent.py` and `core/planner.py`. Avoids abstraction debt from framework churn. The agent is ~410 lines, the planner ~800 lines — both independently testable and debuggable without framework-specific knowledge.

## Why Modular Agent Architecture?

- Planner, executor, memory, reflection, and evaluation are independent modules
- Each can be tested, replaced, or upgraded independently
- Enables parallel development across the stack
- Single responsibility principle: Intelligence layer (`core/intelligence.py`) doesn't know about tool execution; tools don't know about LLM providers

## Why Deterministic Execution Layers?

- Planning is deterministic: DAG creation, validation (circular dep detection), dependency-aware execution
- Tool execution has deterministic retry/timeout logic (configurable `max_retries`, `retry_delay_ms`, `timeout_ms`)
- Only LLM calls are non-deterministic
- This makes the system testable: 630+ tests with deterministic outcomes

## Why WebSocket-Based Monitoring Instead of Polling?

- Accurate CPU/process metrics (delta over real interval via ~5Hz push)
- No REST endpoint load from polling — events pushed when available
- Thread-safe snapshot cache decouples collection from serving
- 5Hz push gives smooth UI updates for sparklines and gauges
- Single WebSocket connection carries all event types (agent, system, confirmations)

## Why Micro-Model v2 Pipeline?

- v1: separate training scripts per model, manual evaluation, no versioning
- v2: unified pipeline with `TrainingPipelineV2` class, automatic evaluation, benchmark comparison, versioned artifacts
- 8-9x latency improvement through optimized vectorization (v2 ~0.62ms vs v1 ~5.55ms)
- MLflow integration for experiment tracking
- Auto-promotion gate: never deploys a weaker model than current production

## Why Plugin SDK?

- Extensibility without modifying core — plugins live in `plugins/` directory
- Isolation between plugins (separate namespace, lifecycle)
- Lifecycle management: `initialize()`, `shutdown()`, `register_tool()`, `register_command()`, `register_workflow()`
- Community contributions without merge conflicts in core codebase

## Why In-Process Async Event Bus Instead of Redis?

In-process async pub/sub using `asyncio.Queue` per subscriber for v1. Avoids Redis dependency for a single-process desktop application. The `EventBus` in `core/events.py` supports topic-based subscription, publish, and publish_nowait. Will swap for a real broker (Redis) only if cross-process scaling is ever needed — unlikely for a personal AI OS.

## Why Three-Tier Permission Gating?

Tools are classified as `FREE` (runs silently), `CONFIRM` (emits WebSocket confirmation, blocks until user responds, 120s timeout → auto-deny), or `RESTRICTED` (requires explicit UI approval + per-session reason logged to audit). This granularity avoids confirmation fatigue while maintaining security for destructive operations. Backed by an append-only audit log (`data/audit/audit-YYYY-MM-DD.jsonl`).

## Why Sandbox Roots Instead of Blanket Filesystem Access?

Configurable list of allowed filesystem paths (default: user home + project root). Any path traversal attempt outside these roots is rejected and logged. URL-encoded path characters are decoded before validation. Symlinks are resolved with `resolve(strict=True)`. This prevents the most common class of LLM-triggered security incidents — unintended file read/write outside the workspace.

## Why Command Policy Instead of Full Terminal Access?

The terminal tool uses a static allowlist of read-only commands (`ls`, `cat`, `git status`, `ps`, etc.) classified as `FREE`. Anything else is `CONFIRM` by default. Destructive commands (`rm`, `format`, `shutdown`, `sudo`, `kill -9`) are `RESTRICTED`. Shell metacharacters (`;`, `|`, `&&`, backtick) in any command downgrade it to `CONFIRM` minimum. Input length capped at 4096 characters. The command-safety micro-model replaces this static allowlist with a learned classifier when enabled.

## Why SQLite for Memory Instead of ChromaDB/Vector DB?

Memory is backed entirely by SQLite with keyword + heuristic scoring (importance × 0.4 + usefulness × 0.3 + reliability × 0.3 + recency/recall bonuses). ChromaDB is listed as an optional dependency (`vector` extras) but is not connected in the deployed code. For a local-first desktop application with thousands of memories, SQLite search with intelligent ranking performs adequately (~1.6ms store, sub-ms search) and avoids the operational complexity of a separate vector database.

## Why Two Database Engine Configurations (Async + Sync)?

The agent runtime uses `aiosqlite` async sessions (`sqlite+aiosqlite://`) for non-blocking DB writes during execution. Tools, task manager, memory store, security audit, and training code use synchronous sessions (`sqlite://`). Both share the same `veyron.db` file with WAL mode and 5s busy timeout. This avoids async overhead in code paths that don't need it while keeping the agent loop non-blocking.

## Why Additive Schema Migration Strategy?

No migration tooling. `init_db()` calls `SQLModel.metadata.create_all()` which is a no-op for existing tables. Columns added after initial deployment are created automatically on startup as long as they have nullable defaults. This works because SQLite's `CREATE TABLE IF NOT EXISTS` ignores existing columns, and SQLModel's metadata includes all current columns. Renaming or dropping columns requires manual migration.

## Why Singleton Pattern for All Services?

Every major subsystem (agent, planner, memory store, tool registry, event bus, model registry, confirmation manager, safety policy) follows `get_X()` / `reset_X()` singleton pattern with `threading.Lock`. This provides:
- Lazy initialization on first use
- Thread-safe access from both async and sync code paths
- Clean test isolation via `reset_X()` in `conftest.py`
- No dependency injection framework overhead

## Why 4-Axis Connection State Machine?

The frontend connection indicator was originally a single boolean (`ws.readyState === OPEN`), causing "Connected" to show even when the REST API was failing or the backend process was dead. Replaced with a 4-axis state machine requiring ALL of: backend process running (`backendRunning`), health endpoint responding (`healthOk`), REST API responding (`restOk`), WebSocket connected (`wsConnected`). Each failure produces a specific diagnostic state and reason string. This eliminated the #1 user-facing bug (false "Connected" indicator).

## Why Ed25519 Signing for Updates?

Tauri's built-in update mechanism uses Ed25519 signatures to verify installer integrity before applying updates. The signing key is generated once, the private key stored as a GitHub Actions secret, and the public key embedded in the Tauri binary. Each release generates a `.sig` file and `latest.json` manifest. This prevents supply-chain attacks where a compromised release server could serve malicious installers.

## Why Model Registry Decoupled from Runtime?

The `ModelRegistry` tracks model lifecycle (register → promote → rollback) but inference modules load models by hardcoded path, not through the registry. This is a known gap: the registry exists but is disconnected from runtime. The intent is for inference modules to query `ModelRegistry.get_production()` for the current production model, but this wiring has not been implemented. Future work must connect them to ensure the registry is the source of truth for model versions.

## Why Asyncio.create_task Instead of FastAPI BackgroundTasks?

`POST /api/agent` originally used FastAPI's `BackgroundTasks`, which runs coroutines inside the ASGI `send()` callback. With agent runs taking up to 300 seconds, this could stall the connection handler and prevent the task from ever starting. Replaced with `asyncio.create_task()` — true fire-and-forget. The response returns immediately; the agent runs independently on the event loop.

## Why No Cross-Validation in Training Pipelines?

All pipelines use a single 80/20 stratified split with `seed=42`. No k-fold, no repeated sampling. Variance estimates are impossible. This is a known weakness — the models are evaluated on a single hold-out set, and the V2 benchmark suffers from data leakage (evaluates on training data). Future training pipelines should add 5-fold stratified cross-validation and report mean ± std of all metrics.

## Why Python + React/TypeScript/Vite Instead of Monolithic Framework?

Backend Python 3.11+ with FastAPI provides the async runtime, type-safe models (Pydantic), and ML ecosystem (scikit-learn, numpy). Frontend React + TypeScript + Vite provides a modern component model, type safety across the API boundary, and fast HMR during development. The two communicate through a defined REST + WebSocket contract — no framework lock-in, each side can be independently evolved.

## Why Default Base Model qwen2.5:3b-instruct?

Chosen as the Tier-2 default because it is small enough for consumer GPUs (runs on 4GB VRAM, ~2.5GB RAM), has strong instruction-following capabilities, and supports tool calling natively. Phi-3.5-mini is documented as an alternative. Configurable in Settings via `ModelConfig.base_model`.

## Why TImezone-Aware UTC Storage?

All timestamps stored as timezone-aware UTC in the database; rendered in the frontend using the browser's local timezone. This avoids DST ambiguity, timezone conversion bugs, and makes log analysis consistent across machines.
