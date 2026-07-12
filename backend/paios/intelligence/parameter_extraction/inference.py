"""Inference API for the parameter extraction micro-model.

Provides ``predict_parameters()`` as the primary entrypoint.
Falls back to empty dict if no trained model is available.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from paios.intelligence.parameter_extraction.model import ParameterExtractionModel

logger = logging.getLogger(__name__)

_model: ParameterExtractionModel | None = None
_model_path: str | None = None


def _default_model_path() -> str:
    from paios.config import DATA_DIR
    return str(DATA_DIR / "models" / "parameter_extraction.pkl")


def _load_model() -> ParameterExtractionModel | None:
    global _model
    if _model is not None:
        return _model

    path = _model_path or _default_model_path()
    model_path = Path(path)
    if not model_path.exists():
        logger.info("no parameter extraction model found at %s", model_path)
        return None

    try:
        model = ParameterExtractionModel()
        model.load(str(model_path))
        _model = model
        logger.info("parameter extraction model loaded from %s", path)
        return model
    except Exception as e:
        logger.warning("failed to load parameter extraction model: %s", e)
        return None


def predict_parameters(
    text: str,
    tool_name: str,
    model_path: str | None = None,
) -> dict[str, Any]:
    """Predict tool parameters from a user request.

    Args:
        text: The user's request text.
        tool_name: The tool to predict parameters for.
        model_path: Optional path to a trained model pickle.

    Returns:
        Dict of predicted parameter names to values.
        Empty dict if no model is available.
    """
    global _model_path
    if model_path is not None:
        _model_path = model_path

    model = _load_model()
    if model is not None and model.fitted:
        return model.predict(text, tool_name)

    return {}


def predict_parameters_multitool(
    text: str,
    tool_names: list[str],
    model_path: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Predict parameters for multiple tools at once.

    Args:
        text: The user's request text.
        tool_names: List of tool names to predict parameters for.
        model_path: Optional path to a trained model pickle.

    Returns:
        Dict mapping tool_name -> {param: value} predictions.
    """
    global _model_path
    if model_path is not None:
        _model_path = model_path

    model = _load_model()
    if model is not None and model.fitted:
        return {t: model.predict(text, t) for t in tool_names}

    return {}


def reset_model() -> None:
    global _model, _model_path
    _model = None
    _model_path = None
