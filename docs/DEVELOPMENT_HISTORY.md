# Development History

Complete chronological evolution of Veyron (originally PAIos), an AI productivity system.
Originally built by GLM-5-Turbo under autonomous directive, continued by DeepSeek-V4-Flash.

---

## Phase 0: Foundation (2026-07-10)

**Goal:** Bootstrap the project skeleton with dependency management, configuration, database schema, and API scaffold.

**Deliverables:**
- Repository initialization with `.gitignore`
- Dependency manifests (`pyproject.toml` with uv, `package.json` with npm)
- Configuration system via Pydantic `BaseSettings` reading `.env` + `config.yaml`
- SQLite + SQLModel database schema (Tables: `task`, `memory`, `audit_event`, `tool_invocation`)
- FastAPI skeleton with health check endpoint
- Event bus: in-process async pub/sub (`asyncio.Queue` per subscriber)
- Initial security layer: path policy, command policy (static allowlist), audit log, confirmation manager

**Key decisions:** Local web app (no desktop wrapper), hybrid model strategy (micro-models + Ollama), no heavy agent frameworks, Python 3.11+ backend, SQLite via SQLAlchemy+SQLModel.

**Test count:** Phase foundation tests passing

---

## Phase 1: Backend Architecture (2026-07-11)

**Goal:** Working agent loop that can receive a request, reason, call real tools, and return real answers — all under security controls.

**Deliverables:**
- Tool system: `Tool` ABC, `ToolRegistry` with auto-discovery, `PermissionLevel` enum
- Three tools: `filesystem_read` (FREE), `system_monitor` (FREE), `terminal` (CONFIRM)
- Security layer: path validation (symlink-aware, sandbox roots), command classification (allowlist/denylist/metachar detection), append-only audit logging
- LLM provider interface (`LLMProvider` ABC) + Ollama integration over HTTP with streaming
- Heuristic intent router (Simple/Complex/domain classification)
- ReAct agent loop wired to `POST /api/agent`, streaming events over WebSocket
- API layer: routes for agent, system, tools, and WebSocket event subscription
- 51 tests

**Exit demo:** "Show my CPU usage" returns real CPU stats; "List files in sandbox" returns real listing; CONFIRM-gated command triggers WebSocket confirmation round-trip.

**Test count:** 51

---

## Phase 2: Agent Runtime (2026-07-11)

**Goal:** Multi-step planning, persistent memory, project understanding, first micro-models.

**Deliverables:**
- DAG planner: LLM-generated step decomposition, validation (circular dep detection via DFS, unknown step refs), dependency-aware parallel execution via `asyncio.gather`
- Step verifier: LLM-based PASS/FAIL verification with retry cap (2 re-plans per step)
- Hybrid memory system: SQLite-backed CRUD, keyword + importance + recency ranking, context injection
- Task manager: lifecycle state machine (CREATED → RUNNING → COMPLETED/FAILED/CANCELLED), persistence, history
- Project analyzer tool: technology detection (20+ categories), dependency parsing, issue detection, recommendations
- Intent classifier micro-model: 10-category taxonomy, 2000-example dataset, TF-IDF + LogisticRegression, 98.3% accuracy, macro_f1=0.982
- Tool selector micro-model: 4 tools, 500-example dataset, precision@1=0.970, recall@3=0.990

**Test count:** 165

---

## Phase 3: Planning Engine & Production Hardening (2026-07-12)

**Goal:** Production-grade planning with observability, persistence, and tool reliability.

**Deliverables:**
- Execution tracker (`ExecutionTracker`): records every LLM call, tool call, and plan step with timing, status, retries. Exposed via `GET /api/agent/{id}/timeline`
- Persistent agent state: checkpoint/resume via `checkpoint_data` on `Task` model. Failed tasks resume via `POST /api/agent/{id}/resume`
- Tool reliability layer: `FailureCategory` enum, `classify_failure()`, retry loop with `asyncio.wait_for` timeout, `max_retries`/`retry_delay_ms`/`timeout_ms` class vars
- Advanced planning: DFS circular dependency detection, topological sort, `asyncio.gather` for parallel step execution
- Cancellation API (`POST /api/agent/{id}/cancel`)
- 165 tests

**Test count:** 165

---

## Phase 4-5: Memory & Security (2026-07-12)

**Goal:** Risk-based safety layer, persistent memory with lifecycle, evaluation framework, agent reflection.

**Deliverables:**
- Safety/permission system: `RiskLevel` (LOW/MEDIUM/HIGH/CRITICAL), `ApprovalMode` (AUTONOMOUS/CONFIRM/SAFE), `SafetyPolicy` with configurable thresholds. 32 tests
- Memory CRUD, text search, context injection, `build_context()` for system prompts. 23 tests
- Evaluation framework: `EvalTask`, `EvalResult`, `Evaluator.run_suite()`, DB persistence via `EvaluationMetric` table. 16 tests
- Memory lifecycle: exponential decay (`I' = I * 0.5^(days/30)`), SHA-256 duplicate detection, merge via `SequenceMatcher` ratio >= 0.75, quality scoring (usefulness × 0.4 + reliability × 0.3 + success_frequency × 0.3)
- Agent reflection: `ReflectionEngine` with LLM-based post-task analysis, stores learnings as `REFLECTION` category memories
- Plan quality scoring (`PlanScore`: step_count_score × 0.3 + dependency_score × 0.3 + tool_coverage_score × 0.4)
- Adaptive replanning: regenerates plan when >50% steps fail, incorporating failure context
- 324 tests

**Test count:** 324

---

## Phase 6: Real-World Validation (2026-07-12)

**Goal:** Real agent benchmark suite, adversarial testing, performance baselines, reliability targets.

**Deliverables:**
- 13 real agent benchmark tasks across basic (5), intermediate (4), and advanced (4) categories
- 34 adversarial tests: path traversal (6), shell metachar (6), safety policy critical denial (2), circular dependencies (4), invalid JSON (3), malformed inputs (2), memory overload/contradictory/empty/negative (9), agent edge cases (8)
- Performance baselines: `benchmarks/perf.py` measures security, memory, planner operations with min/avg/median/P99/max
- Reliability targets documented in `RELIABILITY.md`: >95% pass rate, safety bypass prohibition, graceful recovery, deterministic behavior

**Test count:** 324 (290 + 34 adversarial)

---

## Phase 7-8: Productization (2026-07-13)

**Goal:** Structured verifier, full task management, dashboard API, WebSocket hardening, frontend preparation.

**Deliverables:**
- Structured verifier: `VerifierAction` enum (COMPLETE/RETRY/REPLAN/HUMAN_REVIEW), `VerifierResult` dataclass with confidence, issues, evidence
- Full task management API: pause (`POST /api/agent/{id}/pause`), resume (`POST /api/agent/{id}/resume`), delete (`DELETE /api/agent/{id}`), filterable listing
- Dashboard API: `GET /api/dashboard` returns task counts, recent tasks, system overview
- WebSocket subscribe/unsubscribe with topic-based forwarding, duplicate detection
- Event system hardening: 4 missing event types added (`task.created`, `task.started`, `task.completed`, `task.failed`, `plan.start`)
- Concurrency hardening: 10 fixes across 9 files — EventBus subscriber snapshots under lock, agent background task tracking, planner `_plan_lock`, thread-safe singletons, WAL + 5s busy timeout + pool_pre_ping
- Security audit: path policy symlink fix, command policy whitespace/length cap, terminal env sanitization, confirmation max-pending (100), memory content validation
- 438 tests

**Test count:** 438

---

## Phase 9: Intelligence Layer (2026-07-13 to 2026-07-14)

**Goal:** Complete micro-model training pipeline with v2 models, benchmarks, and runtime integration.

**Sub-phases:**

### Phase 9.1 — Training Data Pipeline
- `TrainingDataCollector`: queries completed/failed tasks from DB, computes quality scores
- `TrainingExample` dataclass with SHA-256 dedup, `TrainingDataset` with filter/split/group operations
- `QualityScorer`: composite 0.0–1.0 score based on completion (35%), efficiency (25%), tool diversity (15%), duration reasonableness (15%), retry penalty (10%)
- `TrainingExporter`: JSONL file export with train/test split support
- 30 new tests

### Phase 9.2 — Dataset Preparation
- `DatasetValidator`: validates intents against 10-category taxonomy, checks tools against registry, detects duplicates, produces `ValidationReport`
- `DatasetSplitter`: stratified 80/20 split preserving category distribution
- `DatasetFormatter`: exports for 4 training tasks (intent classification, tool selection, parameter generation, planner training)
- 24 new tests

### Phase 9.3 — V2 Training Pipeline
- `IntentEvaluator`: full intent classification metrics (accuracy, macro precision/recall/F1, confusion matrix, calibration buckets, common mistakes)
- `ToolSelectorEvaluator`: precision@k, recall@k, F1@k, exact match rate, per-tool metrics
- `ModelComparison`: delta comparison between two model versions
- `TrainingPipelineV2`: unified training with timestamped model files, evaluation reports, versioning
- `BenchmarkV2`: v2 vs v1 vs heuristic comparison on intent accuracy, tool selection precision/recall, latency, LLM call avoidance
- 24 new tests

### Phase 9.4 — Runtime Integration
- Training pipeline executed on 5000 synthetic examples: intent classifier accuracy=99.8%, macro_f1=0.9969; tool selector precision@1=0.9602
- Runtime integration: `classify_request()` runs tool selector inference alongside intent classifier
- Tool selector inference API: `predict_tools()` and `predict_tool_names()` with lazy-loading singleton
- Benchmark: v2 avg latency 0.622ms (vs v1 5.545ms — 8-9x improvement); LLM calls avoided 73.7%
- Parameter extraction prep: schema, dataset, evaluation scaffold
- 38 new tests

**Test count:** 554

---

## Phase 10: Autonomous Improvement (2026-07-14)

**Goal:** Veyron learns from its own usage — model registry, feedback loop, retraining orchestrator, intelligence metrics.

**Deliverables:**
- `ModelRegistry`: lifecycle management (register, promote to production, rollback), JSON-persisted registry file, thread-safe singleton
- `TrainingFeedbackLoop`: converts completed/failed tasks into high-quality training datasets with success filtering, quality-threshold gating, SHA-256 dedup, automatic intent labeling
- `UserInteraction` dataset: daily JSONL files capturing request, intent, tools, parameters, result, quality score
- `RetrainingOrchestrator`: coordinates full retraining cycle — dataset growth detection, candidate training, benchmark comparison, auto-promotion guard (never deploy weaker)
- Intelligence dashboard backend: `GET /api/intelligence/metrics` exposing model status, latency, dataset sizes
- 54 new tests

**Test count:** 608

---

## Phase 11: Intelligence Integration (2026-07-15)

**Goal:** Close the autonomous improvement loop — parameter extraction model, automatic interaction capture, background retraining scheduler.

**Deliverables:**
- `ParameterExtractionModel`: TF-IDF + per-parameter LogisticRegression classifiers across 4 tools, 25 classifiers total
- `ParameterExtractionTrainer`: training pipeline with per-tool/per-parameter evaluation
- `ParameterExtractionInference`: `predict_parameters()` and `predict_parameters_multitool()` with lazy-loading singleton
- Agent integration: `_save_interaction()` fires after every `_complete()`/`_fail()` in both ReAct and Planner modes
- `IntelligenceScheduler`: background retraining loop with configurable interval (default 300s), dataset growth detection, subprocess training via `asyncio.create_subprocess_exec`
- Registry extended to support `parameter_extraction` model type
- 22 new tests

**Test count:** 630

---

## Phase 12-14: Learning & Automation (2026-07-15)

**Goal:** Continuous improvement from real user interactions — reflection, memory upgrades, skill detection, workflow engine, plugin SDK, learning dashboard.

**Deliverables:**
- Enhanced reflection engine: confidence scoring, planning quality, tool selection quality, parameter quality, memory usefulness scoring. Persisted to DB with retrieval and aggregate statistics
- Long-term memory upgrades: importance scoring, enhanced merge engine (SequenceMatcher >= 0.75), memory summarization, user profile generation (preferences, frequent actions, common tools, known projects, skill patterns), decay/pruning with configurable half-life
- Skill learning system: automatic detection of repeated workflow patterns from user history via `SkillDetector`
- Workflow engine: reusable definitions with `$variable` template substitution, condition expressions, retry/failure policies (abort/skip/ignore). Persisted to `Workflow` + `WorkflowStepModel` tables
- Plugin SDK: `PluginBase` ABC with lifecycle (initialize, shutdown, register_tool, register_command, register_workflow), `PluginRegistry` with directory-based and single-file discovery, example plugin
- Learning Dashboard: 11 read-only API endpoints exposing reflection, skill, workflow, benchmark, model, and event data + React frontend with 6 stat cards and 6 tabbed data views
- 5 benchmark test suites: reflection quality, memory quality, workflow prediction, skill detection, learning progress
- 9 new SQLModel tables: ReflectionRecord, Workflow, WorkflowStepModel, Skill, PluginRegistration, LearningEvent, BenchmarkRun, ModelVersion
- 252 new tests

**Test count:** 882

---

## Phase 15: Desktop Packaging (2026-07-16 to 2026-07-17)

**Goal:** Package Veyron as a native desktop application using Tauri v2.

**Deliverables:**
- Tauri v2 desktop shell with WebView2-based rendering
- System tray icon with "Restart AI Engine" and "Quit" commands
- Backend process manager: spawns PyInstaller sidecar (veyron-backend.exe), monitors health, restarts on failure
- Auto-updater: Tauri plugin configured with Ed25519-signed update manifests
- PyInstaller sidecar builder: `build_backend.py` compiles Python backend to single .exe with 40+ hidden imports
- Installer: NSIS (`Veyron_1.0.0_x64-setup.exe`, ~161 MB) and MSI (`Veyron_1.0.0_x64_en-US.msi`, ~163 MB)
- Data separation: runtime data stored in `%APPDATA%/Veyron/`
- Backend process lifecycle: window close handler, `RunEvent::Exit` handler, `Drop` impl for `BackendLauncher`, 2s graceful shutdown + force-kill fallback

**Test count:** 882 (no new tests — packaging)

---

## Phase 16-19: Production Hardening (2026-07-17 to 2026-07-18)

**Goal:** Full production audit, fix all release-blocking bugs, stabilize the runtime.

### Phase 16 — Production Audit (2026-07-17)
- 9 critical, 7 major, 12 minor bugs discovered
- Critical fixes: logger backend (env_logger), Mutex held 30s during startup, restart_backend blocking async runtime, PID tracking after process crash, CORS middleware ordering, 9+ missing PyInstaller hidden imports, event listener leak in TauriBridge, backend wait loop timeout silent fallthrough, useEffect handler dependency

### Phase 17 — Runtime Root Cause (2026-07-17)
- Root cause: `__TAURI__` global variable not available in Tauri v2 by default
- 3 frontend files used `'__TAURI__' in window` causing false negatives in Tauri detection
- Fixed: replaced with `'__TAURI_INTERNALS__' in window` (always present) + added `withGlobalTauri: true` in `tauri.conf.json`
- Three failures traced to same root: dashboard showing HTML instead of JSON, Tasks page crash, persistent "Offline" indicator

### Phase 18 — Stabilization (2026-07-18)
- Bug 1: `TypeError: t is not iterable` — module-scope `__TAURI__` check + silent `catch {}` swallowing JSON parse errors
- Bug 2: Agent creates task but never executes — `BackgroundTasks` blocking ASGI send callback (replaced with `asyncio.create_task`)
- Bug 3: Serialization crash with None progress values — defensive `getattr` checks and `_safe_int` fallbacks
- Bug 4: WebSocket/CORS for Tauri desktop (fixed in previous session)
- Bug 5: Rust missing Manager import (fixed in previous session)
- Validation: 690 tests pass, TypeScript clean, Vite/Rust/PyInstaller builds succeed

### Phase 19 — Release Pipeline & Startup Architecture (2026-07-18)
- GitHub Actions CI/CD workflow (`release.yml`): tag-triggered, builds backend + frontend + Tauri installer, signs with Ed25519, uploads artifacts to GitHub Release
- Startup hardening: blank console window fix (CREATE_NO_WINDOW + --noconsole), 4-axis connection state machine replacing single boolean, removed 2s hardcoded sleep, backoff-based health polling
- Diagnostics page: live connection state, backend PID, latency, request history, environment info
- Update system hardening: Ed25519 signing, `latest.json` manifest, signing key recovery procedure

**Test count:** 882

---

## Phase 15 (Redux): High-Performance Monitoring (2026-07-18)

**Goal:** Real-time system monitoring with background collectors and WebSocket push.

**Deliverables:**
- Background monitoring service with continuous collectors
- 5Hz WebSocket snapshot push (CPU, processes, memory, disk, network, temps, GPU)
- Thread-safe snapshot cache decoupling collection from serving
- 7 collectors running on independent intervals
- Dashboard sparkline rendering from cached snapshot data
- Zero REST calls for real-time monitoring — all data pushed via WebSocket

**Test count:** 882 (no change — monitoring is additive)

---

## v1.0.0 Release Engineering (2026-07-18)

**Goal:** Finalize v1.0.0 release — repository cleanup, documentation, installer verification.

**Deliverables:**
- Repository cleanup: artifact removal, file reorganization
- Complete documentation overhaul: ARCHITECTURE.md, README.md, CONTRIBUTING.md, CHANGELOG.md, BUILD.md, docs/ with AI_MODELS.md, TESTING.md, TROUBLESHOOTING.md
- Release verdict: 22 release checks all PASS — PRODUCTION-READY
- Final release artifacts: `Veyron_1.0.0_x64-setup.exe` (160.8 MB), `Veyron_1.0.0_x64_en-US.msi` (162.7 MB)
- Build artifacts: Tauri executable (16.6 MB), backend sidecar (170.8 MB)
- Resource profile: idle ~145 MB RAM (combined), active ~185 MB (excluding Ollama at ~2.5 GB)
- 30-minute stability test: no memory leak, no thread growth, no WebSocket drops
- Known issues (all acceptable for 1.0.0): port conflict (low), Ollama absence not detected at startup (low), no release server for auto-updates (low), WS reconnection loss (low)

**Test count:** 882 (all passing), TypeScript clean, Rust clean, all builds successful

---

## Post-Release: Agent Evaluation & Continuous Learning (2026-07-18)

**Goal:** Establish regression baseline, formalize evaluation pipeline for ongoing agent improvements.

**Deliverables:**
- Benchmark dataset: 112 tasks across 12 categories (`BENCHMARK_DATASET.json`)
- Evaluation engine: `evaluator_v2.py` with agent, planner, memory, tool, and latency metrics
- Regression detection: `regression.py` with configurable thresholds and severity levels (info/warning/critical)
- Baseline v1.0.0: initial benchmark run establishing reference metrics
- Reporting: structured JSON + human-readable Markdown reports per run
- Continuous learning: dataset growth detection, auto-retraining trigger, promotion guard

**Test count:** 882 + benchmark suite

---

## Summary Statistics (as of v1.0.0)

| Metric | Value |
|--------|-------|
| Total test count | 882 passing (1 skipped: Windows symlink) |
| Python source files | ~100+ |
| Total Python lines | ~15,000+ |
| Trained models | 7 (intent router, intent classifier v1/v2, tool selector v2, error recovery, memory retrieval, parameter extraction) |
| Total synthetic training data | ~20,000 examples across all models |
| Real user interactions captured | ~87 |
| Backend-to-synthetic data ratio | 0.87% |
| Installer size (NSIS) | 160.8 MB |
| Idle RAM (combined, no Ollama) | ~145 MB |
| Active RAM (combined, no Ollama) | ~185 MB |
| Build time (full CI pipeline) | ~15 minutes |
| Development duration | 9 days (2026-07-10 to 2026-07-18) |
