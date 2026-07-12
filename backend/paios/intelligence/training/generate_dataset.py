"""Generate 5000 realistic training examples for a local AI operating system.

Output: backend/data/training/synthetic_training_data.jsonl
"""

from __future__ import annotations

import json
import random
import hashlib
from pathlib import Path
from typing import Any

random.seed(42)

OUTPUT = Path(__file__).resolve().parents[4] / "backend" / "data" / "training" / "synthetic_training_data.jsonl"

# ── Templates ──────────────────────────────────────────────────────────────────

SYSTEM_TEMPLATES = [
    ("what's my current cpu usage", "system_management", ["system_monitor"], {"metric": "cpu"}, "easy", False),
    ("show me the cpu load right now", "system_management", ["system_monitor"], {"metric": "cpu"}, "easy", False),
    ("is the cpu pegged?", "system_management", ["system_monitor"], {"metric": "cpu"}, "easy", False),
    ("how much ram is being used", "system_management", ["system_monitor"], {"metric": "memory"}, "easy", False),
    ("check memory usage", "system_management", ["system_monitor"], {"metric": "memory"}, "easy", False),
    ("show my disk space", "system_management", ["system_monitor"], {"metric": "disk"}, "easy", False),
    ("how much free disk do i have", "system_management", ["system_monitor"], {"metric": "disk"}, "easy", False),
    ("list running processes", "system_management", ["system_monitor"], {"metric": "processes"}, "easy", False),
    ("what processes are eating memory", "system_management", ["system_monitor"], {"metric": "processes"}, "moderate", False),
    ("top 5 processes by cpu", "system_management", ["system_monitor"], {"metric": "processes", "sort_by": "cpu", "limit": 5}, "easy", False),
    ("is the system healthy", "system_management", ["system_monitor"], {"metric": "health"}, "easy", False),
    ("run a health check", "system_management", ["system_monitor"], {"metric": "health"}, "easy", False),
    ("give me a full system overview", "system_management", ["system_monitor"], {"metric": "overview"}, "easy", False),
    ("check disk health on c drive", "system_management", ["system_monitor"], {"metric": "disk", "path": "C:\\"}, "moderate", False),
    ("monitor cpu temperature", "system_management", ["system_monitor"], {"metric": "cpu"}, "easy", False),
    ("show system uptime", "system_management", ["system_monitor"], {"metric": "uptime"}, "easy", False),
    ("how long has the system been running", "system_management", ["system_monitor"], {"metric": "uptime"}, "easy", False),
    ("what os version am i running", "system_management", ["system_monitor"], {"metric": "os"}, "easy", False),
    ("check network stats", "system_management", ["system_monitor"], {"metric": "network"}, "moderate", False),
    ("list processes using port 3000", "system_management", ["terminal"], {"command": "netstat -ano | findstr :3000"}, "moderate", False),
    ("what is listening on port 8080", "system_management", ["terminal"], {"command": "netstat -ano | findstr :8080"}, "moderate", False),
    ("check if docker is running", "system_management", ["terminal"], {"command": "docker info"}, "easy", False),
    ("show environment variables", "system_management", ["terminal"], {"command": "set"}, "easy", False),
    ("what python version is installed", "system_management", ["terminal"], {"command": "python --version"}, "easy", False),
    ("check node version", "system_management", ["terminal"], {"command": "node --version"}, "easy", False),
    ("check npm version", "system_management", ["terminal"], {"command": "npm --version"}, "easy", False),
    ("show the system path variable", "system_management", ["terminal"], {"command": "echo %PATH%"}, "easy", False),
    ("check disk usage of current directory", "system_management", ["terminal"], {"command": "du -sh ."}, "moderate", False),
    ("show io stats", "system_management", ["system_monitor"], {"metric": "disk_io"}, "moderate", False),
    ("are there any zombie processes", "system_management", ["terminal"], {"command": "tasklist /FI 'STATUS eq Unknown'"}, "moderate", False),
    ("report system vitals every 5 seconds", "system_management", ["system_monitor", "terminal"], {"metric": "overview"}, "hard", True),
    ("alert me if cpu goes above 90 percent", "system_management", ["system_monitor"], {"metric": "cpu"}, "hard", True),
    ("how many cores does my cpu have", "system_management", ["system_monitor"], {"metric": "cpu"}, "easy", False),
    ("what is my gpu", "system_management", ["terminal"], {"command": "wmic path win32_VideoController get name"}, "moderate", False),
    ("show system info", "system_management", ["terminal"], {"command": "systeminfo"}, "easy", False),
    ("check powershell version", "system_management", ["terminal"], {"command": "$PSVersionTable.PSVersion"}, "easy", False),
    ("list all services", "system_management", ["terminal"], {"command": "Get-Service"}, "moderate", False),
    ("is the web server running", "system_management", ["terminal"], {"command": "Get-Process -Name nginx -ErrorAction SilentlyContinue"}, "moderate", False),
    ("check swap usage", "system_management", ["system_monitor"], {"metric": "memory"}, "moderate", False),
    ("what is my ip address", "system_management", ["terminal"], {"command": "ipconfig | findstr IPv4"}, "easy", False),
    ("show network interfaces", "system_management", ["terminal"], {"command": "ipconfig /all"}, "easy", False),
    ("list installed programs", "system_management", ["terminal"], {"command": "Get-WmiObject Win32_Product | Select Name"}, "moderate", False),
    ("check if git is installed", "system_management", ["terminal"], {"command": "git --version"}, "easy", False),
    ("show current directory size", "system_management", ["terminal"], {"command": "Get-ChildItem -Recurse | Measure-Object -Property Length -Sum"}, "moderate", False),
    ("find large files over 100mb", "system_management", ["terminal", "filesystem_read"], {"command": "Get-ChildItem -Recurse -File | Where Length -gt 100MB"}, "moderate", True),
    ("what startup programs are enabled", "system_management", ["terminal"], {"command": "Get-CimInstance Win32_StartupCommand"}, "moderate", False),
    ("check if a port is open", "system_management", ["terminal"], {"command": "Test-NetConnection localhost -Port 3000"}, "moderate", False),
    ("list scheduled tasks", "system_management", ["terminal"], {"command": "Get-ScheduledTask"}, "moderate", False),
    ("check battery health", "system_management", ["terminal"], {"command": "powercfg /batteryreport"}, "moderate", False),
    ("how much space does node_modules take", "system_management", ["terminal", "filesystem_read"], {"command": "Get-ChildItem node_modules -Recurse -File | Measure Length -Sum"}, "moderate", True),
]

FILE_TEMPLATES = [
    ("read the readme file", "file_operation", ["filesystem_read"], {"path": "README.md"}, "easy", False),
    ("show me the contents of package.json", "file_operation", ["filesystem_read"], {"path": "package.json"}, "easy", False),
    ("list files in the current directory", "file_operation", ["filesystem_read"], {"path": "."}, "easy", False),
    ("what is in the src folder", "file_operation", ["filesystem_read"], {"path": "src"}, "easy", False),
    ("show me the gitignore", "file_operation", ["filesystem_read"], {"path": ".gitignore"}, "easy", False),
    ("read the config file", "file_operation", ["filesystem_read"], {"path": "config.yaml"}, "easy", False),
    ("list python files in the project", "file_operation", ["filesystem_read"], {"path": ".", "pattern": "*.py"}, "moderate", False),
    ("find all test files", "file_operation", ["filesystem_read"], {"path": "tests", "pattern": "test_*.py"}, "easy", False),
    ("show me the main entry point", "file_operation", ["filesystem_read"], {"path": "src/index.js"}, "easy", False),
    ("what does the dockerfile look like", "file_operation", ["filesystem_read"], {"path": "Dockerfile"}, "easy", False),
    ("list all markdown files", "file_operation", ["filesystem_read"], {"path": ".", "pattern": "*.md"}, "easy", False),
    ("show directory tree two levels deep", "file_operation", ["filesystem_read"], {"path": ".", "depth": 2}, "moderate", False),
    ("what is the structure of the project", "file_operation", ["filesystem_read"], {"path": ".", "depth": 3}, "moderate", False),
    ("find files containing the word api", "file_operation", ["filesystem_read"], {"path": ".", "search": "api"}, "moderate", False),
    ("check if there are any todo comments in the code", "file_operation", ["filesystem_read"], {"path": ".", "search": "TODO"}, "moderate", False),
    ("read the database schema file", "file_operation", ["filesystem_read"], {"path": "db/schema.sql"}, "easy", False),
    ("show the test setup file", "file_operation", ["filesystem_read"], {"path": "tests/setup.py"}, "easy", False),
    ("list configuration files in root", "file_operation", ["filesystem_read"], {"path": ".", "pattern": "*.{yaml,yml,toml,json}"}, "moderate", False),
    ("find all python imports in the codebase", "file_operation", ["filesystem_read", "terminal"], {"search": "import "}, "hard", True),
    ("show the most recently modified file", "file_operation", ["filesystem_read"], {"path": ".", "sort": "modified"}, "moderate", False),
    ("find all empty directories", "file_operation", ["filesystem_read"], {"path": ".", "find_empty": True}, "moderate", False),
    ("read the changelog", "file_operation", ["filesystem_read"], {"path": "CHANGELOG.md"}, "easy", False),
    ("check if the license file exists", "file_operation", ["filesystem_read"], {"path": "LICENSE"}, "easy", False),
    ("list files larger than 1mb", "file_operation", ["filesystem_read", "terminal"], {"path": ".", "min_size_mb": 1}, "moderate", True),
    ("show the contents of the env example file", "file_operation", ["filesystem_read"], {"path": ".env.example"}, "easy", False),
    ("read the first 20 lines of the main log", "file_operation", ["filesystem_read"], {"path": "logs/app.log", "lines": 20}, "moderate", False),
    ("find all javascript files in the frontend", "file_operation", ["filesystem_read"], {"path": "frontend/src", "pattern": "*.js"}, "easy", False),
    ("list all files that have been changed recently", "file_operation", ["filesystem_read"], {"path": ".", "sort": "modified", "limit": 20}, "moderate", False),
    ("show me the project directory structure", "file_operation", ["filesystem_read"], {"path": ".", "depth": 2}, "easy", False),
    ("find all tsx files", "file_operation", ["filesystem_read"], {"path": ".", "pattern": "*.tsx"}, "easy", False),
    ("search for the word deprecated in the codebase", "file_operation", ["filesystem_read"], {"path": ".", "search": "deprecated"}, "moderate", False),
    ("list all files without a gitignore entry", "file_operation", ["filesystem_read", "terminal"], {"path": "."}, "hard", True),
    ("read the docker compose file", "file_operation", ["filesystem_read"], {"path": "docker-compose.yml"}, "easy", False),
    ("show the package lock version", "file_operation", ["filesystem_read"], {"path": "package-lock.json", "lines": 5}, "easy", False),
    ("check if there are any json files with syntax errors", "file_operation", ["filesystem_read", "terminal"], {"path": ".", "pattern": "*.json"}, "moderate", True),
    ("find all config files", "file_operation", ["filesystem_read"], {"path": ".", "pattern": "*.config.*"}, "easy", False),
    ("show the file that defines the task model", "file_operation", ["filesystem_read"], {"path": "backend/paios/db/models.py"}, "easy", False),
    ("find files that dont have a newline at the end", "file_operation", ["filesystem_read", "terminal"], {"path": "."}, "hard", True),
    ("list all directories with an init file", "file_operation", ["filesystem_read"], {"path": ".", "pattern": "__init__.py"}, "moderate", False),
    ("show the project readme from the docs folder", "file_operation", ["filesystem_read"], {"path": "docs/README.md"}, "easy", False),
    ("find all image files in assets", "file_operation", ["filesystem_read"], {"path": "assets", "pattern": "*.{png,jpg,svg}"}, "easy", False),
    ("read the copyright notice", "file_operation", ["filesystem_read"], {"path": "COPYRIGHT"}, "easy", False),
    ("show all files with 0600 permissions", "file_operation", ["filesystem_read", "terminal"], {"path": "."}, "hard", True),
    ("list all files in the scripts directory with their sizes", "file_operation", ["filesystem_read"], {"path": "scripts"}, "easy", False),
    ("find files that contain the word password", "file_operation", ["filesystem_read"], {"path": ".", "search": "password"}, "moderate", False),
    ("show me the api routes definition", "file_operation", ["filesystem_read"], {"path": "backend/paios/api/routes"}, "easy", False),
    ("check if there are any binary files in the repo", "file_operation", ["filesystem_read", "terminal"], {"path": "."}, "moderate", True),
    ("list all environment files", "file_operation", ["filesystem_read"], {"path": ".", "pattern": ".env*"}, "easy", False),
    ("show the size of each top-level directory", "file_operation", ["filesystem_read", "terminal"], {"path": "."}, "moderate", True),
    ("find all yaml files", "file_operation", ["filesystem_read"], {"path": ".", "pattern": "*.{yaml,yml}"}, "easy", False),
]

TERMINAL_TEMPLATES = [
    ("run npm install", "tool_execution", ["terminal"], {"command": "npm install"}, "easy", False),
    ("build the frontend", "tool_execution", ["terminal"], {"command": "npm run build"}, "easy", False),
    ("run the tests", "tool_execution", ["terminal"], {"command": "npm test"}, "easy", False),
    ("start the dev server", "tool_execution", ["terminal"], {"command": "npm run dev"}, "easy", False),
    ("run linting", "tool_execution", ["terminal"], {"command": "npx eslint src/"}, "moderate", False),
    ("format all python files with black", "tool_execution", ["terminal"], {"command": "black ."}, "moderate", False),
    ("run ruff linter", "tool_execution", ["terminal"], {"command": "ruff check ."}, "moderate", False),
    ("check type annotations with mypy", "tool_execution", ["terminal"], {"command": "mypy backend/"}, "moderate", False),
    ("run pytest", "tool_execution", ["terminal"], {"command": "pytest"}, "easy", False),
    ("run a specific test file", "tool_execution", ["terminal"], {"command": "pytest tests/unit/test_agent.py"}, "moderate", False),
    ("run tests with coverage", "tool_execution", ["terminal"], {"command": "pytest --cov=backend/"}, "moderate", False),
    ("install a python package", "tool_execution", ["terminal"], {"command": "pip install requests"}, "easy", False),
    ("update all pip packages", "tool_execution", ["terminal"], {"command": "pip list --outdated --format=freeze | %{$_.Split('==')[0]} | pip install --upgrade"}, "hard", False),
    ("run git status", "tool_execution", ["terminal"], {"command": "git status"}, "easy", False),
    ("show git log", "tool_execution", ["terminal"], {"command": "git log --oneline -10"}, "easy", False),
    ("show git diff", "tool_execution", ["terminal"], {"command": "git diff"}, "moderate", False),
    ("check which branch i am on", "tool_execution", ["terminal"], {"command": "git branch"}, "easy", False),
    ("pull latest changes", "tool_execution", ["terminal"], {"command": "git pull"}, "easy", False),
    ("check for uncommitted changes", "tool_execution", ["terminal"], {"command": "git status --short"}, "easy", False),
    ("show git log with graph", "tool_execution", ["terminal"], {"command": "git log --oneline --graph --all"}, "moderate", False),
    ("list git tags", "tool_execution", ["terminal"], {"command": "git tag"}, "easy", False),
    ("show commit details for the last commit", "tool_execution", ["terminal"], {"command": "git show HEAD"}, "moderate", False),
    ("who wrote this file", "tool_execution", ["terminal"], {"command": "git log --follow --format='%an' README.md"}, "moderate", False),
    ("show unstaged changes", "tool_execution", ["terminal"], {"command": "git diff --name-only"}, "easy", False),
    ("show staged changes", "tool_execution", ["terminal"], {"command": "git diff --cached --name-only"}, "easy", False),
    ("list all remotes", "tool_execution", ["terminal"], {"command": "git remote -v"}, "easy", False),
    ("create a new branch called feature-x", "tool_execution", ["terminal"], {"command": "git checkout -b feature-x"}, "moderate", False),
    ("run node script", "tool_execution", ["terminal"], {"command": "node scripts/migrate.js"}, "moderate", False),
    ("run database migrations", "tool_execution", ["terminal"], {"command": "alembic upgrade head"}, "moderate", False),
    ("seed the database", "tool_execution", ["terminal"], {"command": "python scripts/seed.py"}, "moderate", False),
    ("create a virtual environment", "tool_execution", ["terminal"], {"command": "python -m venv .venv"}, "moderate", False),
    ("activate the virtual environment", "tool_execution", ["terminal"], {"command": ".venv\\Scripts\\activate"}, "easy", False),
    ("sync dependencies with uv", "tool_execution", ["terminal"], {"command": "uv sync"}, "moderate", False),
    ("run a shell command", "tool_execution", ["terminal"], {"command": "echo hello world"}, "easy", False),
    ("show disk usage for current folder", "tool_execution", ["terminal"], {"command": "du -sh *"}, "moderate", False),
    ("count lines of code", "tool_execution", ["terminal"], {"command": "git ls-files | xargs wc -l"}, "moderate", False),
    ("count lines in python files", "tool_execution", ["terminal"], {"command": "Get-ChildItem -Recurse *.py | Get-Content | Measure-Object -Line"}, "moderate", False),
    ("find large files", "tool_execution", ["terminal"], {"command": "Get-ChildItem -Recurse -File | Sort-Object Length -Descending | Select-Object -First 10 Name,Length"}, "moderate", False),
    ("list all files modified today", "tool_execution", ["terminal"], {"command": "Get-ChildItem -Recurse -File | Where LastWriteTime -gt (Get-Date).Date"}, "moderate", False),
    ("compress this folder into a zip", "tool_execution", ["terminal"], {"command": "Compress-Archive -Path . -DestinationPath backup.zip"}, "moderate", False),
    ("extract a tar archive", "tool_execution", ["terminal"], {"command": "tar -xzf archive.tar.gz"}, "moderate", False),
    ("download a file from the internet", "tool_execution", ["terminal"], {"command": "curl -O https://example.com/file.zip"}, "moderate", False),
    ("make a directory", "tool_execution", ["terminal"], {"command": "mkdir temp"}, "easy", False),
    ("copy a file", "tool_execution", ["terminal"], {"command": "cp config.example.yaml config.yaml"}, "moderate", False),
    ("run the application", "tool_execution", ["terminal"], {"command": "uvicorn paios.main:app --reload"}, "moderate", False),
    ("start the api in production mode", "tool_execution", ["terminal"], {"command": "uvicorn paios.main:app --host 0.0.0.0 --port 8000"}, "moderate", False),
    ("test the health endpoint", "tool_execution", ["terminal"], {"command": "curl http://localhost:8000/api/health"}, "moderate", False),
    ("list all npm scripts", "tool_execution", ["terminal"], {"command": "npm run"}, "easy", False),
    ("install frontend dependencies", "tool_execution", ["terminal"], {"command": "npm install --prefix frontend"}, "moderate", False),
    ("build the frontend for production", "tool_execution", ["terminal"], {"command": "npm run build --prefix frontend"}, "moderate", False),
]

PROJECT_ANALYSIS_TEMPLATES = [
    ("analyze this project", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("what technologies does this project use", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("detect the tech stack", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("scan for issues in the project", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("find problems in the codebase", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("analyze the frontend directory", "project_analysis", ["project_analyzer"], {"path": "frontend"}, "easy", False),
    ("analyze the backend source", "project_analysis", ["project_analyzer"], {"path": "backend"}, "easy", False),
    ("what is the architecture of this project", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("give me a project health report", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("check if there are any outdated dependencies", "project_analysis", ["project_analyzer", "terminal"], {"path": "."}, "moderate", True),
    ("what testing framework does this project use", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("is this a python project or a node project", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("summarize the project structure", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("what build tools are configured", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("are there any security vulnerabilities in the dependencies", "project_analysis", ["project_analyzer", "terminal"], {"path": "."}, "hard", True),
    ("generate a project report", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("does the project have a ci pipeline", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("find all external api calls in the code", "project_analysis", ["project_analyzer", "filesystem_read"], {"path": ".", "search": "https?://"}, "hard", True),
    ("check code quality metrics", "project_analysis", ["project_analyzer", "terminal"], {"path": "."}, "hard", True),
    ("what linters are configured", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("recommend improvements for this project", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("analyze the test coverage setup", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("find unused dependencies", "project_analysis", ["project_analyzer", "terminal"], {"path": "."}, "hard", True),
    ("check the project against best practices", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("is this project using typescript", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("what version of python does this need", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("find all configuration files", "project_analysis", ["project_analyzer", "filesystem_read"], {"path": "."}, "moderate", True),
    ("check if docker is configured", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("does this project have adequate documentation", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("find duplicated code", "project_analysis", ["project_analyzer", "terminal"], {"path": "."}, "hard", True),
    ("analyze the project for potential improvements", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("check if there is a changelog", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("what database does this project use", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("list all dependencies with their versions", "project_analysis", ["project_analyzer", "filesystem_read"], {"path": "."}, "moderate", True),
    ("analyze the codebase for technical debt", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("check if there are any deprecated packages", "project_analysis", ["project_analyzer", "terminal"], {"path": "."}, "moderate", True),
    ("what framework is used for the frontend", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("is this a monorepo", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("analyze only the backend dependencies", "project_analysis", ["project_analyzer"], {"path": "backend"}, "easy", False),
    ("check if the project has proper error handling", "project_analysis", ["project_analyzer", "filesystem_read"], {"path": "."}, "hard", True),
    ("what orm is being used", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("generate a dependency graph", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("find inconsistent naming conventions", "project_analysis", ["project_analyzer", "filesystem_read"], {"path": "."}, "hard", True),
    ("check the project for common anti-patterns", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
    ("what testing tools are available", "project_analysis", ["project_analyzer"], {"path": "."}, "easy", False),
    ("analyze the frontend and backend separately", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", True),
    ("check for hardcoded configuration", "project_analysis", ["project_analyzer", "filesystem_read"], {"path": ".", "search": "hardcoded"}, "hard", True),
    ("does the project use environment variables properly", "project_analysis", ["project_analyzer", "filesystem_read"], {"path": "."}, "moderate", True),
    ("find all the todo and fixme comments", "project_analysis", ["project_analyzer", "filesystem_read"], {"path": ".", "search": "TODO|FIXME"}, "moderate", True),
    ("rate the project on code quality", "project_analysis", ["project_analyzer"], {"path": "."}, "moderate", False),
]

DEBUGGING_TEMPLATES = [
    ("why is the build failing", "debugging", ["terminal", "filesystem_read"], {"command": "npm run build"}, "moderate", True),
    ("the tests are failing can you check why", "debugging", ["terminal", "filesystem_read"], {"command": "pytest -v"}, "moderate", True),
    ("the server wont start", "debugging", ["terminal", "filesystem_read"], {"command": "uvicorn paios.main:app"}, "moderate", True),
    ("find errors in the log file", "debugging", ["filesystem_read", "terminal"], {"path": "logs", "search": "ERROR"}, "moderate", True),
    ("debug this python traceback", "debugging", ["filesystem_read"], {"path": "traceback.log"}, "hard", False),
    ("the app is crashing on startup", "debugging", ["terminal", "filesystem_read"], {"command": "python app.py"}, "hard", True),
    ("why is the import failing", "debugging", ["filesystem_read", "terminal"], {"path": ".", "search": "ModuleNotFoundError"}, "moderate", True),
    ("check if there is a syntax error in the code", "debugging", ["terminal"], {"command": "python -m py_compile backend/paios/main.py"}, "moderate", False),
    ("find the source of a null pointer exception", "debugging", ["filesystem_read", "terminal"], {"path": ".", "search": "NoneType"}, "hard", True),
    ("why is the docker build failing", "debugging", ["terminal", "filesystem_read"], {"command": "docker build ."}, "hard", True),
    ("investigate the performance issue", "debugging", ["system_monitor", "terminal"], {"metric": "overview"}, "hard", True),
    ("why is the api returning 500 errors", "debugging", ["terminal", "filesystem_read"], {"command": "curl http://localhost:8000/api/health"}, "moderate", True),
    ("find the line causing the division by zero", "debugging", ["filesystem_read"], {"path": ".", "search": "/ "}, "hard", False),
    ("the frontend is not rendering", "debugging", ["terminal", "filesystem_read"], {"command": "npm run build --prefix frontend"}, "moderate", True),
    ("why is the database connection failing", "debugging", ["terminal", "filesystem_read"], {"command": "python -c 'import sqlite3; sqlite3.connect(\"test.db\")'"}, "moderate", True),
    ("check if there is a memory leak", "debugging", ["system_monitor", "terminal"], {"metric": "memory"}, "hard", True),
    ("why did the process exit with code 1", "debugging", ["terminal"], {"command": "echo %ERRORLEVEL%"}, "moderate", False),
    ("the git merge failed", "debugging", ["terminal"], {"command": "git status"}, "moderate", False),
    ("find circular imports", "debugging", ["filesystem_read", "terminal"], {"path": ".", "search": "import "}, "hard", True),
    ("why is the webpack bundle so large", "debugging", ["terminal", "filesystem_read"], {"command": "npx webpack --analyze"}, "hard", True),
    ("debug the websocket disconnection", "debugging", ["filesystem_read", "terminal"], {"path": ".", "search": "websocket"}, "hard", True),
    ("why is the form validation failing", "debugging", ["filesystem_read"], {"path": ".", "search": "validate"}, "moderate", False),
    ("check for timeout issues", "debugging", ["filesystem_read"], {"path": ".", "search": "timeout"}, "moderate", False),
    ("the ci pipeline is red", "debugging", ["terminal"], {"command": "git log --oneline -5"}, "moderate", False),
    ("find the commit that introduced a bug", "debugging", ["terminal"], {"command": "git bisect start"}, "hard", False),
    ("why is the endpoint returning empty data", "debugging", ["filesystem_read", "terminal"], {"path": ".", "search": "return None"}, "moderate", True),
    ("the production build is different from dev", "debugging", ["terminal", "filesystem_read"], {"command": "npm run build"}, "moderate", True),
    ("check for port conflicts", "debugging", ["terminal"], {"command": "netstat -ano | findstr :8000"}, "moderate", False),
    ("why are the styles not loading", "debugging", ["filesystem_read", "terminal"], {"path": "frontend/src"}, "moderate", True),
    ("investigate a slow database query", "debugging", ["filesystem_read", "terminal"], {"path": ".", "search": "SELECT"}, "hard", True),
    ("the test environment is not set up correctly", "debugging", ["terminal", "filesystem_read"], {"command": "pytest --setup-show"}, "moderate", True),
    ("why is the type check failing", "debugging", ["terminal"], {"command": "mypy backend/"}, "moderate", False),
    ("find the unhandled exception in the logs", "debugging", ["filesystem_read"], {"path": "logs", "search": "Exception"}, "moderate", False),
    ("the async code is not awaiting", "debugging", ["filesystem_read"], {"path": ".", "search": "async def"}, "hard", False),
    ("why is the file watcher not triggering", "debugging", ["filesystem_read", "terminal"], {"path": ".", "search": "watch"}, "hard", True),
]

CODING_TEMPLATES = [
    ("write a python function to read a csv file", "coding_task", ["filesystem_read", "terminal"], {"command": "python -c 'import csv'"}, "moderate", True),
    ("create a new api endpoint", "coding_task", ["filesystem_read", "terminal"], {"path": "backend/paios/api/routes"}, "hard", True),
    ("add error handling to this function", "coding_task", ["filesystem_read"], {"path": "."}, "moderate", False),
    ("write a unit test for the agent module", "coding_task", ["filesystem_read", "terminal"], {"path": "backend/paios/core/agent.py"}, "hard", True),
    ("refactor this code to use async", "coding_task", ["filesystem_read"], {"path": "."}, "hard", False),
    ("add type annotations to the codebase", "coding_task", ["filesystem_read", "terminal"], {"path": "."}, "moderate", True),
    ("create a new tool class", "coding_task", ["filesystem_read", "terminal"], {"path": "backend/paios/tools"}, "hard", True),
    ("write a bash script to automate backups", "coding_task", ["filesystem_read", "terminal"], {"command": "cat > backup.sh"}, "moderate", True),
    ("add a new route to the api", "coding_task", ["filesystem_read", "terminal"], {"path": "backend/paios/api/routes"}, "hard", True),
    ("create a database migration", "coding_task", ["filesystem_read", "terminal"], {"command": "alembic revision --autogenerate"}, "hard", True),
    ("add input validation to the tool", "coding_task", ["filesystem_read"], {"path": "."}, "moderate", False),
    ("write a json schema validator", "coding_task", ["filesystem_read", "terminal"], {"command": "python -c 'import jsonschema'"}, "moderate", True),
    ("implement a caching layer", "coding_task", ["filesystem_read"], {"path": "."}, "hard", False),
    ("create a new react component", "coding_task", ["filesystem_read", "terminal"], {"path": "frontend/src/components"}, "moderate", True),
    ("write a custom hook", "coding_task", ["filesystem_read", "terminal"], {"path": "frontend/src/hooks"}, "moderate", True),
    ("add tailwind styles to the component", "coding_task", ["filesystem_read"], {"path": "frontend/src"}, "moderate", False),
    ("write a performance benchmark", "coding_task", ["filesystem_read", "terminal"], {"path": "benchmarks"}, "hard", True),
    ("set up eslint configuration", "coding_task", ["filesystem_read", "terminal"], {"command": "npx eslint --init"}, "moderate", True),
    ("create a configuration class", "coding_task", ["filesystem_read"], {"path": "."}, "moderate", False),
    ("implement a retry decorator", "coding_task", ["filesystem_read", "terminal"], {"command": "python -c 'import functools'"}, "moderate", True),
    ("write a data migration script", "coding_task", ["filesystem_read", "terminal"], {"path": "scripts"}, "hard", True),
    ("add logging to the application", "coding_task", ["filesystem_read"], {"path": "."}, "moderate", False),
    ("create a new page component", "coding_task", ["filesystem_read", "terminal"], {"path": "frontend/src/pages"}, "moderate", True),
    ("set up a state management store", "coding_task", ["filesystem_read", "terminal"], {"path": "frontend/src/stores"}, "moderate", True),
    ("write a cli entry point", "coding_task", ["filesystem_read", "terminal"], {"path": "backend/paios"}, "hard", True),
    ("add environment variable support", "coding_task", ["filesystem_read"], {"path": "."}, "moderate", False),
    ("create a websocket handler", "coding_task", ["filesystem_read", "terminal"], {"path": "backend/paios/api"}, "hard", True),
    ("implement rate limiting", "coding_task", ["filesystem_read"], {"path": "."}, "hard", False),
    ("write a system health check endpoint", "coding_task", ["filesystem_read", "terminal"], {"path": "backend/paios/api/routes"}, "hard", True),
    ("build a file watcher utility", "coding_task", ["filesystem_read", "terminal"], {"path": "backend/paios/tools"}, "hard", True),
]

PLANNING_TEMPLATES = [
    ("set up a new development environment", "planning_task", ["terminal", "filesystem_read"], {"command": "python -m venv .venv"}, "moderate", True),
    ("deploy the application to production", "planning_task", ["terminal", "filesystem_read", "project_analyzer"], {"path": "."}, "hard", True),
    ("migrate the database and verify", "planning_task", ["terminal", "filesystem_read"], {"command": "alembic upgrade head"}, "hard", True),
    ("set up ci cd for this project", "planning_task", ["project_analyzer", "filesystem_read", "terminal"], {"path": "."}, "hard", True),
    ("prepare a release", "planning_task", ["terminal", "filesystem_read", "project_analyzer"], {"command": "git tag"}, "hard", True),
    ("investigate and fix the production issue", "planning_task", ["system_monitor", "terminal", "filesystem_read"], {"metric": "overview"}, "hard", True),
    ("optimize the application performance", "planning_task", ["system_monitor", "project_analyzer", "terminal"], {"metric": "overview"}, "hard", True),
    ("set up logging and monitoring", "planning_task", ["filesystem_read", "terminal", "system_monitor"], {"path": "."}, "hard", True),
    ("implement a new feature end to end", "planning_task", ["project_analyzer", "filesystem_read", "terminal"], {"path": "."}, "hard", True),
    ("upgrade all dependencies safely", "planning_task", ["terminal", "filesystem_read", "project_analyzer"], {"command": "pip list --outdated"}, "hard", True),
    ("run the full test suite and report", "planning_task", ["terminal", "filesystem_read"], {"command": "pytest -v --tb=long"}, "moderate", True),
    ("backup the database and archive logs", "planning_task", ["terminal", "filesystem_read"], {"command": "sqlite3 data.db .dump"}, "hard", True),
    ("compare two branches and summarize differences", "planning_task", ["terminal", "filesystem_read"], {"command": "git diff main..feature"}, "moderate", True),
    ("audit security of the project", "planning_task", ["project_analyzer", "filesystem_read", "terminal"], {"path": "."}, "hard", True),
    ("create a development workflow", "planning_task", ["filesystem_read", "terminal"], {"path": "."}, "hard", True),
    ("set up code review automation", "planning_task", ["terminal", "project_analyzer"], {"command": "npx lint-staged"}, "hard", True),
    ("migrate from javascript to typescript", "planning_task", ["project_analyzer", "filesystem_read", "terminal"], {"path": "."}, "hard", True),
    ("containerize the application", "planning_task", ["project_analyzer", "filesystem_read", "terminal"], {"path": "."}, "hard", True),
    ("implement a microservice architecture", "planning_task", ["project_analyzer", "filesystem_read", "terminal"], {"path": "."}, "hard", True),
    ("set up a staging environment", "planning_task", ["terminal", "filesystem_read", "project_analyzer"], {"command": "docker compose up"}, "hard", True),
]

QUESTION_TEMPLATES = [
    ("what does this error message mean", "question_answering", ["filesystem_read", "terminal"], {"search": "error"}, "moderate", False),
    ("how do i install this project", "question_answering", ["filesystem_read"], {"path": "README.md"}, "easy", False),
    ("what is the purpose of this config option", "question_answering", ["filesystem_read"], {"path": "config.example.yaml"}, "easy", False),
    ("how do i run the tests", "question_answering", ["filesystem_read"], {"path": "README.md"}, "easy", False),
    ("what does this command do", "question_answering", ["filesystem_read", "terminal"], {"command": "command --help"}, "moderate", False),
    ("how are tasks created in the system", "question_answering", ["filesystem_read"], {"path": "backend/paios/core/task_manager.py"}, "moderate", False),
    ("what is the architecture of paios", "question_answering", ["filesystem_read"], {"path": "ARCHITECTURE.md"}, "easy", False),
    ("how does the security layer work", "question_answering", ["filesystem_read"], {"path": "ARCHITECTURE.md"}, "moderate", False),
    ("what tools are available", "question_answering", ["filesystem_read"], {"path": "backend/paios/tools"}, "easy", False),
    ("how does the memory system work", "question_answering", ["filesystem_read"], {"path": "ARCHITECTURE.md"}, "moderate", False),
    ("when was the last release", "question_answering", ["terminal"], {"command": "git tag --sort=-creatordate"}, "moderate", False),
    ("what version of this project is running", "question_answering", ["filesystem_read"], {"path": "pyproject.toml"}, "easy", False),
    ("explain the project layout", "question_answering", ["filesystem_read"], {"path": "README.md"}, "easy", False),
    ("what is the default configuration", "question_answering", ["filesystem_read"], {"path": "config.example.yaml"}, "easy", False),
    ("how do i add a new tool", "question_answering", ["filesystem_read"], {"path": "backend/paios/tools/base.py"}, "moderate", False),
    ("what are the design principles", "question_answering", ["filesystem_read"], {"path": "ARCHITECTURE.md"}, "easy", False),
    ("how does planning work", "question_answering", ["filesystem_read"], {"path": "ARCHITECTURE.md"}, "moderate", False),
    ("what is the roadmap", "question_answering", ["filesystem_read"], {"path": "ROADMAP.md"}, "easy", False),
    ("what database does this use", "question_answering", ["filesystem_read"], {"path": "pyproject.toml"}, "easy", False),
    ("how do i contribute", "question_answering", ["filesystem_read"], {"path": "CONTRIBUTING.md"}, "easy", False),
]

CONVERSATION_TEMPLATES = [
    ("hello", "conversation", [], {}, "easy", False),
    ("good morning", "conversation", [], {}, "easy", False),
    ("what can you do", "conversation", [], {}, "easy", False),
    ("tell me a fun fact", "conversation", [], {}, "easy", False),
    ("how are you", "conversation", [], {}, "easy", False),
    ("thanks for your help", "conversation", [], {}, "easy", False),
    ("goodbye", "conversation", [], {}, "easy", False),
    ("what is your name", "conversation", [], {}, "easy", False),
    ("who created you", "conversation", [], {}, "easy", False),
    ("i need help with something", "conversation", [], {}, "easy", False),
    ("can you assist me", "conversation", [], {}, "easy", False),
    ("are you an ai", "conversation", [], {}, "easy", False),
    ("how does this work", "conversation", [], {}, "easy", False),
    ("im stuck", "conversation", [], {}, "easy", False),
    ("show me around", "conversation", [], {}, "easy", False),
]

# ── Generation ─────────────────────────────────────────────────────────────────

ALL_TEMPLATES: list[tuple[str, str, list[str], dict[str, Any], str, bool]] = (
    SYSTEM_TEMPLATES
    + FILE_TEMPLATES
    + TERMINAL_TEMPLATES
    + PROJECT_ANALYSIS_TEMPLATES
    + DEBUGGING_TEMPLATES
    + CODING_TEMPLATES
    + PLANNING_TEMPLATES
    + QUESTION_TEMPLATES
    + CONVERSATION_TEMPLATES
)

DIFFICULTY_REPHRASE = {
    "easy": [
        "can you {}",
        "could you {}",
        "please {}",
        "i need you to {}",
        "{}",
        "hey, {}",
        "{} please",
    ],
    "moderate": [
        "i need help: {}",
        "could you please {}",
        "can you help me {}",
        "id like you to {}",
        "would you {}",
        "im trying to {}",
        "can i get you to {}",
        "hey can you {}",
    ],
    "hard": [
        "i need you to {} and then let me know",
        "im working on something: can you {}",
        "ive been trying to {} but its not working",
        "this is complex: {}",
        "i could use your help with {}",
        "can you take a look at {}",
        "need to {} — can you handle this",
        "heres a tricky one: {}",
    ],
}

LOCATION_VARIANTS = [
    "in this project",
    "in the current directory",
    "in the codebase",
    "in the repository",
    "in this folder",
    "",
    "here",
    "in the workspace",
    "for this repo",
    "in the project root",
]

PROJECT_SUFFIXES = [
    " for the python backend",
    " in the frontend code",
    " in the api layer",
    " for the database",
    " in the configuration",
    " across the whole app",
    " in the source code",
    " in the test suite",
    " for the tools module",
    " in the core module",
]

def rephrase(template: str, difficulty: str) -> str:
    fmt = random.choice(DIFFICULTY_REPHRASE[difficulty])
    result = fmt.format(template)
    if random.random() < 0.15:
        suffix = random.choice(LOCATION_VARIANTS)
        if suffix:
            result += " " + suffix
    if random.random() < 0.08 and difficulty in ("moderate", "hard"):
        if not any(s in result for s in PROJECT_SUFFIXES):
            result += random.choice(PROJECT_SUFFIXES)
    return result.strip()


def mutate_params(params: dict[str, Any]) -> dict[str, Any]:
    mutated = dict(params)
    if "path" in mutated and mutated["path"] == ".":
        if random.random() < 0.2:
            mutated["path"] = random.choice([".", "src", "backend", "frontend", "tests", "docs"])
    if "metric" in mutated:
        if random.random() < 0.15:
            mutated["metric"] = random.choice(["cpu", "memory", "disk", "processes", "health"])
    return mutated


def generate() -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    target = 5000

    while len(examples) < target:
        template, intent, tools, params, difficulty, needs_planning = random.choice(ALL_TEMPLATES)

        request = rephrase(template, difficulty)
        params = mutate_params(params)

        raw = f"{request}|{'|'.join(sorted(tools))}|{intent}"
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        difficulty_d = difficulty
        if needs_planning and difficulty_d == "easy":
            difficulty_d = "moderate"

        ex = {
            "request": request,
            "intent": intent,
            "expected_tools": sorted(set(tools)),
            "expected_parameters": params,
            "difficulty": difficulty_d,
            "planning_required": needs_planning,
        }
        examples.append(ex)

        if len(examples) % 1000 == 0:
            print(f"  generated {len(examples)} examples...")

    return examples


def main() -> None:
    print("Generating 5000 training examples...")
    examples = generate()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    intents = {}
    diffs = {}
    plan_count = 0
    for ex in examples:
        intents[ex["intent"]] = intents.get(ex["intent"], 0) + 1
        diffs[ex["difficulty"]] = diffs.get(ex["difficulty"], 0) + 1
        if ex["planning_required"]:
            plan_count += 1

    print(f"\nSaved to: {OUTPUT}")
    print(f"Total: {len(examples)}")
    print(f"\nIntent distribution:")
    for k, v in sorted(intents.items(), key=lambda x: -x[1]):
        print(f"  {k:30s} {v:4d} ({v/len(examples)*100:5.1f}%)")
    print(f"\nDifficulty distribution:")
    for k, v in sorted(diffs.items(), key=lambda x: -x[1]):
        print(f"  {k:30s} {v:4d} ({v/len(examples)*100:5.1f}%)")
    print(f"\nPlanning required: {plan_count} ({plan_count/len(examples)*100:.1f}%)")


if __name__ == "__main__":
    main()
