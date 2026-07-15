# Contributing

## Development Setup

See [BUILD.md](BUILD.md) for full build instructions.

## Code Style

- **Python**: Follow Ruff defaults (reformatter + lint). Run `ruff check .` before committing.
- **TypeScript**: Follow project's tsconfig strict mode.
- **Rust**: Follow `cargo fmt` style.

## Commit Messages

Use conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.

## Before Submitting

1. Run `uv run pytest -q` — all tests must pass (known pre-existing failures OK)
2. Run `ruff check backend/ tests/ benchmarks/`
3. For frontend changes: `cd frontend && npm run typecheck`
4. For desktop changes: `cd frontend/src-tauri && cargo build`

## Reporting Issues

Open a GitHub issue with:
- Steps to reproduce
- Expected vs actual behavior
- Logs from `backend/data/logs/` (if applicable)
