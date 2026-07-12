"""Schema for parameter extraction — defines the data model for a
future micro-model that predicts tool parameters from user requests.

Each tool has a known parameter schema. The parameter extraction model should
map a user request + tool name to the expected parameter values.

Not yet trained — this is the data contract for future implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParameterExample:
    """A single training example for parameter extraction.

    The model should learn to extract parameter values from the request text
    given the tool that will be called.
    """

    request: str
    tool_name: str
    expected_parameters: dict[str, Any] = field(default_factory=dict)
    intent_category: str = ""
    difficulty: str = "easy"


@dataclass
class ParameterPrediction:
    """Prediction output from the parameter extraction model."""

    tool_name: str
    predicted_parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    missing_parameters: list[str] = field(default_factory=list)


# ── Tool parameter schemas ────────────────────────────────────────────────

TOOL_PARAMETER_SCHEMAS: dict[str, dict[str, Any]] = {
    "filesystem_read": {
        "path": {"type": "string", "description": "File or directory path", "required": True},
        "action": {"type": "string", "description": "Action: read, list, or stat", "default": "read"},
        "pattern": {"type": "string", "description": "Glob pattern to filter files", "default": None},
        "depth": {"type": "integer", "description": "Directory recursion depth", "default": 1},
        "search": {"type": "string", "description": "Text to search for in files", "default": None},
        "lines": {"type": "integer", "description": "Number of lines to read", "default": None},
    },
    "system_monitor": {
        "metric": {
            "type": "string",
            "description": "Metric: cpu, memory, disk, processes, health, network, uptime",
            "required": True,
        },
        "sort_by": {"type": "string", "description": "Sort field for processes", "default": None},
        "limit": {"type": "integer", "description": "Max results to return", "default": None},
    },
    "terminal": {
        "command": {"type": "string", "description": "Shell command to execute", "required": True},
        "workdir": {"type": "string", "description": "Working directory", "default": None},
        "timeout": {"type": "integer", "description": "Command timeout in seconds", "default": 30},
    },
    "project_analyzer": {
        "path": {"type": "string", "description": "Project path to analyze", "required": True},
        "depth": {"type": "string", "description": "Analysis depth: basic, full", "default": "basic"},
    },
}
