# Contributing to Veyron

## Development Setup

### Backend

```bash
# Create a virtual environment (Python 3.11-3.13)
uv venv --python 3.12

# Install all dependencies including dev and ML extras
uv sync
uv pip install -e ".[dev,ml]"

# Copy and edit configuration
cp config.example.yaml config.yaml

# Launch the API server
uv run uvicorn veyron.main:app --reload
# -> http://localhost:8000  (docs at /docs)
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# -> http://localhost:5173 (proxies API to backend)
```

### Desktop (Tauri)

```bash
cd frontend
npm install
npm run tauri:dev
```

For a production desktop build:

```bash
cd frontend/src-tauri
cargo build --release
```

## Branch Strategy

- `main` -- production-ready. All commits on main pass tests, linting, and type checking.
- `feat/*` -- feature branches. Squash-merge into main when complete.
- `fix/*` -- bug fixes. Squash-merge into main.
- `docs/*` -- documentation changes only.
- `refactor/*` -- code restructuring with no functional change.
- `perf/*` -- performance improvements.

Feature branches should be short-lived (ideally less than one week). Rebase onto main before opening a pull request.

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add memory reranker micro-model
fix: handle null bytes in agent request input
refactor: extract safety policy into separate class
docs: add architecture diagram to ARCHITECTURE.md
test: add planner DAG execution tests
chore: update ruff config to 100 char line length
perf: cache tool registry lookups
style: format imports per isort rules
```

Scope is optional but encouraged for larger changes:

```
feat(memory): add importance decay function
fix(planner): handle empty dependency list
refactor(security): extract command classification
```

## Code Style

### Python

Veyron uses [Ruff](https://docs.astral.sh/ruff) for linting and formatting, configured in `pyproject.toml`:

- Line length: 100
- Target version: py311
- Lint rules: E, F, I, UP, B, SIM

```bash
# Check all Python code
ruff check backend/ tests/ benchmarks/

# Auto-fix violations
ruff check --fix backend/ tests/ benchmarks/
```

Follow PEP 8 conventions. Use type annotations for all public functions and methods. Prefer `pathlib` over `os.path`. Use `async/await` for I/O-bound operations.

### TypeScript / JavaScript

Formatting is handled by [Prettier](https://prettier.io/) with the project's `.prettierrc` configuration.

```bash
cd frontend
npm run format
npm run typecheck
```

Follow the project's `tsconfig.json` strict mode settings. Use TypeScript types for all exports. Avoid `any` unless absolutely necessary.

### Rust

Rust code in the Tauri shell follows standard conventions:

```bash
cd frontend/src-tauri
cargo fmt --check
cargo clippy -- -D warnings
```

Use `cargo fmt` before committing. Clippy warnings must be resolved.

## Testing Requirements

All tests must pass before merging. The project has 880+ tests across three categories.

### Running Tests

```bash
# Run all tests
uv run pytest -q

# Run specific categories
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/benchmarks/

# Run a single test file with verbose output
uv run pytest tests/unit/test_planner.py -v

# Run with coverage
uv run pytest --cov=backend/veyron --cov-report=term-missing
```

### Test Conventions

- Tests live in `tests/unit/`, `tests/integration/`, or `tests/benchmarks/`.
- Test files are named `test_<module>.py`.
- `pytest-asyncio` is enabled in auto mode (configured in `pyproject.toml`).
- The `conftest.py` provides these fixtures:
  - `isolated_data_dir` (autouse) -- redirects `backend/data` to a temp directory.
  - `sandbox_root` -- a writable temp directory used as the only sandbox root.
  - `settings_with_sandbox` (autouse) -- forces sandbox roots to only the temp root.
  - `reset_singletons` (autouse) -- resets all process-wide singletons between tests.
  - `fresh_db` -- initializes an isolated SQLite database.
  - `StubProvider` -- a fake LLM provider for deterministic agent tests.
- All database state is isolated per test.
- Agent tests should use `StubProvider` to avoid real LLM calls.
- Tool tests should use `sandbox_root` as the only allowed path.
- Security tests should monkeypatch settings to change approval mode or risk thresholds.

### Writing Tests

```python
import pytest
from veyron.some_module import SomeClass


class TestSomeFeature:
    async def test_happy_path(self, fresh_db):
        instance = SomeClass()
        result = await instance.method()
        assert result.ok

    def test_error_case(self):
        ...
```

## Pull Request Process

1. Create a branch from `main` following the naming convention.
2. Make your changes with atomic commits following conventional commit format.
3. Run the full test suite and linting locally.
4. Push your branch and open a pull request against `main`.
5. Ensure CI passes (lint, type check, tests, coverage).
6. Request review from at least one maintainer.
7. Address all review feedback. Each round of changes should be pushed as fixup commits.
8. Once approved, squash-merge into main. The merge commit message should be the PR title.
9. Delete the feature branch after merge.

## How To

### Add a Tool

1. Create a file in `backend/veyron/tools/`, e.g. `my_tool.py`.
2. Subclass `Tool` from `veyron.tools.base`:

```python
from typing import Any
from pydantic import BaseModel, Field
from veyron.tools.base import Tool, ToolContext, ToolResult
from veyron.security.command_policy import PermissionLevel


class MyInputs(BaseModel):
    query: str = Field(..., description="The search query")


class MyTool(Tool):
    name = "my_tool"
    description = "Does something useful"
    permission = PermissionLevel.FREE
    inputs_schema = MyInputs

    async def run(self, ctx: ToolContext, **inputs: Any) -> ToolResult:
        query = inputs["query"]
        # Do work...
        return ToolResult(output="result text", data={"key": "value"})
```

3. The tool is auto-discovered by `ToolRegistry` on import. No manual registration required.
4. Write tests in `tests/unit/test_my_tool.py`.
5. Add the tool to the API endpoint listing in `api/routes/tools.py` if it should be listed in the UI.

### Add a Workflow

1. Define a `WorkflowDefinition` with a list of `WorkflowStep`:

```python
from veyron.workflow.models import WorkflowDefinition, WorkflowStep, StepType
from veyron.workflow.registry import WorkflowRegistry

steps = [
    WorkflowStep(
        step_type=StepType.TOOL_CALL,
        name="check_disk",
        tool_name="system_monitor",
        params={"operation": "disk"},
    ),
    WorkflowStep(
        step_type=StepType.CONDITION,
        name="alert_if_full",
        condition="$disk_usage > 90",
        tool_name="terminal",
        params={"command": 'echo "Disk almost full"'},
    ),
]

wf = WorkflowDefinition(name="disk_check", steps=steps)
registry = WorkflowRegistry()
wf_id = registry.save(wf)
```

2. Execute via `WorkflowEngine`:

```python
from veyron.workflow.engine import WorkflowEngine

engine = WorkflowEngine()
result = await engine.execute(wf, variables={"disk_usage": 85})
```

3. Workflows support variable templates (`$var_name`), retry policies, conditions, and failure policies (abort / skip / ignore).

### Add a Plugin

1. Create a directory under `plugins/`:

```
plugins/
└── my_plugin/
    ├── __init__.py
    └── ...
```

2. Subclass `PluginBase` from `veyron.plugin.sdk`:

```python
from veyron.plugin.sdk import PluginBase, PluginManifest
from veyron.tools.base import Tool


class MyTool(Tool):
    name = "my_plugin_tool"
    ...


class MyPlugin(PluginBase):
    manifest = PluginManifest(
        name="my_plugin",
        version="1.0.0",
        description="Example plugin",
        author="You",
    )

    async def initialize(self) -> bool:
        self.register_tool(MyTool)
        return True


plugin = MyPlugin()
```

3. The plugin is auto-discovered by `PluginRegistry` from the `plugins/` directory.
4. Plugins can register tools, commands, and custom workflows.
5. Write tests in `tests/unit/test_my_plugin.py`.

### Add a Micro-Model

1. Create a new package under `backend/veyron/intelligence/`, e.g. `my_model/`.
2. Implement the following files:
   - `schema.py` -- input/output dataclasses.
   - `dataset.py` -- dataset generation or loading.
   - `model.py` -- scikit-learn Pipeline definition.
   - `trainer.py` -- training function that returns metrics and the trained model.
   - `inference.py` -- inference function (`predict()`).
3. Add training to `run_training.py`: call the trainer and log metrics to MLflow.
4. Add inference to the appropriate place in `core/` or `intelligence/`.
5. Register the model type in `intelligence/models/registry.py`.
6. Write tests in `tests/unit/test_my_model.py`.
7. Add any new configuration options to `config.example.yaml`.

### Add a New Model Type to the Registry

Models are registered automatically by the training pipeline. To register manually:

```python
from veyron.intelligence.models.registry import ModelRegistry
from veyron.intelligence.models.schema import ModelMetadata

registry = ModelRegistry()
registry.register(ModelMetadata(
    name="intent_classifier",
    version="v2.0.0-20260717_114439",
    model_type="intent_classifier",
    metrics={"macro_f1": 0.9727},
    path="/path/to/model.pkl",
    status="candidate",
))
registry.promote("intent_classifier", "v2.0.0-20260717_114439")
```

The promotion gate requires a new model to exceed the current production score by a configurable threshold (default: +0.01 on the primary metric).

## Code Review Expectations

- Every PR must be reviewed by at least one maintainer.
- The reviewer verifies:
  - Changes match the PR description and scope.
  - Tests cover the new code, or the PR explains why not.
  - No debugging artifacts, commented-out code, or print statements remain.
  - Public APIs are typed (Python type annotations or TypeScript types) and documented.
  - Security implications are considered, especially for tool and API route changes.
  - No secrets, keys, or credentials are committed.
  - The branch is rebased on the latest `main`.
- The author merges after approval. No self-approvals.
- For urgent fixes, a single maintainer review is sufficient. For architectural changes, two reviews are required.

## CI Expectations

Before submitting a PR, ensure:

1. `ruff check backend/ tests/ benchmarks/` passes with zero violations.
2. `uv run pytest -q` passes.
3. For frontend changes: `cd frontend && npm run typecheck` passes.
4. For desktop changes: `cd frontend/src-tauri && cargo build` succeeds.
5. New features include tests with reasonable coverage.
6. New public APIs include type annotations.
7. No secrets, keys, or credentials are committed.

## Documentation

When you add a new feature:

1. Update the relevant section in `README.md` (features, quick start, project structure).
2. Update `docs/ARCHITECTURE.md` with implementation details.
3. Add how-to instructions to this file if the feature introduces a new extension point.
4. Update `CHANGELOG.md` with a summary of the change.
5. If configuration is affected, update `config.example.yaml` and the configuration section of `README.md`.

Documentation files and their purpose:

| File | Purpose |
|------|---------|
| `README.md` | User-facing overview, quick start, feature list |
| `docs/ARCHITECTURE.md` | Deep implementation reference for engineers |
| `CONTRIBUTING.md` | This file -- developer setup, conventions, how-to guides |
| `docs/DESIGN_DECISIONS.md` | Design decisions and rationale |
| `CHANGELOG.md` | Notable changes per release |
| `docs/TROUBLESHOOTING.md` | Common issues and resolutions |
