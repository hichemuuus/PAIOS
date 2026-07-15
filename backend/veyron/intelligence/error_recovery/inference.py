from __future__ import annotations

import logging
from pathlib import Path

from veyron.intelligence.error_recovery.model import ErrorRecoveryModel
from veyron.intelligence.error_recovery.schema import (
    RECOVERY_CONFIDENCE_THRESHOLD,
    ErrorRecoveryPrediction,
    RecoveryAction,
)

logger = logging.getLogger(__name__)

_model: ErrorRecoveryModel | None = None
_model_path: str | None = None


def _default_model_path() -> str:
    from veyron.config import DATA_DIR
    return str(DATA_DIR / "models" / "error_recovery.pkl")


def _load_model() -> ErrorRecoveryModel | None:
    global _model
    if _model is not None:
        return _model

    path = _model_path or _default_model_path()
    model_file = Path(path)
    if not model_file.exists():
        logger.info("no error recovery model found at %s", model_file)
        return None

    try:
        model = ErrorRecoveryModel()
        model.load(str(model_file))
        _model = model
        logger.info("error recovery model loaded from %s", path)
        return model
    except Exception as e:
        logger.warning("failed to load error recovery model: %s", e)
        return None


def predict_recovery_action(
    error_message: str,
    tool_name: str,
    task_context: str = "",
    previous_action: str = "none",
    model_path: str | None = None,
) -> ErrorRecoveryPrediction:
    global _model_path
    if model_path is not None:
        _model_path = model_path

    if not error_message or not error_message.strip():
        return ErrorRecoveryPrediction(
            error_message=error_message,
            tool_name=tool_name,
            recovery_action=RecoveryAction.FALLBACK_LLM,
            requires_llm=True,
            fallback=True,
        )

    model = _load_model()
    if model is None or not model.fitted:
        return ErrorRecoveryPrediction(
            error_message=error_message,
            tool_name=tool_name,
            recovery_action=RecoveryAction.FALLBACK_LLM,
            requires_llm=True,
            fallback=True,
        )

    text = f"{error_message} | tool: {tool_name} | context: {task_context} | previous: {previous_action}"
    action_str, confidence = model.predict_with_confidence(text)

    try:
        action = RecoveryAction(action_str)
    except ValueError:
        action = RecoveryAction.FALLBACK_LLM
        confidence = 0.0

    requires_llm = confidence < RECOVERY_CONFIDENCE_THRESHOLD or action == RecoveryAction.FALLBACK_LLM

    return ErrorRecoveryPrediction(
        error_message=error_message,
        tool_name=tool_name,
        recovery_action=action,
        confidence=round(confidence, 3),
        requires_llm=requires_llm,
        fallback=confidence < RECOVERY_CONFIDENCE_THRESHOLD,
    )


def reset_model() -> None:
    global _model, _model_path
    _model = None
    _model_path = None
