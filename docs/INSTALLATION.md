# Veyron — Installation Guide

**Veyron** is a local-first AI productivity system with memory, tools, micro-model intelligence, and a mission-control desktop UI.

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10/11 | Windows 10/11 |
| CPU | x86_64, 4 cores | x86_64, 8 cores |
| RAM | 8 GB | 16 GB |
| Disk | 2 GB free | 10 GB free |
| Python | 3.11–3.13 (for source install) | 3.12 |
| Node.js | 18+ (for development) | 20 LTS |
| Rust | 1.77+ (for Tauri build, optional) | stable |
| WebView2 | Built into Windows 10+ | — |

**Other platforms (experimental):** Linux and macOS are architecture-ready but not officially supported. Desktop installer is Windows-only.

---

## Installation Options

1. **Desktop Installer (Windows)** — Download the `.exe` setup from GitHub Releases, run the installer, and launch from the Start Menu. Backend + frontend + Tauri shell are bundled into a single install. No Python/Node/Rust required.
2. **From Source** — Full development setup. Requires Python, Node.js, and optionally Rust for the Tauri desktop build.

---

## Desktop Installer Setup (Windows)

1. Download `Veyron_x64-setup.exe` from the [GitHub Releases](https://github.com/hichemuuus/Veyron/releases) page.
2. Run the installer (no admin rights required). It installs to `%LOCALAPPDATA%\Veyron`.
3. Launch **Veyron** from the Start Menu or desktop shortcut.
4. The backend starts automatically — a tray icon indicates backend status.
5. The desktop window opens to the Dashboard.

### First Launch Configuration

1. Open the **Settings** page (gear icon in the sidebar).
2. Under **LLM Provider**, select **Ollama** (recommended) or an OpenAI-compatible remote provider.
3. Set the **Ollama Host** (default: `http://localhost:11434`).
4. Select a **Model** (default: `qwen2.5:3b-instruct`).
5. Click **Save** — the backend will verify the connection.

### Ollama Setup

1. Download and install Ollama from [https://ollama.com](https://ollama.com).
2. Open a terminal and pull a model:
   ```bash
   ollama pull qwen2.5:3b-instruct
   ```
3. Verify the model is available:
   ```bash
   ollama list
   ```
4. Keep Ollama running in the background (it auto-starts on login by default).
5. Veyron will connect to Ollama automatically.

---

## Development Setup (From Source)

### Prerequisites

Ensure the following are installed on your system:
- **Python 3.11–3.13** — [python.org](https://python.org)
- **uv** — `pip install uv` or [docs.astral.sh/uv](https://docs.astral.sh/uv)
- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **Rust 1.77+** (only needed for Tauri desktop build) — [rustup.rs](https://rustup.rs)

### Step 1: Clone the Repository

```bash
git clone https://github.com/hichemuuus/Veyron.git
cd Veyron
```

### Step 2: Python Backend Setup

```bash
# Create virtual environment and install dependencies
uv sync

# Install dev dependencies (testing, linting)
uv sync --group dev

# Install ML dependencies (micro-models)
uv sync --extra ml
```

### Step 3: Frontend Setup

```bash
cd frontend
npm install
```

### Step 4: Configuration

```bash
# Copy the example config (edit as needed)
cp config.example.yaml config.yaml

# Optional: create .env for environment variable overrides
```

Default settings in `config.yaml`:
- Ollama URL: `http://localhost:11434`
- Base model: `qwen2.5:3b-instruct`
- Server host: `127.0.0.1`, port: `8000`

### Step 5: Run in Development Mode

```bash
# From the frontend/ directory
cd frontend
npm run tauri:dev
```

This starts:
- Vite dev server on `http://localhost:5173`
- Tauri desktop window (loads from Vite dev server)
- Backend as a Tauri sidecar process

### Run Backend Standalone (without Tauri)

```bash
# From the project root
uv run uvicorn veyron.main:app --reload --port 8000
```

The frontend can then be accessed separately:
```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

### Build for Production

```bash
# 1. Build the Python backend sidecar (PyInstaller)
python scripts/build_backend.py

# 2. Build the Tauri desktop installer
cd frontend
npm run tauri:build
```

Output: `frontend/src-tauri/target/release/bundle/nsis/Veyron_x64-setup.exe`

---

## Common Errors & Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| Backend fails to start | Port conflict, missing dependencies, or config error | Check `%APPDATA%\Veyron\logs\veyron.log` or `backend/data/logs/veyron.log`. Run `uvicorn veyron.main:app` manually to see errors. |
| Port 8000 in use | Another process is using port 8000 | Kill the conflicting process or change `server.port` in `config.yaml`. |
| Ollama connection refused | Ollama is not running or URL is wrong | Ensure Ollama is running (`ollama serve`). Verify `ollama_url` in config. Default: `http://localhost:11434`. |
| Frontend can't connect to backend | Backend not started, CORS misconfiguration, or Tauri proxy issue | In dev mode, ensure the backend is running on port 8000. In production, check the Tauri sidecar logs. |
| WebSocket disconnects | Network interruption, backend restart, or timeout | The frontend auto-reconnects every 3 seconds. Check backend logs for crashes. |
| Model not found | Model not pulled in Ollama | Run `ollama list` to see available models. Pull the required model: `ollama pull qwen2.5:3b-instruct`. |
| WebView2 not found | Missing WebView2 runtime (rare on Windows 10+) | Install WebView2 Evergreen Bootstrapper from Microsoft. |
| Sidecar not found | PyInstaller build not run before Tauri build | Run `python scripts/build_backend.py` before `npm run tauri:build`. |

---

## Update System

Veyron uses the **Tauri updater plugin** for automatic updates.

### How Auto-Updates Work

1. **Startup check** — 5 seconds after launch, Veyron checks GitHub Releases for a newer version.
2. **Manual check** — Click "Check Now" in Settings → Updates.
3. **Discovery** — The updater fetches `latest.json` from the latest GitHub Release.
4. **Notification** — If an update is available, the UI shows update options.
5. **Download** — Background download with progress tracking (resumable).
6. **Verification** — Tauri verifies the Ed25519 signature before installing.
7. **Installation** — The new installer replaces the old version. User data is preserved in `%APPDATA%\Veyron`.
8. **Restart** — User is prompted to restart the application.

### Update States

| State | Description |
|-------|-------------|
| Idle | Up to date |
| Checking | Querying update endpoint |
| Available | New version found — click "Update Now" |
| Downloading | Background download in progress |
| Installed | Ready to apply — click "Restart Now" |
| Failed | Error — click "Retry" |

### Recovery

- The existing installation is never deleted before the new one is verified.
- If installation fails, Veyron continues running the old version.
- Manual downloads are always available from GitHub Releases.
- Rollback: install a previous version manually (user data is preserved).

---

## User Data Locations

| OS | Data Directory |
|----|----------------|
| Windows | `%APPDATA%\Veyron\` |
| macOS | `~/Library/Application Support/Veyron/` |
| Linux | `~/.local/share/veyron/` |

Contains: `veyron.db` (SQLite database), `config.json` (user preferences), `logs/`, `models/`, `audit/`.
