# Veyron

> A modular autonomous operating layer combining deterministic planning, memory retrieval, local intelligence models, and controlled tool execution.

## Overview

Veyron is a local-first agent runtime that combines a ReAct AI core with sandboxed tool execution, hybrid memory, micro-model intelligence, and a desktop user interface. It operates as an intelligent layer between users and their systems — understanding requests, planning multi-step work, executing tools under security policies, and learning from every interaction.

The system exists to provide a professional-grade, private, local AI operating layer that does not rely on cloud services. By running entirely offline via Ollama and local micro-models, Veyron ensures data sovereignty while still delivering autonomous task execution with planning, memory, and security.

Veyron solves the problem of autonomous task execution on local systems with enterprise-grade security, persistent memory, and adaptive planning. It decomposes complex goals into DAG-based execution plans, routes sub-tasks through sandboxed tools gated by security policies, reflects on outcomes to improve future performance, and continuously retrains its micro-models through an active learning pipeline.

## Features

- Autonomous task execution from natural language goals
- DAG-based planning engine with adaptive re-planning
- Hybrid memory system (keyword + importance + recency)
- 5 local intelligence micro-models (intent, tool selection, planning, memory retrieval, error recovery)
- Sandboxed tool execution with security policies
- Real-time desktop application (React + Tauri)
- WebSocket-based live monitoring
- Plugin SDK for extensibility
- Workflow engine for reusable automation
- Comprehensive test suite (880+ tests)

## Architecture

```mermaid
flowchart TB
    User --> UI[React + Tauri Desktop]
    UI --> API[FastAPI Backend]
    API --> Agent[Agent Runtime]
    Agent --> Planner
    Agent --> TaskMgr[Task Manager]
    Agent --> Memory[Memory System]
    Agent --> Tools[Tool Execution]
    Agent --> Eval[Evaluator]
    Agent --> Reflect[Reflection Engine]
    Agent --> AI[AI Models]
    AI --> Intent[Intent Router]
    AI --> ToolSel[Tool Selector]
    AI --> PlanModel[Planning Model]
    AI --> MemRet[Memory Retrieval]
    AI --> ErrRec[Error Recovery]
```

## Quick Start

### System Requirements
- Python 3.11-3.13
- Node.js 18+
- Rust (optional, for Tauri desktop build)
- Ollama (recommended for local LLM)

### Development Setup

```bash
# Backend
uv sync
cp config.example.yaml config.yaml
# Edit config.yaml with your settings
uv run uvicorn veyron.main:app --reload

# Frontend (browser only)
cd frontend
npm install
npm run dev

# Desktop (Tauri)
npm run tauri:dev
```

### Production Build
See [BUILD.md](BUILD.md) and [INSTALLATION.md](docs/INSTALLATION.md).

## Configuration

See [config.example.yaml](config.example.yaml) for all options.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Installation](docs/INSTALLATION.md)
- [Building](BUILD.md)
- [Contributing](CONTRIBUTING.md)
- [Testing](docs/TESTING.md)
- [AI Models](docs/AI_MODELS.md)
- [Design Decisions](docs/DESIGN_DECISIONS.md)
- [Development History](docs/DEVELOPMENT_HISTORY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [API Reference](docs/ARCHITECTURE.md#api)

## Project Status

Veyron v1.0.0 -- Production-ready. Active development continues.

## License

MIT License -- see [LICENSE](LICENSE).
