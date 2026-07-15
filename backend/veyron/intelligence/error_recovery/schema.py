from __future__ import annotations

import enum
from dataclasses import dataclass


class RecoveryAction(str, enum.Enum):
    RETRY = "retry"
    MODIFY_PARAMETERS = "modify_parameters"
    ALTERNATIVE_TOOL = "alternative_tool"
    CLARIFY = "clarify"
    FALLBACK_LLM = "fallback_llm"


RECOVERY_ACTIONS = [a.value for a in RecoveryAction]


@dataclass
class ErrorRecoveryExample:
    error_message: str
    tool_name: str
    task_context: str
    previous_action: str
    recovery_action: RecoveryAction
    difficulty: str = "moderate"
    failure_category: str = "unknown"


@dataclass
class ErrorRecoveryPrediction:
    error_message: str
    tool_name: str
    recovery_action: RecoveryAction
    confidence: float = 0.0
    requires_llm: bool = True
    fallback: bool = False


RECOVERY_CONFIDENCE_THRESHOLD = 0.50
