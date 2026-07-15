from __future__ import annotations

from dataclasses import dataclass, field

PLANNING_CONFIDENCE_THRESHOLD = 0.50

PLANNING_STEP_CATEGORIES = [
    "research",
    "file_operation",
    "tool_execution",
    "coding_task",
    "debugging",
    "system_management",
    "project_analysis",
    "question_answering",
]

STEP_BIN_NONE = "none"
STEP_BIN_SINGLE = "single"
STEP_BIN_FEW = "few"
STEP_BIN_SEVERAL = "several"
STEP_BIN_MANY = "many"

STEP_BINS = [STEP_BIN_NONE, STEP_BIN_SINGLE, STEP_BIN_FEW, STEP_BIN_SEVERAL, STEP_BIN_MANY]


def step_bin_to_range(bin_name: str) -> tuple[int, int]:
    return {
        STEP_BIN_NONE: (0, 0),
        STEP_BIN_SINGLE: (1, 1),
        STEP_BIN_FEW: (2, 3),
        STEP_BIN_SEVERAL: (4, 6),
        STEP_BIN_MANY: (7, 10),
    }.get(bin_name, (0, 0))


def step_count_to_bin(count: int) -> str:
    if count <= 0:
        return STEP_BIN_NONE
    if count == 1:
        return STEP_BIN_SINGLE
    if count <= 3:
        return STEP_BIN_FEW
    if count <= 6:
        return STEP_BIN_SEVERAL
    return STEP_BIN_MANY


def bin_center(bin_name: str) -> int:
    lo, hi = step_bin_to_range(bin_name)
    return (lo + hi) // 2


@dataclass
class PlanningExample:
    request: str
    intent_category: str
    complexity: str
    requires_plan: bool
    estimated_steps: int
    step_categories: list[str] = field(default_factory=list)
    available_tools: list[str] = field(default_factory=list)
    failure_category: str = "unknown"


@dataclass
class PlanningPrediction:
    request: str
    requires_plan: bool
    estimated_steps: int
    step_categories: list[str] = field(default_factory=list)
    confidence: float = 0.0
    plan_confidence: float = 0.0
    steps_confidence: float = 0.0
    requires_llm: bool = True
    fallback: bool = False
